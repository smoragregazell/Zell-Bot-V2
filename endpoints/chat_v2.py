# endpoints/chat_v2.py
# V2 chat endpoint: Responses API + tool-calling loop + console tracing
# Notes:
# - Auth can be bypassed ONLY in local via env var SKIP_AUTH=1
# - TRACE_V2=1 prints a detailed trace of tool calls and outputs

import os
import json
import time
import inspect
import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple
from contextvars import ContextVar

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# --- Auth (optional skip in local) ---
from utils.token_verifier import verificar_token

# --- Tickets tools ---
from Tools.busquedacombinada_tool import (
    fetch_ticket_data,
    get_ticket_comments,
    search_tickets_by_keywords,
)

# --- Semantic (tickets FAISS) ---
from Tools.semantic_tool import (
    init_semantic_tool,
    generate_openai_embedding,
    perform_faiss_search,
)

# --- Docs RAG ---
from Tools.docs_tool import search_docs, get_doc_context

# --- Query tool (SQL queries) ---
from Tools.query_tool import (
    generate_sql_query,
    fetch_query_results,
)
from utils.contextManager.context_handler import get_interaction_id

# --- Logging V2 ---
from utils.logs_v2 import (
    log_chat_v2_interaction,
    log_token_usage,
    extract_token_usage,
    calculate_cost,
    set_trace_function,
)

router = APIRouter()

TRACE_V2 = os.getenv("TRACE_V2", "0") == "1"
SKIP_AUTH = os.getenv("SKIP_AUTH", "0") == "1"

# --- Conversational context storage ---
# Almacena el último response_id por conversation_id para mantener contexto
# Formato: {conversation_id: {"last_response_id": "resp_xxx", "updated_at": timestamp}}
_conversation_response_ids: Dict[str, Dict[str, Any]] = {}

# --- Web search tracking ---
# Almacena el conteo de búsquedas web por conversación
# Formato: {conversation_id: count}
_web_search_counts: Dict[str, int] = {}
MAX_WEB_SEARCHES_PER_CONV = 3  # Límite de búsquedas web por conversación


def tr(msg: str) -> None:
    if TRACE_V2:
        print(f"[V2-TRACE] {msg}", flush=True)


def get_last_response_id(conversation_id: str) -> Optional[str]:
    """Obtiene el último response_id guardado para esta conversación."""
    entry = _conversation_response_ids.get(conversation_id)
    if entry:
        return entry.get("last_response_id")
    return None


def save_last_response_id(conversation_id: str, response_id: str) -> None:
    """Guarda el último response_id para esta conversación."""
    _conversation_response_ids[conversation_id] = {
        "last_response_id": response_id,
        "updated_at": time.time(),
    }


def clear_conversation_context(conversation_id: str) -> None:
    """Limpia el contexto de una conversación (para empezar de nuevo)."""
    _conversation_response_ids.pop(conversation_id, None)
    _web_search_counts.pop(conversation_id, None)


def get_web_search_count(conversation_id: str) -> int:
    """Obtiene el número de búsquedas web realizadas en esta conversación."""
    return _web_search_counts.get(conversation_id, 0)


def increment_web_search_count(conversation_id: str) -> int:
    """Incrementa el contador de búsquedas web y retorna el nuevo valor."""
    current = _web_search_counts.get(conversation_id, 0)
    new_count = current + 1
    _web_search_counts[conversation_id] = new_count
    return new_count


def can_use_web_search(conversation_id: str) -> bool:
    """Verifica si se puede realizar una búsqueda web (no se ha alcanzado el límite)."""
    return get_web_search_count(conversation_id) < MAX_WEB_SEARCHES_PER_CONV


# Configurar función de trace para logs_v2
set_trace_function(tr)


# ============================================
# LIVE STEPS: StepEmitter con ContextVar
# ============================================

# ContextVar para el emitter actual (por request, thread-safe)
_step_emitter: ContextVar[Optional['StepEmitter']] = ContextVar('step_emitter', default=None)


