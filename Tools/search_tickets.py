"""
Búsqueda de tickets - Módulo centralizado para búsqueda por keywords, semántica e híbrida.
Incluye funciones de bajo nivel para FAISS y embeddings.
"""
import os
import logging
import requests
from typing import List, Dict, Any, Optional

import faiss
import numpy as np
import openai

from utils.debug_logger import log_debug_event
from utils.logs import log_ai_call
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# === Config para FAISS de tickets ===
OPENAI_API_KEY_SEMANTIC = (
    os.getenv("OPENAI_API_KEY_Semantic")
    or os.getenv("OPENAI_API_KEY_SEMANTIC")
    or os.getenv("OPENAI_API_KEY_V2")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("OPENAI_API_KEY_Clasificador")
)
FAISS_INDEX_PATH = "Data/faiss_index_ip.bin"
FAISS_IDS_PATH = "Data/faiss_ids.npy"

# === Globals para FAISS de tickets ===
faiss_index = None
issue_ids = None
faiss_loaded = False


def load_faiss_data():
    """Carga el índice FAISS y los IDs de tickets."""
    global faiss_index, issue_ids, faiss_loaded
    if faiss_loaded:
        return True
    try:
        faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        issue_ids = np.load(FAISS_IDS_PATH).astype("int64")
        faiss_loaded = True
        if faiss_index.ntotal != len(issue_ids):
            logger.warning(f"[SearchTickets] ⚠️ Inconsistencia FAISS: index size={faiss_index.ntotal}, ids={len(issue_ids)}")
        else:
            logger.info(f"[SearchTickets] ✅ FAISS cargado: {faiss_index.ntotal} vectores, {len(issue_ids)} IDs")
        return True
    except Exception as e:
        logger.error(f"[SearchTickets] ❌ Falló carga FAISS/IDs: {e}")
        return False


def init_semantic_tool():
    """Inicializa el tool semántico: configura API key y carga FAISS."""
    openai.api_key = OPENAI_API_KEY_SEMANTIC
    return load_faiss_data()


