"""
Buscar cotizaciones - Búsqueda semántica de cotizaciones del sistema ZELL.
Similar a search_etiquetas.py pero específico para cotizaciones (quotes).
"""
import os
import json
from typing import List, Dict, Any, Tuple

import numpy as np
import faiss

from Tools.search_tickets import generate_openai_embedding


def _normalize(v: np.ndarray) -> np.ndarray:
    """Normaliza un vector a norma unitaria."""
    n = np.linalg.norm(v)
    if n == 0:
        return v
    return v / n


def _load_meta(meta_path: str) -> List[Dict[str, Any]]:
    """Carga metadata de cotizaciones desde archivo JSONL."""
    rows = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_index_and_meta(universe: str = "quotes", data_dir: str = "Data") -> Tuple[Any, List[Dict[str, Any]]]:
    """
    Carga el índice FAISS y la metadata para cotizaciones.
    
    Args:
        universe: Nombre del universo (default: "quotes")
        data_dir: Directorio donde están los archivos de índice y metadata
    
    Returns:
        Tupla (index, meta) donde index es el índice FAISS y meta es la lista de metadata
    """
    idx_path = os.path.join(data_dir, f"{universe}.index")
    meta_path = os.path.join(data_dir, f"{universe}_meta.jsonl")

    if not os.path.exists(idx_path):
        raise FileNotFoundError(f"No existe index: {idx_path}")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"No existe meta: {meta_path}")

    index = faiss.read_index(idx_path)
    meta = _load_meta(meta_path)
    return index, meta


def search_quotes(query: str, top_k: int = 5, universe: str = "quotes", similarity_threshold: float = 0.80) -> Dict[str, Any]:
    """
    Busca cotizaciones relevantes usando búsqueda semántica (FAISS).
    
    Args:
        query: Texto de búsqueda (ej: "reporte de créditos", "buscador de agendas", etc.)
        top_k: Número máximo de resultados a buscar (default: 5, recomendado: 3-10)
        universe: Nombre del universo (default: "quotes")
        similarity_threshold: Umbral mínimo de similitud (default: 0.80)
                              Score >= 0.85: muy relevante
                              Score 0.80-0.85: relevante
                              Score < 0.80: filtrar (menos relevante)
    
    Returns:
        Dict con formato:
        {
            "ok": True/False,
            "universe": str,
            "query": str,
            "hits": [
                {
                    "rank": int,
                    "score": float,  # Score de similitud (más alto = más similar, rango 0-1)
                    "i_issue_id": int,   # Número de ticket
                    "i_quote_id": int,   # ID de cotización
                    "v_title": str,      # Título de la cotización
                    "i_units": float,    # Unidades
                    "f_payment_date": str,  # Fecha de pago (puede ser null)
                    "descriptions": str,    # Descripciones (puede ser null)
                },
                ...
            ]
        }
    """
    try:
        index, meta = _load_index_and_meta(universe)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}

    emb = generate_openai_embedding(query, conversation_id=f"quotes_search:{universe}", interaction_id=None)
    if emb is None:
        return {"ok": False, "error": "embedding_failed"}

    q = _normalize(np.array(emb, dtype=np.float32)).reshape(1, -1)
    # Buscar más resultados inicialmente para luego filtrar por umbral
    search_k = min(top_k * 2, 20)  # Buscar hasta 20 para tener opciones después del filtro
    scores, ids = index.search(q, search_k)

    hits = []
    for rank, i in enumerate(ids[0].tolist()):
        if i < 0 or i >= len(meta):
            continue
        
        score = float(scores[0][rank])
        
        # Filtrar por umbral de similitud (solo retornar resultados relevantes)
        if score < similarity_threshold:
            continue
        
        # Limitar a top_k resultados después del filtro
        if len(hits) >= top_k:
            break
        
        m = meta[i]
        
        hits.append({
            "rank": len(hits) + 1,
            "score": score,
            "i_issue_id": m.get("i_issue_id"),
            "i_quote_id": m.get("i_quote_id"),
            "v_title": m.get("v_title"),
            "i_units": m.get("i_units"),
            "f_payment_date": m.get("f_payment_date"),
            "descriptions": m.get("descriptions"),
        })

    return {"ok": True, "universe": universe, "query": query, "hits": hits}