class StepEmitter:
    """Emite eventos de progreso para live steps en el frontend"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.last_sent_time = 0.0
        self.last_message = ""
        self.throttle_ms = 0  # Sin throttle - mostrar TODOS los mensajes (para debug)
    
    async def emit_status(self, message: str):
        """Emite un mensaje de estado si pasa el throttle/dedupe"""
        now = time.time() * 1000  # milliseconds
        
        # Dedupe: si es EXACTAMENTE el mismo mensaje, ignorar
        # Pero permitir mensajes similares con IDs diferentes (ej: "Obteniendo ticket #123" vs "#456")
        if message == self.last_message:
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Mensaje duplicado filtrado: '{message}'", flush=True)
            return
        
        # Throttle: si pasó menos tiempo, ignorar (pero más permisivo)
        time_since_last = now - self.last_sent_time
        if time_since_last < self.throttle_ms:
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Mensaje throttled (esperando {self.throttle_ms - time_since_last:.1f}ms más): '{message}'", flush=True)
            return
        
        self.last_sent_time = now
        self.last_message = message
        
        if TRACE_V2:
            print(f"[V2-TRACE-DEBUG] Mensaje enviado a queue: '{message}'", flush=True)
        
        try:
            await self.queue.put({
                'type': 'status',
                'message': message,
                'timestamp': now
            })
        except Exception as e:
            # No bloquear si hay error (ej: queue cerrada)
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Error enviando a queue: {e}", flush=True)
            pass
    
    async def get_event(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """Obtiene un evento de la queue con timeout"""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    async def emit_response(self, response: str):
        """Emite la respuesta final"""
        try:
            await self.queue.put({
                'type': 'response',
                'content': response,
                'timestamp': time.time() * 1000
            })
        except Exception:
            pass
    
    async def emit_error(self, error: str):
        """Emite un error"""
        try:
            await self.queue.put({
                'type': 'error',
                'message': error,
                'timestamp': time.time() * 1000
            })
        except Exception:
            pass


# ============================================
# DETECCIÓN Y TRADUCCIÓN DE MENSAJES
# ============================================

def is_relevant_for_live_steps(msg: str) -> bool:
    """Detecta si un mensaje tr() es relevante para mostrar en live steps"""
    # Patrones más flexibles que capturan variaciones (con o sin puntos, etc.)
    relevant_patterns = [
        r"Buscando en documentación interna Zell",  # Con o sin "..."
        r"Explorando scope=.+ ejecutando estrategia=.+",
        r"Obteniendo top \d+ resultados para query",  # Con o sin ":"
        r"Buscando en tickets con palabras clave",  # Con o sin ":"
        r"Buscando en tickets con búsqueda semántica",  # Con o sin "..."
        r"Buscando en: .+",  # Debe tener ":"
        r"Obteniendo item .+ id=",  # Más flexible
        r"Obteniendo info clave del documento",  # Con o sin espacio al final
        r"Obteniendo datos del ticket #\d+",
        r"Query SQL generado",  # Con o sin ":"
        r"Ejecutando web_search para",  # Con o sin ":"
        r"Generando respuesta final para el usuario",  # Con o sin "..."
    ]
    
    for pattern in relevant_patterns:
        if re.search(pattern, msg, re.IGNORECASE):
            return True
    return False


def extract_live_step_message(msg: str) -> Optional[str]:
    """Extrae el mensaje amigable del mensaje técnico usando regex"""
    
    # Patrones con sus traducciones
    patterns = [
        # "Buscando en documentación interna Zell..."
        (r"Buscando en documentación interna Zell", 
         "Buscando en documentación interna Zell..."),
        
        # "Explorando scope={scope} ejecutando estrategia={policy}"
        (r"Explorando scope=(.+) ejecutando estrategia=(.+)", 
         lambda m: f"Explorando {m.group(1)} con estrategia {m.group(2)}..."),
        
        # "Obteniendo top {top_k} resultados para query: '{query[:120]}'"
        (r"Obteniendo top (\d+) resultados para query", 
         lambda m: f"Se encontraron {m.group(1)} resultados relevantes"),
        
        # "Buscando en tickets con palabras clave: {words}"
        (r"Buscando en tickets con palabras clave", 
         "Buscando en tickets con palabras clave..."),
        
        # "Buscando en tickets con búsqueda semántica..."
        (r"Buscando en tickets con búsqueda semántica", 
         "Buscando en tickets con búsqueda semántica..."),
        
        # "Buscando en: {universe}"
        (r"Buscando en: (.+)", 
         lambda m: f"Buscando en {m.group(1)}..."),
        
        # "Obteniendo item {item_type} id={item_id}"
        (r"Obteniendo item (.+?) id=(.+)", 
         lambda m: f"Obteniendo {m.group(1)} #{m.group(2)}..."),
        
        # "Obteniendo info clave del documento "
        (r"Obteniendo info clave del documento", 
         "Obteniendo información del documento..."),
        
        # "Obteniendo datos del ticket #{item_id}"
        (r"Obteniendo datos del ticket #(\d+)", 
         lambda m: f"Obteniendo datos del ticket #{m.group(1)}..."),
        
        # "Query SQL generado: {sql_query}"
        (r"Query SQL generado", 
         "Ejecutando consulta SQL..."),
        
        # "Ejecutando web_search para: {web_query[:100]}"
        (r"Ejecutando web_search para", 
         "Buscando información en la web..."),
        
        # "Generando respuesta final para el usuario..."
        (r"Generando respuesta final para el usuario", 
         "Generando respuesta final para el usuario..."),
    ]
    
    for pattern, translation in patterns:
        match = re.search(pattern, msg)
        if match:
            try:
                if callable(translation):
                    return translation(match)
                else:
                    return translation
            except Exception as e:
                # Si hay error en la traducción, loguear y continuar
                if TRACE_V2:
                    print(f"[V2-TRACE-DEBUG] Error traduciendo '{msg}' con patrón '{pattern}': {e}", flush=True)
                continue
    
    # Si no se encontró traducción, loguear para debug
    if TRACE_V2:
        print(f"[V2-TRACE-DEBUG] No se encontró traducción para mensaje relevante: {msg}", flush=True)
    return None


# ============================================
# tr() MEJORADO (con emisión de eventos)
# ============================================

def tr(msg: str) -> None:
    """Trace function mejorada: log normal + emisión de eventos live si aplica"""
    # Log normal (siempre funciona, no cambia nada)
    if TRACE_V2:
        print(f"[V2-TRACE] {msg}", flush=True)
    
    # Si es relevante para live steps Y hay emitter activo, emitirlo
    if is_relevant_for_live_steps(msg):
        emitter = _step_emitter.get()
        if emitter:
            friendly_msg = extract_live_step_message(msg)
            if friendly_msg:
                # Debug: loguear cuando se emite un mensaje
                if TRACE_V2:
                    print(f"[V2-TRACE-DEBUG] Emitiendo live step: '{friendly_msg}' (original: '{msg}')", flush=True)
                # Emitir sin bloquear (usar create_task si estamos en contexto async)
                try:
                    loop = asyncio.get_running_loop()
                    # Estamos en contexto async, usar create_task
                    asyncio.create_task(emitter.emit_status(friendly_msg))
                except RuntimeError:
                    # No hay event loop corriendo, crear uno nuevo (raro pero posible)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(emitter.emit_status(friendly_msg))
                        else:
                            loop.run_until_complete(emitter.emit_status(friendly_msg))
                    except:
                        # Si falla todo, ignorar (no es crítico)
                        pass
            else:
                # Debug: mensaje relevante pero sin traducción
                if TRACE_V2:
                    print(f"[V2-TRACE-DEBUG] Mensaje relevante pero sin traducción: {msg}", flush=True)
        else:
            # Debug: si el mensaje es relevante pero no hay emitter, loguear
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Mensaje relevante pero sin emitter: {msg}", flush=True)


# --- OpenAI client (usando ai_calls centralizado) ---
from utils.ai_calls import responses_create, get_openai_client

# Cliente para Responses API (mantener compatibilidad)
client = get_openai_client(tool=None)

# Load ticket FAISS once
try:
    init_semantic_tool()
    tr("FAISS inicializado correctamente")
except Exception as e:
    tr(f"Error al inicializar FAISS (continuará con búsqueda por palabras clave): {e}")


class ChatV2Request(BaseModel):
    conversation_id: str
    user_message: str
    zToken: str
    userName: str


# Load system instructions from file
def load_system_instructions() -> str:
    """Carga las instrucciones del sistema desde el archivo de texto."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    instructions_path = os.path.join(project_root, "Prompts", "V2", "system_instruccions.txt")
    
    try:
        with open(instructions_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        tr(f"WARNING: No se encontró {instructions_path}, usando instrucciones por defecto")
        return "Eres un asistente interno para Zell."
    except Exception as e:
        tr(f"ERROR al cargar instrucciones: {e}, usando instrucciones por defecto")
        return "Eres un asistente interno para Zell."

SYSTEM_INSTRUCTIONS = load_system_instructions()


TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_knowledge",
        "description": (
            "Busca en tickets/cotizaciones/docs por keyword, semántica o híbrido. "
            "Devuelve IDs y scores; luego usa get_item para detalle."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {
                    "type": "string",
                    "enum": ["tickets", "quotes", "docs", "all"],
                    "default": "all",
                },
                "policy": {
                    "type": "string",
                    "enum": ["auto", "keyword", "semantic", "hybrid"],
                    "default": "auto",
                },
                "universe": {
                    "type": "string",
                    "description": (
                        "Universo de documentos cuando scope=docs. "
                        "Opciones: "
                        "'docs_org' (PREDETERMINADO - documentos organizacionales: políticas, procedimientos, manuales ISO, guías, reglamentos, códigos de ética). "
                        "Este es el universo principal donde se buscará la mayoría de las veces. "
                        "'meetings_weekly' (minutas de reuniones semanales - PROBLEMAS Y SOLUCIONES). "
                        "Úsalo cuando el usuario pregunte sobre: problemas similares que otros han enfrentado, soluciones ya discutidas, "
                        "situaciones que el equipo ya vivió ('¿alguien ha tenido este problema?', 'experiencia similar', 'caso parecido', "
                        "'¿cómo se resolvió esto antes?', '¿esto ya pasó?'). "
                        "También para: reuniones específicas, temas tratados en juntas, asistentes, fechas de reuniones, decisiones o acuerdos. "
                        "DECISIÓN: Si la pregunta es sobre problema/solución/caso similar, busca PRIMERO en meetings_weekly. "
                        "Si no encuentras nada relevante, entonces busca en docs_org."
                    ),
                    "default": "docs_org",
                },
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_item",
        "description": (
            "Trae detalle de un item (ticket, quote, doc). "
            "Úsalo DIRECTAMENTE cuando el usuario pida un ticket específico por número/ID "
            "(ej: 'traeme el ticket 36816', 'ticket #12345', 'muéstrame el ticket 5000'). "
            "NO uses search_knowledge primero si el usuario especifica un número de ticket."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["ticket", "quote", "doc"]},
                "id": {"type": "string", "description": "ID del item. Para tickets, usa el número del ticket (ej: '36816', '12345')."},
                "include_comments": {"type": "boolean", "default": True},
                "universe": {
                    "type": "string",
                    "description": (
                        "Universo de documentos cuando type=doc. "
                        "Debe coincidir con el universo usado en search_knowledge para obtener el chunk_id. "
                        "Opciones: 'docs_org', 'meetings_weekly', u otros."
                    ),
                    "default": "docs_org",
                },
            },
            "required": ["type", "id"],
        },
    },
    {
        "type": "function",
        "name": "query_tickets",
        "description": (
            "Ejecuta consultas SQL sobre tickets para responder preguntas cuantitativas o de filtrado. "
            "Úsalo cuando el usuario pregunte: cuántos tickets, tickets abiertos/cerrados en un período, "
            "tickets por persona (Javier, Alfredo, etc.), tickets por cliente, tickets por estatus/categoría, "
            "tickets con filtros de fecha (diciembre, último mes, etc.), o cualquier pregunta que requiera "
            "contar, agregar o filtrar tickets con criterios específicos. "
            "Ejemplos: '¿Cuántos tickets se abrieron en diciembre por Javier?', "
            "'Tickets activos de Exitus', 'Tickets en estatus Desarrollo'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_question": {
                    "type": "string",
                    "description": "La pregunta del usuario sobre tickets que requiere una consulta SQL.",
                },
            },
            "required": ["user_question"],
        },
    },
    {
        "type": "web_search"  # Tool integrado de OpenAI para búsquedas web en tiempo real
    },
]