def generate_openai_embedding(query: str, conversation_id: str, interaction_id: Optional[int] = None) -> Optional[np.ndarray]:
    """
    Genera un embedding usando OpenAI para cualquier propósito (tickets, documentos, etc.).
    
    Args:
        query: Texto a convertir en embedding
        conversation_id: ID de conversación (para logging)
        interaction_id: ID de interacción (opcional, para logging)
    
    Returns:
        Vector normalizado L2 de forma (1, d) o None si hay error
    """
    try:
        log_debug_event("Búsqueda Semántica", conversation_id, interaction_id, "Generate Embedding", {"query": query})
        resp = openai.embeddings.create(model="text-embedding-ada-002", input=query)
        
        # Extraer token usage para logging de costos
        # OpenAI embeddings retorna usage con total_tokens y prompt_tokens
        token_usage = {}
        if hasattr(resp, 'usage'):
            usage = resp.usage
            if hasattr(usage, 'total_tokens'):
                token_usage = {
                    "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
                    "total_tokens": usage.total_tokens
                }
            elif hasattr(usage, 'prompt_tokens'):
                token_usage = {
                    "prompt_tokens": usage.prompt_tokens,
                    "total_tokens": getattr(usage, 'total_tokens', usage.prompt_tokens)
                }
            elif isinstance(usage, dict):
                token_usage = usage
        
        # Logging de costos para embeddings (solo CSV, no bloquea)
        try:
            safe_messages = [{"role": "user", "content": query[:200]}]  # Truncar para logging
            log_ai_call(
                call_type="Embedding Generation",
                model="text-embedding-ada-002",
                provider="openai",
                messages=safe_messages,
                response={"status": "success", "dimension": len(resp.data[0].embedding)},
                token_usage=token_usage if token_usage else {"prompt_tokens": 0, "total_tokens": 0},
                conversation_id=conversation_id,
                interaction_id=interaction_id,
                tool="generate_openai_embedding"
            )
        except Exception as log_error:
            # No bloquear si falla el logging
            logger.debug(f"[SearchTickets] Error al registrar embedding en log: {log_error}")
        
        vec = np.array(resp.data[0].embedding, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(vec)
        return vec
    except Exception as e:
        logger.error(f"[SearchTickets] ❌ Error embedding: {e}")
        log_debug_event("Búsqueda Semántica", conversation_id, interaction_id, "Embedding Error", {"error": str(e)})
        return None


def perform_faiss_search(vector: np.ndarray, k: int = 10) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Busca en el índice FAISS de tickets usando un vector de consulta.
    
    Args:
        vector: Vector de consulta normalizado de forma (1, d)
        k: Número de resultados a retornar
    
    Returns:
        Tupla (results, debug_info) donde:
        - results: Lista de dicts con {"ticket_id": int, "score": float} (score es distancia)
        - debug_info: Dict con información de debug
    """
    if faiss_index is None:
        logger.error("[SearchTickets] ❌ FAISS index no inicializado. Llama init_semantic_tool() primero.")
        return [], {"error": "FAISS not initialized"}
    
    distances, indices = faiss_index.search(vector, k)
    results = []
    for i, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        results.append({"ticket_id": int(idx), "score": float(distances[0][i])})
    return results, {"distances": distances.tolist(), "indices": indices.tolist()}

logger = logging.getLogger(__name__)


def search_tickets_by_keywords(keywords: List[str], max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Busca tickets por palabras clave usando SQL LIKE en Título y Descripción.
    
    Args:
        keywords: Lista de palabras clave a buscar
        max_results: Número máximo de resultados por keyword
    
    Returns:
        Lista de tickets encontrados (cada uno con IdTicket, Cliente, Titulo, Descripcion)
    """
    if not keywords:
        return []

    all_results = []
    seen_ids = set()

    for kw in keywords:
        words = kw.split()
        if not words:
            continue  # si está vacío, lo saltamos

        sanitized_words = [w.replace("'", "''") for w in words]
        like_titulo = " AND ".join([f"Titulo COLLATE Latin1_General_CI_AI LIKE '%{w}%'" for w in sanitized_words])
        like_desc = " AND ".join([f"Descripcion COLLATE Latin1_General_CI_AI LIKE '%{w}%'" for w in sanitized_words])
        like_clause = f"(({like_titulo}) OR ({like_desc}))"

        logger.debug(f"🔍 Ejecutando búsqueda LIKE para keyword '{kw}':\n{like_clause}")

        sql_query = f"""
            SELECT TOP {max_results}
                iError = 0,
                vError = '',
                vJsonType = 'Query',
                IdTicket,
                Cliente,
                Titulo,
                Descripcion
            FROM Tickets
            WHERE {like_clause}
            ORDER BY CONVERT(datetime, FechaCreado, 101) DESC
        """

        api_url = f"https://tickets.zell.mx/apilink/info?query={sql_query}"
        headers = {
            "x-api-key": os.getenv("ZELL_API_KEY"),
            "user": os.getenv("ZELL_USER"),
            "password": os.getenv("ZELL_PASSWORD"),
            "action": "7777"
        }

        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            results = response.json()

            for r in results:
                if not isinstance(r, dict):
                    logger.warning(f"[Keyword Search] salto resultado no dict: {r!r}")
                    continue
                ticket_id = r.get("IdTicket")
                if ticket_id and ticket_id not in seen_ids:
                    seen_ids.add(ticket_id)
                    all_results.append(r)

        except Exception as e:
            logger.error(f"❌ Error en búsqueda LIKE con keyword '{kw}': {e}")
            # Continuar con siguiente keyword si hay error
            continue

    return all_results


def search_tickets_semantic(
    query: str,
    conversation_id: str,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Busca tickets usando búsqueda semántica (FAISS).
    
    Args:
        query: Texto de búsqueda
        conversation_id: ID de conversación (para logging)
        top_k: Número de resultados a retornar
    
    Returns:
        Lista de resultados con formato:
        [
            {
                "ticket_id": 12345,
                "score": 0.85,  # Similitud [0.0, 1.0] donde mayor = mejor
                "method": "semantic"
            },
            ...
        ]
    """
    # Asegurar que FAISS esté cargado
    if not faiss_loaded:
        load_faiss_data()
    
    try:
        # Generar embedding de la query
        vec = generate_openai_embedding(query, conversation_id, interaction_id=None)
        if vec is None:
            logger.error("No se pudo generar embedding para búsqueda semántica")
            return []

        # Buscar en FAISS
        faiss_results, _dbg = perform_faiss_search(vec, k=top_k)
        if not faiss_results:
            return []

        # Convertir distancias a similitud (normalizado L2: distancia en [0, 2])
        # Distancia 0.0 (idéntico) → Similitud 1.0
        # Distancia 2.0 (opuesto) → Similitud 0.0
        results = []
        for r in faiss_results:
            distance = r.get("score", 2.0)  # score es una distancia de FAISS
            similarity = max(0.0, 1.0 - (float(distance) / 2.0))
            results.append({
                "ticket_id": r.get("ticket_id"),
                "score": similarity,  # Ahora es similitud (mayor = mejor)
                "method": "semantic"
            })

        return results

    except Exception as e:
        logger.error(f"❌ Error en búsqueda semántica: {e}")
        return []


def search_tickets_hybrid(
    query: str,
    conversation_id: str,
    top_k: int = 10,
    keyword_max_per_term: int = 3
) -> List[Dict[str, Any]]:
    """
    Busca tickets usando ambas estrategias (keywords + semántica) y combina resultados.
    
    Args:
        query: Texto de búsqueda
        conversation_id: ID de conversación (para logging)
        top_k: Número máximo de resultados finales
        keyword_max_per_term: Número máximo de resultados por keyword
    
    Returns:
        Lista de resultados combinados y deduplicados, ordenados por score descendente:
        [
            {
                "ticket_id": 12345,
                "score": 1.0,  # Mayor entre keyword (1.0) y semantic (0.0-1.0)
                "method": "keyword" o "semantic" o "both"
            },
            ...
        ]
    """
    # Asegurar que FAISS esté cargado
    if not faiss_loaded:
        load_faiss_data()
    
    all_hits = []

    # 1. Búsqueda por keywords
    words = [w.strip(".,:;!?()[]{}\"'").lower() for w in query.split()]
    words = [w for w in words if len(w) >= 4][:6] or [query]
    
    keyword_results = search_tickets_by_keywords(words, max_results=keyword_max_per_term)
    for r in keyword_results:
        tid = r.get("IdTicket") or r.get("ticket_id") or r.get("id")
        if tid is not None:
            all_hits.append({
                "ticket_id": tid,
                "score": 1.0,  # Score fijo para keywords
                "method": "keyword",
                "title": r.get("Titulo") or r.get("title") or "",
            })

    # 2. Búsqueda semántica
    semantic_results = search_tickets_semantic(query, conversation_id, top_k=top_k)
    for r in semantic_results:
        all_hits.append({
            "ticket_id": r.get("ticket_id"),
            "score": r.get("score", 0.0),  # Similitud [0.0, 1.0]
            "method": "semantic",
        })

    # 3. Deduplicar: si un ticket aparece en ambos, mantener el mayor score
    best: Dict[int, Dict[str, Any]] = {}
    for h in all_hits:
        tid = h.get("ticket_id")
        if tid is None:
            continue
        
        if tid not in best or float(h.get("score", 0)) > float(best[tid].get("score", 0)):
            # Si ya existía, marcar como "both"
            if tid in best and h.get("method") != best[tid].get("method"):
                h["method"] = "both"
            best[tid] = h

    # 4. Ordenar por score descendente y retornar top_k
    final_results = sorted(
        best.values(),
        key=lambda x: float(x.get("score", 0)),
        reverse=True
    )[:top_k]

    return final_results