# --------------------------
# Tool implementations
# --------------------------

def _dedupe_hits(hits: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for h in hits:
        k = f"{h.get('type')}::{h.get('id')}"
        if k not in best or float(h.get("score", 0)) > float(best[k].get("score", 0)):
            best[k] = h
    return sorted(best.values(), key=lambda x: float(x.get("score", 0)), reverse=True)[:top_k]


def tool_search_knowledge(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    scope = args.get("scope", "all")
    policy = args.get("policy", "auto")
    top_k = int(args.get("top_k", 5))
    universe = (args.get("universe") or "docs_org").strip()

    if not query:
        return {"hits": [], "notes": ["query vacío"]}

    # Simple AUTO heuristic
    if policy == "auto":
        policy = "hybrid" if len(query.split()) <= 8 else "keyword"

    tr(f"Buscando en documentación interna Zell...")
    tr(f"Explorando scope={scope} ejecutando estrategia={policy}")
    tr(f"Obteniendo top {top_k} resultados para query: '{query[:120]}'")

    hits: List[Dict[str, Any]] = []
    notes: List[str] = []

    # ---- TICKETS ----
    if scope in ("tickets", "all"):
        # Keyword search (LIKE)
        if policy in ("keyword", "hybrid"):
            words = [w.strip(".,:;!?()[]{}\"'").lower() for w in query.split()]
            words = [w for w in words if len(w) >= 4][:6] or [query]
            tr(f"Buscando en tickets con palabras clave: {words}")
            try:
                like_results = search_tickets_by_keywords(words, max_results=top_k)
            except TypeError:
                like_results = search_tickets_by_keywords(words)

            count = len(like_results) if like_results else 0
            if count > 0:
                tr(f"Encontrados {count} tickets con búsqueda por palabras clave")
            else:
                tr(f"No se encontraron tickets con palabras clave")

            for r in like_results or []:
                tid = r.get("IdTicket") or r.get("ticket_id") or r.get("id")
                title = r.get("Titulo") or r.get("title") or r.get("titulo")
                if tid is not None:
                    hits.append(
                        {
                            "type": "ticket",
                            "id": str(tid),
                            "score": 1.0,
                            "method": "keyword",
                            "snippet": (title or "")[:220],
                            "metadata": {"title": title},
                        }
                    )

        # Semantic search (ticket FAISS)
        if policy in ("semantic", "hybrid"):
            tr(f"Buscando en tickets con búsqueda semántica...")
            try:
                vec = generate_openai_embedding(query, conversation_id, interaction_id=None)
                if vec is not None:
                    faiss_results, _dbg = perform_faiss_search(vec, k=top_k)
                    count = len(faiss_results) if faiss_results else 0
                    if count > 0:
                        tr(f"Encontrados {count} tickets con búsqueda semántica")
                    else:
                        tr(f"No se encontraron tickets con búsqueda semántica")

                    for r in faiss_results or []:
                        tid = r.get("ticket_id") or r.get("IdTicket") or r.get("id")
                        score = r.get("score", 0.0)
                        snippet = r.get("text") or r.get("snippet") or ""
                        hits.append(
                            {
                                "type": "ticket",
                                "id": str(tid),
                                "score": float(score),
                                "method": "semantic",
                                "snippet": str(snippet)[:260],
                                "metadata": {},
                            }
                        )
            except Exception as e:
                tr(f"Error en búsqueda semántica FAISS: {e}")

    # ---- QUOTES ---- (stub)
    if scope in ("quotes", "all"):
        notes.append("quotes: aún no implementado (stub)")

    # ---- DOCS ----
    if scope in ("docs", "all"):
        tr(f"Buscando en: {universe}")
        try:
            doc_res = search_docs(query=query, universe=universe, top_k=top_k)
            if doc_res.get("ok"):
                dhits = doc_res.get("hits", []) or []
                count = len(dhits)
                if count > 0:
                    tr(f"Encontrados {count} documentos en {universe}")
                else:
                    tr(f"No se encontraron documentos en {universe}")

                for h in dhits:
                    # Construir snippet según tipo de documento
                    snippet_parts = []
                    if h.get("title"):
                        snippet_parts.append(h.get("title"))
                    if h.get("section"):
                        snippet_parts.append(h.get("section"))
                    # Para meetings, agregar info adicional
                    if h.get("meeting_date"):
                        snippet_parts.append(f"Reunión: {h.get('meeting_date')}")
                    if h.get("row_key") and "#tema-" in str(h.get("row_key")):
                        tema_num = str(h.get("row_key")).split("#tema-")[-1]
                        snippet_parts.append(f"Tema #{tema_num}")
                    
                    snippet = " :: ".join(snippet_parts).strip()[:260]
                    
                    metadata = {
                        "doc_id": h.get("doc_id"),
                        "title": h.get("title"),
                        "section": h.get("section"),
                        "source_path": h.get("source_path"),
                        "universe": universe,
                        "codigo": h.get("codigo"),
                        "fecha_emision": h.get("fecha_emision"),
                        "revision": h.get("revision"),
                        "estatus": h.get("estatus"),
                    }
                    
                    # Metadata específica para meetings
                    if h.get("meeting_date"):
                        metadata["meeting_date"] = h.get("meeting_date")
                        metadata["meeting_start"] = h.get("meeting_start")
                        metadata["meeting_end"] = h.get("meeting_end")
                    if h.get("row_key"):
                        metadata["row_key"] = h.get("row_key")
                    if h.get("block_kind"):
                        metadata["block_kind"] = h.get("block_kind")
                    
                    hits.append(
                        {
                            "type": "doc",
                            "id": str(h.get("chunk_id")),  # id = chunk_id
                            "score": float(h.get("score", 0.0)),
                            "method": "docs_semantic",
                            "snippet": snippet or f'{h.get("title","")}'.strip()[:260],
                            "metadata": metadata,
                        }
                    )
            else:
                err = doc_res.get("error")
                tr(f"Error al buscar documentos: {err}")
                notes.append(f"docs: error={err}")
        except Exception as e:
            tr(f"Excepción al buscar documentos: {e}")
            notes.append(f"docs: exception={e}")

    final_hits = _dedupe_hits(hits, top_k=top_k)
    total_found = len(final_hits)
    if total_found > 0:
        tr(f"Total de resultados encontrados: {total_found}")
    else:
        tr(f"Sin resultados en ninguna fuente")
    return {"hits": final_hits, "notes": notes}


def tool_get_item(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    item_type = args.get("type")
    item_id = str(args.get("id"))
    include_comments = bool(args.get("include_comments", True))

    tr(f"Obteniendo item {item_type} id={item_id}")

    # ---- DOC ----
    if item_type == "doc":
        universe = (args.get("universe") or "docs_org").strip()
        tr(f"Obteniendo info clave del documento ")
        try:
            # item_id = chunk_id
            result = get_doc_context(universe=universe, chunk_ids=[item_id], max_chunks=6)
            if result.get("ok") and result.get("blocks"):
                blocks_count = len(result.get("blocks", []))
                title = result.get("blocks", [{}])[0].get("title", "N/A") if result.get("blocks") else "N/A"
                tr(f"Documento obtenido: {title} ({blocks_count} bloques)")
            return result
        except Exception as e:
            return {
                "ok": False,
                "error": f"get_doc_context_failed: {e}",
                "universe": universe,
                "chunk_id": item_id,
            }

    # ---- TICKET ----
    if item_type == "ticket":
        tr(f"Obteniendo datos del ticket #{item_id}")
        try:
            ticket_data = fetch_ticket_data(item_id)
            title = ticket_data.get("Titulo") or ticket_data.get("title") or "N/A"
            tr(f"Ticket obtenido: {title}")
        except Exception as e:
            tr(f"Error al obtener ticket: {e}")
            return {"error": f"fetch_ticket_data falló: {e}"}

        out: Dict[str, Any] = {"ticket_data": ticket_data}

        if include_comments:
            tr(f"Obteniendo comentarios del ticket...")
            try:
                out["ticket_comments"] = get_ticket_comments(item_id, conversation_id)
                comments_count = len(out.get("ticket_comments", []))
                tr(f"Comentarios obtenidos: {comments_count}")
            except Exception as e:
                tr(f"Error al obtener comentarios: {e}")
                out["ticket_comments_error"] = str(e)

        return out

    # ---- QUOTE (stub) ----
    if item_type == "quote":
        return {"error": "get_item quote aún no implementado"}

    return {"error": f"Tipo no soportado: {item_type}"}


async def tool_query_tickets(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    """
    Tool para ejecutar consultas SQL sobre tickets.
    Reutiliza las funciones de query_tool.py pero filtra a top 25 resultados.
    """
    user_question = (args.get("user_question") or "").strip()
    
    if not user_question:
        return {"error": "La pregunta no puede estar vacía."}
    
    tr(f"Generando consulta SQL para: {user_question[:100]}")
    
    try:
        # Obtener interaction_id para logging
        interaction_id = get_interaction_id(conversation_id)
        try:
            interaction_id = int(interaction_id) if interaction_id else None
        except (ValueError, TypeError):
            interaction_id = None
        
        # 1️⃣ Generar la consulta SQL
        sql_response = await generate_sql_query(user_question, conversation_id, interaction_id)
        if not isinstance(sql_response, dict):
            tr(f"Error: generate_sql_query retornó tipo inesperado: {type(sql_response)}")
            return {
                "error": "No se pudo generar la consulta SQL.",
                "details": f"generate_sql_query retornó: {type(sql_response).__name__}"
            }
        
        sql_query = sql_response.get("sql_query", "").strip()
        sql_description = sql_response.get("mensaje", "")
        
        tr(f"Query SQL generado: {sql_query}")
        if sql_description:
            tr(f"Descripción: {sql_description}")
        
        if not sql_query or sql_query.lower() == "no viable":
            return {
                "error": "No viable",
                "message": (
                    "No pude generar una consulta basada en tu pregunta. Puede deberse a que:\n"
                    "🔹 Falta información o la pregunta es ambigua.\n"
                    "🔹 Solicitas datos a los que no tengo acceso.\n"
                    "🔹 Los datos no existen en la base.\n"
                    "Intenta reformularla o agrega más detalle."
                ),
            }
        
        # 2️⃣ Ejecutar consulta en Zell
        tr(f"Ejecutando consulta en base de datos...")
        api_data, status_code, _, _ = fetch_query_results(sql_query)
        if api_data is None:
            tr(f"Error llamando API de Zell")
            return {"error": "Error llamando API de Zell."}
        
        if isinstance(api_data, list) and not api_data:
            tr(f"No se encontraron tickets con los criterios especificados")
            return {
                "ok": True,
                "response": "No hay resultados para esa consulta.",
                "sql_query": sql_query,
                "results_count": 0,
            }
        
        # 3️⃣ Filtrar a top 25 resultados
        if isinstance(api_data, list):
            filtered_data = api_data[:25]
            total_count = len(api_data)
            tr(f"Encontrados {total_count} tickets")
            if total_count > 25:
                tr(f"Mostrando top 25 de {total_count} resultados")
        else:
            filtered_data = api_data
            total_count = 1
        
        # 4️⃣ Retornar datos estructurados (el LLM de chat_v2 generará la respuesta final)
        return {
            "ok": True,
            "query_type": "sql",
            "sql_query": sql_query,
            "sql_description": sql_description,
            "user_question": user_question,
            "results": filtered_data,
            "results_count": len(filtered_data) if isinstance(filtered_data, list) else 1,
            "total_results": total_count,
            "note": f"Mostrando top 25 de {total_count} resultados" if total_count > 25 else None,
        }
        
    except Exception as e:
        tr(f"Error al ejecutar query_tickets: {e}")
        return {"error": f"Error ejecutando consulta: {str(e)}"}


TOOL_IMPL = {
    "search_knowledge": tool_search_knowledge,
    "get_item": tool_get_item,
    "query_tickets": tool_query_tickets,
}


# --------------------------
# Endpoint
# --------------------------

@router.post("/chat_v2")
async def chat_v2(req: ChatV2Request):
    # Variables para logging
    had_previous_context = False
    rounds_used = 0
    final_response_id: Optional[str] = None
    
    try:
        # Auth (skip in local only)
        if not SKIP_AUTH:
            verificar_token(req.zToken)
        else:
            tr("Autenticación omitida (SKIP_AUTH=1)")

        tr(f"Nueva solicitud - conv_id={req.conversation_id} usuario={req.userName}")
        tr(f"Usuario: {req.user_message}")

        # Obtener el último response_id de esta conversación para mantener contexto
        conversation_prev_id = get_last_response_id(req.conversation_id)
        had_previous_context = conversation_prev_id is not None
        if conversation_prev_id:
            tr(f"Continuando conversación previa (response_id: {conversation_prev_id})")
        else:
            tr("Nueva conversación (sin contexto previo)")

        # prev_id se inicializa con el de la conversación anterior (solo para el primer round)
        prev_id: Optional[str] = conversation_prev_id
        next_input: List[Dict[str, Any]] = [{"role": "user", "content": req.user_message}]

        # Tool-calling loop
        for round_idx in range(1, 7):
            tr(f"--- ROUND {round_idx} --- prev_id={prev_id}")
            tr(f"Iniciando round {round_idx}")
            tr(f"Enviando solicitud a OpenAI...")

            t0 = time.time()
            try:
                response = await responses_create(
                    model=os.getenv("V2_MODEL", "gpt-5-mini"),
                    instructions=SYSTEM_INSTRUCTIONS,
                    tools=TOOLS,
                    input=next_input,
                    previous_response_id=prev_id,
                )
            except Exception as api_error:
                # Si el error es por previous_response_id inválido/expirado, limpiar y reintentar sin él
                error_str = str(api_error).lower()
                if (prev_id and round_idx == 1 and 
                    ("not found" in error_str or "invalid" in error_str or "expired" in error_str)):
                    tr(f"response_id expirado/inválido: {api_error}, reintentando sin contexto previo")
                    clear_conversation_context(req.conversation_id)
                    prev_id = None
                    # Reintentar sin previous_response_id
                    response = await responses_create(
                        model=os.getenv("V2_MODEL", "gpt-5-mini"),
                        instructions=SYSTEM_INSTRUCTIONS,
                        tools=TOOLS,
                        input=next_input,
                        previous_response_id=None,
                    )
                else:
                    raise  # Re-lanzar si no es un error de previous_response_id
            
            tr(f"Respuesta recibida de OpenAI (took {time.time() - t0:.2f}s)")
            tr(f"OpenAI response.id={response.id}")
            
            # Extraer información de tokens y costos
            token_info = extract_token_usage(response)
            model_used = os.getenv("V2_MODEL", "gpt-5-mini")
            if token_info["total_tokens"] > 0:
                tr(f"Tokens: input={token_info['input_tokens']}, output={token_info['output_tokens']}, total={token_info['total_tokens']}")
                costs = calculate_cost(model_used, token_info["input_tokens"], token_info["output_tokens"])
                tr(f"Cost: ${costs['cost_total_usd']:.6f} (input: ${costs['cost_input_usd']:.6f}, output: ${costs['cost_output_usd']:.6f})")

            rounds_used = round_idx
            final_response_id = response.id

            # Final answer
            if getattr(response, "output_text", None):
                tr(f"Generando respuesta final para el usuario...")
                tr(f"Respuesta final generada ({len(response.output_text)} caracteres)")
                # Guardar el response_id final para mantener contexto en la siguiente interacción
                save_last_response_id(req.conversation_id, response.id)
                
                # Log de la interacción
                log_chat_v2_interaction(
                    userName=req.userName,
                    conversation_id=req.conversation_id,
                    user_message=req.user_message,
                    response=response.output_text,
                    response_id=response.id,
                    rounds_used=rounds_used,
                    had_previous_context=had_previous_context,
                    extra_info="Success"
                )
                
                return {"classification": "V2", "response": response.output_text}

            # Tool calls
            calls = [it for it in response.output if getattr(it, "type", None) == "function_call"]
            calls_count = len(calls)
            if calls_count > 0:
                tr(f"LLM solicitó {calls_count} tool(s)")
            else:
                tr("LLM no solicitó tools")

            if not calls:
                tr("Sin tools solicitados y sin respuesta - deteniendo ejecución")
                # Guardar el response_id incluso en caso de error
                save_last_response_id(req.conversation_id, response.id)
                
                error_response = "No hubo tool calls ni output_text (revisar tools/instructions)."
                
                # Log de la interacción con error
                log_chat_v2_interaction(
                    userName=req.userName,
                    conversation_id=req.conversation_id,
                    user_message=req.user_message,
                    response=error_response,
                    response_id=response.id,
                    rounds_used=rounds_used,
                    had_previous_context=had_previous_context,
                    extra_info="No tool calls or output_text"
                )
                
                return {
                    "classification": "V2",
                    "response": error_response,
                }

            tool_outputs: List[Dict[str, Any]] = []
            web_search_used_this_round = False
            tools_called_this_round: List[str] = []

            for i, item in enumerate(calls, start=1):
                name = getattr(item, "name", "")
                tool_type = getattr(item, "type", None)
                
                # Detectar si es web_search (tool integrado de OpenAI)
                # Los tools integrados pueden venir sin "name" pero con "type"
                is_web_search = (tool_type == "web_search" or name == "web_search")
                
                # Debug: loguear cuando detectamos web_search
                if is_web_search:
                    tr(f"[DEBUG] web_search detectado - tool_type={tool_type}, name={name}, arguments={getattr(item, 'arguments', 'N/A')}")
                
                # Validar límite de búsquedas web
                if is_web_search:
                    #tr(f"Ejecutando web_search")
                    
                    if not can_use_web_search(req.conversation_id):
                        current_count = get_web_search_count(req.conversation_id)
                        tr(f"Límite de búsquedas web alcanzado (count={current_count}/{MAX_WEB_SEARCHES_PER_CONV}) - BLOQUEADO")
                        result = {
                            "error": f"Límite de búsquedas web alcanzado. Se han realizado {current_count} búsquedas web en esta conversación (máximo: {MAX_WEB_SEARCHES_PER_CONV}).",
                            "limit_reached": True,
                            "current_count": current_count,
                            "max_allowed": MAX_WEB_SEARCHES_PER_CONV
                        }
                        tool_outputs.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(item, "call_id", ""),
                                "output": json.dumps(result, ensure_ascii=False),
                            }
                        )
                        # No marcar como usado si fue bloqueado
                        continue
                    else:
                        # Incrementar contador antes de procesar
                        new_count = increment_web_search_count(req.conversation_id)
                        web_search_used_this_round = True
                        tools_called_this_round.append("web_search")
                        
                        # Intentar extraer la query del contexto si está disponible
                        web_query = ""
                        try:
                            # La query puede estar en los argumentos o en el contexto previo
                            if hasattr(item, "arguments") and item.arguments:
                                args_dict = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                                web_query = args_dict.get("query", "") or args_dict.get("search_query", "")
                        except:
                            pass
                        
                        # Siempre mostrar mensaje cuando se ejecuta web_search
                        # IMPORTANTE: Este mensaje se emite INMEDIATAMENTE cuando detectamos que OpenAI va a usar web_search
                        # OpenAI ejecutará web_search internamente después, pero nosotros ya mostramos el mensaje aquí
                        if web_query:
                            tr(f"Ejecutando web_search para: {web_query[:100]}")
                        else:
                            # Si no podemos extraer la query, intentar obtenerla del mensaje del usuario o usar un mensaje genérico
                            tr(f"Ejecutando web_search para: [query procesada por OpenAI]")
                        
                        tr(f"Búsqueda web permitida (count={new_count}/{MAX_WEB_SEARCHES_PER_CONV}) - OpenAI ejecutará la búsqueda internamente")
                        continue  # web_search es manejado por OpenAI, no necesitamos procesarlo
                
                try:
                    args = json.loads(getattr(item, "arguments", "") or "{}")
                except Exception:
                    args = {"_raw_arguments": getattr(item, "arguments", "")}

                tool_name_display = name or tool_type or "unknown"
                
                if not is_web_search:
                    tr(f"Ejecutando tool: {tool_name_display}...")
                    tools_called_this_round.append(tool_name_display)

                # web_search es un tool integrado de OpenAI
                # OpenAI lo ejecuta automáticamente cuando está en la lista de tools
                # No necesitamos implementación custom, solo tracking del límite
                if is_web_search:
                    # Ya validamos el límite arriba y incrementamos el contador si está permitido
                    # OpenAI procesará web_search automáticamente y los resultados aparecerán en el siguiente round
                    # No agregamos output manual, OpenAI maneja tools integrados automáticamente
                    continue

                fn = TOOL_IMPL.get(name)
                t1 = time.time()
                if fn:
                    # Manejar funciones async y síncronas
                    if inspect.iscoroutinefunction(fn):
                        result = await fn(args, req.conversation_id)
                    else:
                        result = fn(args, req.conversation_id)
                else:
                    tr(f"Tool {name} no implementada")
                    result = {"error": f"Tool no implementada: {name}"}
                dt = time.time() - t1

                # Summary mejorado en español
                summary_parts = []
                if isinstance(result, dict):
                    if "hits" in result and isinstance(result["hits"], list):
                        count = len(result["hits"])
                        summary_parts.append(f"Encontrados {count} resultados")
                    elif "ticket_data" in result:
                        summary_parts.append("Ticket obtenido exitosamente")
                        if "ticket_comments" in result:
                            comments_count = len(result.get("ticket_comments", []))
                            summary_parts.append(f"({comments_count} comentarios)")
                    elif "blocks" in result:
                        blocks_count = len(result.get("blocks", []))
                        summary_parts.append(f"Documento obtenido ({blocks_count} bloques)")
                    elif "query_type" in result and result.get("query_type") == "sql":
                        results_count = result.get("results_count", 0)
                        total_results = result.get("total_results", 0)
                        summary_parts.append(f"Consulta ejecutada: {results_count} resultados")
                        if total_results > results_count:
                            summary_parts.append(f"(de {total_results} total)")
                    elif "error" in result:
                        error_msg = str(result.get("error", ""))[:50]
                        summary_parts.append(f"Error: {error_msg}")
                
                summary = " | ".join(summary_parts) if summary_parts else "Completado"
                tr(f"Tool completado en {dt:.2f}s: {summary}")

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(item, "call_id", ""),
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            # Log token usage para este round
            if token_info["total_tokens"] > 0:
                log_token_usage(
                    conversation_id=req.conversation_id,
                    response_id=response.id,
                    round_num=round_idx,
                    model=model_used,
                    input_tokens=token_info["input_tokens"],
                    output_tokens=token_info["output_tokens"],
                    total_tokens=token_info["total_tokens"],
                    web_search_used=web_search_used_this_round,
                    tools_called=tools_called_this_round
                )
            
            prev_id = response.id
            next_input = tool_outputs

        tr("Límite de rounds alcanzado (máximo 6)")
        # Guardar el último response_id incluso si se alcanzó el límite
        if final_response_id:
            save_last_response_id(req.conversation_id, final_response_id)
        
        error_response = "Se alcanzó límite de pasos internos (tool loop)."
        
        # Log de la interacción con límite alcanzado
        log_chat_v2_interaction(
            userName=req.userName,
            conversation_id=req.conversation_id,
            user_message=req.user_message,
            response=error_response,
            response_id=final_response_id or "",
            rounds_used=rounds_used,
            had_previous_context=had_previous_context,
            extra_info="Max rounds reached"
        )
        
        return {"classification": "V2", "response": error_response}

    except Exception as e:
        # Si el error es por response_id expirado, limpiar y reintentar (opcional)
        error_str = str(e).lower()
        if "not found" in error_str or "invalid" in error_str or "expired" in error_str:
            tr(f"Posible error de response_id expirado: {e}, limpiando contexto")
            clear_conversation_context(req.conversation_id)
        
        # Log del error
        try:
            log_chat_v2_interaction(
                userName=req.userName,
                conversation_id=req.conversation_id,
                user_message=req.user_message,
                response=f"Error: {str(e)}",
                response_id=final_response_id or "",
                rounds_used=rounds_used,
                had_previous_context=had_previous_context,
                extra_info=f"Exception: {type(e).__name__}"
            )
        except:
            pass  # No fallar si el logging falla
        
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


# ============================================
# HELPER: Procesar chat_v2 y retornar resultado
# ============================================

async def process_chat_v2_core(req: ChatV2Request) -> Dict[str, Any]:
    """
    Lógica central de chat_v2 que puede ser reutilizada.
    Retorna dict con 'response' y 'response_id' en lugar de JSONResponse.
    """
    # Variables para logging
    had_previous_context = False
    rounds_used = 0
    final_response_id: Optional[str] = None
    
    try:
        # Auth (skip in local only)
        if not SKIP_AUTH:
            verificar_token(req.zToken)
        else:
            tr("Autenticación omitida (SKIP_AUTH=1)")

        tr(f"Nueva solicitud - conv_id={req.conversation_id} usuario={req.userName}")
        tr(f"Usuario: {req.user_message}")

        # Obtener el último response_id de esta conversación para mantener contexto
        conversation_prev_id = get_last_response_id(req.conversation_id)
        had_previous_context = conversation_prev_id is not None
        if conversation_prev_id:
            tr(f"Continuando conversación previa (response_id: {conversation_prev_id})")
        else:
            tr("Nueva conversación (sin contexto previo)")

        # prev_id se inicializa con el de la conversación anterior (solo para el primer round)
        prev_id: Optional[str] = conversation_prev_id
        next_input: List[Dict[str, Any]] = [{"role": "user", "content": req.user_message}]

        # Tool-calling loop
        for round_idx in range(1, 7):
            tr(f"--- ROUND {round_idx} --- prev_id={prev_id}")
            tr(f"Iniciando round {round_idx}")
            tr(f"Enviando solicitud a OpenAI...")

            t0 = time.time()
            try:
                response = await responses_create(
                    model=os.getenv("V2_MODEL", "gpt-5-mini"),
                    instructions=SYSTEM_INSTRUCTIONS,
                    tools=TOOLS,
                    input=next_input,
                    previous_response_id=prev_id,
                )
            except Exception as api_error:
                error_str = str(api_error).lower()
                if (prev_id and round_idx == 1 and 
                    ("not found" in error_str or "invalid" in error_str or "expired" in error_str)):
                    tr(f"response_id expirado/inválido: {api_error}, reintentando sin contexto previo")
                    clear_conversation_context(req.conversation_id)
                    prev_id = None
                    response = await responses_create(
                        model=os.getenv("V2_MODEL", "gpt-5-mini"),
                        instructions=SYSTEM_INSTRUCTIONS,
                        tools=TOOLS,
                        input=next_input,
                        previous_response_id=None,
                    )
                else:
                    raise
            
            tr(f"Respuesta recibida de OpenAI (took {time.time() - t0:.2f}s)")
            tr(f"OpenAI response.id={response.id}")
            
            # Extraer información de tokens y costos
            token_info = extract_token_usage(response)
            model_used = os.getenv("V2_MODEL", "gpt-5-mini")
            if token_info["total_tokens"] > 0:
                tr(f"Tokens: input={token_info['input_tokens']}, output={token_info['output_tokens']}, total={token_info['total_tokens']}")
                costs = calculate_cost(model_used, token_info["input_tokens"], token_info["output_tokens"])
                tr(f"Cost: ${costs['cost_total_usd']:.6f}")

            rounds_used = round_idx
            final_response_id = response.id

            # Final answer
            if getattr(response, "output_text", None):
                tr(f"Generando respuesta final para el usuario...")
                tr(f"Respuesta final generada ({len(response.output_text)} caracteres)")
                save_last_response_id(req.conversation_id, response.id)
                
                # Emitir respuesta final al emitter si existe (para SSE)
                emitter = _step_emitter.get()
                if emitter:
                    await emitter.emit_response(response.output_text)
                
                log_chat_v2_interaction(
                    userName=req.userName,
                    conversation_id=req.conversation_id,
                    user_message=req.user_message,
                    response=response.output_text,
                    response_id=response.id,
                    rounds_used=rounds_used,
                    had_previous_context=had_previous_context,
                    extra_info="Success"
                )
                
                return {"response": response.output_text, "response_id": response.id}

            # Tool calls
            calls = [it for it in response.output if getattr(it, "type", None) == "function_call"]
            tr(f"tool_calls={len(calls)}")

            if not calls:
                tr("Sin tools solicitados y sin respuesta - deteniendo ejecución")
                save_last_response_id(req.conversation_id, response.id)
                
                error_response = "No hubo tool calls ni output_text (revisar tools/instructions)."
                
                log_chat_v2_interaction(
                    userName=req.userName,
                    conversation_id=req.conversation_id,
                    user_message=req.user_message,
                    response=error_response,
                    response_id=response.id,
                    rounds_used=rounds_used,
                    had_previous_context=had_previous_context,
                    extra_info="No tool calls or output_text"
                )
                
                return {"response": error_response, "response_id": response.id}

            tool_outputs: List[Dict[str, Any]] = []
            web_search_used_this_round = False
            tools_called_this_round: List[str] = []

            for i, item in enumerate(calls, start=1):
                name = getattr(item, "name", "")
                tool_type = getattr(item, "type", None)
                try:
                    args = json.loads(getattr(item, "arguments", "") or "{}")
                except Exception:
                    args = {"_raw_arguments": getattr(item, "arguments", "")}

                tr(f"CALL {i}: {name} args={args}")

                # Manejar web_search (tool integrado de OpenAI)
                if tool_type == "web_search" or name == "web_search":
                    # Debug: loguear cuando detectamos web_search
                    tr(f"[DEBUG] web_search detectado en process_chat_v2_core - tool_type={tool_type}, name={name}")
                    
                    web_search_used_this_round = True
                    tools_called_this_round.append("web_search")
                    
                    # Intentar extraer la query si está disponible
                    web_query = ""
                    try:
                        if hasattr(item, "arguments") and item.arguments:
                            args_dict = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                            web_query = args_dict.get("query", "") or args_dict.get("search_query", "")
                    except:
                        pass
                    
                    # Siempre mostrar mensaje cuando se ejecuta web_search
                    # IMPORTANTE: Este mensaje se emite INMEDIATAMENTE cuando detectamos que OpenAI va a usar web_search
                    if web_query:
                        tr(f"Ejecutando web_search para: {web_query[:100]}")
                    else:
                        tr(f"Ejecutando web_search para: [query procesada por OpenAI]")
                    
                    tr(f"[DEBUG] web_search mensaje emitido - OpenAI ejecutará la búsqueda internamente")
                    # OpenAI maneja web_search automáticamente
                    continue

                fn = TOOL_IMPL.get(name)
                t1 = time.time()
                if fn:
                    if inspect.iscoroutinefunction(fn):
                        result = await fn(args, req.conversation_id)
                    else:
                        result = fn(args, req.conversation_id)
                else:
                    tr(f"Tool {name} no implementada")
                    result = {"error": f"Tool no implementada: {name}"}
                dt = time.time() - t1

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(item, "call_id", ""),
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            if token_info["total_tokens"] > 0:
                log_token_usage(
                    conversation_id=req.conversation_id,
                    response_id=response.id,
                    round_num=round_idx,
                    model=model_used,
                    input_tokens=token_info["input_tokens"],
                    output_tokens=token_info["output_tokens"],
                    total_tokens=token_info["total_tokens"],
                    web_search_used=web_search_used_this_round,
                    tools_called=tools_called_this_round
                )
            
            prev_id = response.id
            next_input = tool_outputs

        tr("Límite de rounds alcanzado (máximo 6)")
        if final_response_id:
            save_last_response_id(req.conversation_id, final_response_id)
        
        error_response = "Se alcanzó límite de pasos internos (tool loop)."
        
        log_chat_v2_interaction(
            userName=req.userName,
            conversation_id=req.conversation_id,
            user_message=req.user_message,
            response=error_response,
            response_id=final_response_id or "",
            rounds_used=rounds_used,
            had_previous_context=had_previous_context,
            extra_info="Max rounds reached"
        )
        
        return {"response": error_response, "response_id": final_response_id or ""}

    except Exception as e:
        error_str = str(e).lower()
        if "not found" in error_str or "invalid" in error_str or "expired" in error_str:
            tr(f"Posible error de response_id expirado: {e}, limpiando contexto")
            clear_conversation_context(req.conversation_id)
        
        error_response = f"Error: {str(e)}"
        try:
            log_chat_v2_interaction(
                userName=req.userName,
                conversation_id=req.conversation_id,
                user_message=req.user_message,
                response=error_response,
                response_id="",
                rounds_used=0,
                had_previous_context=had_previous_context if 'had_previous_context' in locals() else False,
                extra_info=f"Exception: {type(e).__name__}"
            )
        except:
            pass
        
        return {"response": error_response, "response_id": ""}


# ============================================
# ENDPOINT SSE: /chat_v2/stream
# ============================================

@router.post("/chat_v2/stream")
async def chat_v2_stream(req: ChatV2Request):
    """Endpoint SSE que muestra live steps mientras procesa la solicitud"""
    
    async def event_generator():
        # Crear emitter para este request
        emitter = StepEmitter()
        _step_emitter.set(emitter)  # Guardar en contexto
        
        try:
            # Ejecutar el pipeline en un task
            task = asyncio.create_task(process_chat_v2_core(req))
            
            # Enviar eventos mientras procesa
            last_event_time = time.time()
            keep_alive_interval = 8.0  # Enviar keep-alive cada 8 segundos
            response_sent = False
            
            while not task.done() or not response_sent:
                # Obtener evento del emitter
                event = await emitter.get_event(timeout=0.1)
                if event:
                    last_event_time = time.time()
                    if event['type'] == 'status':
                        yield f"data: {json.dumps({'type': 'status', 'message': event['message']}, ensure_ascii=False)}\n\n"
                    elif event['type'] == 'response':
                        yield f"data: {json.dumps({'type': 'response', 'content': event['content']}, ensure_ascii=False)}\n\n"
                        response_sent = True
                        break
                    elif event['type'] == 'error':
                        yield f"data: {json.dumps({'type': 'error', 'message': event['message']}, ensure_ascii=False)}\n\n"
                        response_sent = True
                        break
                else:
                    # Si el task terminó pero no recibimos respuesta por eventos, obtener resultado directo
                    if task.done() and not response_sent:
                        try:
                            result = await task
                            if result and result.get('response'):
                                yield f"data: {json.dumps({'type': 'response', 'content': result['response']}, ensure_ascii=False)}\n\n"
                                response_sent = True
                                break
                        except Exception as e:
                            yield f"data: {json.dumps({'type': 'error', 'message': f'Error: {str(e)}'}, ensure_ascii=False)}\n\n"
                            response_sent = True
                            break
                    
                    # Keep-alive: si pasan 8+ segundos sin eventos, enviar mensaje neutral
                    if time.time() - last_event_time > keep_alive_interval:
                        # Keep-alive sin mensaje visible (solo para mantener conexión)
                        yield f": keep-alive\n\n"
                        last_event_time = time.time()
            
            # Asegurar que el task termine
            if not task.done():
                await task
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error: {str(e)}'}, ensure_ascii=False)}\n\n"
        finally:
            _step_emitter.set(None)  # Limpiar contexto
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat_v2/clear_context")
async def clear_chat_context(req: ChatV2Request):
    """Endpoint opcional para limpiar el contexto de una conversación y empezar de nuevo."""
    try:
        if not SKIP_AUTH:
            verificar_token(req.zToken)
        
        clear_conversation_context(req.conversation_id)
        return {
            "ok": True,
            "message": f"Contexto limpiado para conversation_id={req.conversation_id}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al limpiar contexto: {e}")
