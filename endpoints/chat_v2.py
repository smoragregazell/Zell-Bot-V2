# endpoints/chat_v2.py
# V2 chat endpoint: Responses API + tool-calling loop + console tracing
# Notes:
# - Auth can be bypassed ONLY in local via env var SKIP_AUTH=1
# - TRACE_V2=1 prints a detailed trace of tool calls and outputs

import os
import json
import time
import csv
import inspect
from typing import Any, Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
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

router = APIRouter()

TRACE_V2 = os.getenv("TRACE_V2", "0") == "1"
SKIP_AUTH = os.getenv("SKIP_AUTH", "0") == "1"

# --- Conversational context storage ---
# Almacena el último response_id por conversation_id para mantener contexto
# Formato: {conversation_id: {"last_response_id": "resp_xxx", "updated_at": timestamp}}
_conversation_response_ids: Dict[str, Dict[str, Any]] = {}


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
    tr(f"Saved last_response_id={response_id} for conv_id={conversation_id}")


def clear_conversation_context(conversation_id: str) -> None:
    """Limpia el contexto de una conversación (para empezar de nuevo)."""
    _conversation_response_ids.pop(conversation_id, None)
    tr(f"Cleared context for conv_id={conversation_id}")


# --- Logging simple a CSV ---
CHAT_V2_LOG_FILE = os.path.join("logs", "chat_v2_interactions.csv")


def ensure_log_file_exists():
    """Asegura que el archivo de log existe con headers."""
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(CHAT_V2_LOG_FILE) or os.path.getsize(CHAT_V2_LOG_FILE) == 0:
        with open(CHAT_V2_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "userName",
                "conversation_id",
                "user_message",
                "response",
                "response_id",
                "rounds_used",
                "had_previous_context",
                "extra_info"
            ])


def log_chat_v2_interaction(
    userName: str,
    conversation_id: str,
    user_message: str,
    response: str,
    response_id: Optional[str] = None,
    rounds_used: int = 0,
    had_previous_context: bool = False,
    extra_info: str = ""
):
    """Log simple de interacciones de chat_v2 a CSV."""
    try:
        ensure_log_file_exists()
        timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
        
        # Usar modo append con manejo de errores más robusto
        try:
            with open(CHAT_V2_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    userName or "N/A",
                    conversation_id or "",  # Asegurar que no sea None
                    user_message[:500] if len(user_message) > 500 else user_message,  # Limitar tamaño
                    response[:1000] if len(response) > 1000 else response,  # Limitar tamaño
                    response_id or "",
                    rounds_used,
                    "Yes" if had_previous_context else "No",
                    extra_info
                ])
                f.flush()  # Forzar escritura inmediata
            tr(f"Logged interaction to {CHAT_V2_LOG_FILE}")
        except PermissionError as pe:
            tr(f"Permission denied writing to CSV (file may be open): {pe}")
        except IOError as ioe:
            tr(f"IO error writing to CSV: {ioe}")
    except Exception as e:
        tr(f"Error logging to CSV: {e}")
        import traceback
        tr(f"Traceback: {traceback.format_exc()}")


# --- OpenAI client (usando ai_calls centralizado) ---
from utils.ai_calls import responses_create, get_openai_client

# Cliente para Responses API (mantener compatibilidad)
client = get_openai_client(tool=None)

# Load ticket FAISS once
try:
    init_semantic_tool()
    tr("FAISS initialized OK")
except Exception as e:
    tr(f"FAISS init failed (will still run keyword search): {e}")


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
                        "Opciones: 'policies_iso' (políticas/procedimientos ISO), "
                        "'meetings_weekly' (minutas de reuniones semanales con temas tratados, asistentes, fechas), "
                        "u otros universos disponibles. "
                        "Usa 'meetings_weekly' cuando el usuario pregunte sobre reuniones, temas tratados en juntas, asistentes a reuniones, o decisiones de reuniones."
                    ),
                    "default": "policies_iso",
                },
                "top_k": {"type": "integer", "default": 8},
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
                        "Opciones: 'policies_iso', 'meetings_weekly', u otros."
                    ),
                    "default": "policies_iso",
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
    top_k = int(args.get("top_k", 8))
    universe = (args.get("universe") or "policies_iso").strip()

    if not query:
        return {"hits": [], "notes": ["query vacío"]}

    # Simple AUTO heuristic
    if policy == "auto":
        policy = "hybrid" if len(query.split()) <= 8 else "keyword"

    tr(f"search_knowledge policy={policy} scope={scope} top_k={top_k} universe={universe} query='{query[:120]}'")

    hits: List[Dict[str, Any]] = []
    notes: List[str] = []

    # ---- TICKETS ----
    if scope in ("tickets", "all"):
        # Keyword search (LIKE)
        if policy in ("keyword", "hybrid"):
            words = [w.strip(".,:;!?()[]{}\"'").lower() for w in query.split()]
            words = [w for w in words if len(w) >= 4][:6] or [query]
            try:
                like_results = search_tickets_by_keywords(words, max_results=top_k)
            except TypeError:
                like_results = search_tickets_by_keywords(words)

            tr(f"LIKE keywords={words} hits={len(like_results) if like_results else 0}")

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
            try:
                vec = generate_openai_embedding(query, conversation_id, interaction_id=None)
                if vec is not None:
                    faiss_results, _dbg = perform_faiss_search(vec, k=top_k)
                    tr(f"FAISS hits={len(faiss_results) if faiss_results else 0}")

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
                tr(f"FAISS search failed: {e}")

    # ---- QUOTES ---- (stub)
    if scope in ("quotes", "all"):
        notes.append("quotes: aún no implementado (stub)")

    # ---- DOCS ----
    if scope in ("docs", "all"):
        try:
            doc_res = search_docs(query=query, universe=universe, top_k=top_k)
            if doc_res.get("ok"):
                dhits = doc_res.get("hits", []) or []
                tr(f"DOCS hits={len(dhits)} universe={universe}")

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
                tr(f"DOCS search failed: {err}")
                notes.append(f"docs: error={err}")
        except Exception as e:
            tr(f"DOCS search exception: {e}")
            notes.append(f"docs: exception={e}")

    final_hits = _dedupe_hits(hits, top_k=top_k)
    return {"hits": final_hits, "notes": notes}


def tool_get_item(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    item_type = args.get("type")
    item_id = str(args.get("id"))
    include_comments = bool(args.get("include_comments", True))

    tr(f"get_item type={item_type} id={item_id} include_comments={include_comments}")

    # ---- DOC ----
    if item_type == "doc":
        universe = (args.get("universe") or "policies_iso").strip()
        try:
            # item_id = chunk_id
            return get_doc_context(universe=universe, chunk_ids=[item_id], max_chunks=6)
        except Exception as e:
            return {
                "ok": False,
                "error": f"get_doc_context_failed: {e}",
                "universe": universe,
                "chunk_id": item_id,
            }

    # ---- TICKET ----
    if item_type == "ticket":
        try:
            ticket_data = fetch_ticket_data(item_id)
        except Exception as e:
            return {"error": f"fetch_ticket_data falló: {e}"}

        out: Dict[str, Any] = {"ticket_data": ticket_data}

        if include_comments:
            try:
                out["ticket_comments"] = get_ticket_comments(item_id, conversation_id)
            except Exception as e:
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
    
    tr(f"query_tickets question='{user_question[:120]}'")
    
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
            tr(f"generate_sql_query returned: {type(sql_response)} = {sql_response}")
            return {
                "error": "No se pudo generar la consulta SQL.",
                "details": f"generate_sql_query retornó: {type(sql_response).__name__}"
            }
        
        sql_query = sql_response.get("sql_query", "").strip()
        sql_description = sql_response.get("mensaje", "")
        
        tr(f"📊 SQL Query Generated: {sql_query}")
        tr(f"📝 SQL Description: {sql_description}")
        
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
        api_data, status_code, _, _ = fetch_query_results(sql_query)
        if api_data is None:
            return {"error": "Error llamando API de Zell."}
        
        if isinstance(api_data, list) and not api_data:
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
            tr(f"query_tickets: {total_count} total results, filtering to top 25")
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
        tr(f"query_tickets exception: {e}")
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
            tr("AUTH skipped (SKIP_AUTH=1)")

        tr(f"NEW REQUEST conv_id={req.conversation_id} user={req.userName}")
        tr(f"USER: {req.user_message}")

        # Obtener el último response_id de esta conversación para mantener contexto
        conversation_prev_id = get_last_response_id(req.conversation_id)
        had_previous_context = conversation_prev_id is not None
        if conversation_prev_id:
            tr(f"Continuing from previous response_id={conversation_prev_id}")
        else:
            tr("New conversation (no previous response_id)")

        # prev_id se inicializa con el de la conversación anterior (solo para el primer round)
        prev_id: Optional[str] = conversation_prev_id
        next_input: List[Dict[str, Any]] = [{"role": "user", "content": req.user_message}]

        # Tool-calling loop
        for round_idx in range(1, 7):
            tr(f"--- ROUND {round_idx} --- prev_id={prev_id}")

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
                    tr(f"previous_response_id expired/invalid: {api_error}, retrying without it")
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
            
            tr(f"OpenAI response.id={response.id} took={time.time() - t0:.2f}s")

            rounds_used = round_idx
            final_response_id = response.id

            # Final answer
            if getattr(response, "output_text", None):
                tr(f"FINAL OUTPUT len={len(response.output_text)}")
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
            tr(f"tool_calls={len(calls)}")

            if not calls:
                tr("No tool calls and no output_text -> stopping")
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

            for i, item in enumerate(calls, start=1):
                name = getattr(item, "name", "")
                try:
                    args = json.loads(getattr(item, "arguments", "") or "{}")
                except Exception:
                    args = {"_raw_arguments": getattr(item, "arguments", "")}

                tr(f"CALL {i}: {name} args={args}")

                fn = TOOL_IMPL.get(name)
                t1 = time.time()
                if fn:
                    # Manejar funciones async y síncronas
                    if inspect.iscoroutinefunction(fn):
                        result = await fn(args, req.conversation_id)
                    else:
                        result = fn(args, req.conversation_id)
                else:
                    result = {"error": f"Tool no implementada: {name}"}
                dt = time.time() - t1

                # Summary
                summary = ""
                if isinstance(result, dict):
                    if "hits" in result and isinstance(result["hits"], list):
                        ids = [f'{h.get("type")}:{h.get("id")}' for h in result["hits"][:5]]
                        summary = f"hits={len(result['hits'])} top={ids}"
                    elif "ticket_data" in result:
                        td = result.get("ticket_data") or {}
                        summary = f"ticket_data_keys={list(td.keys())[:8]} comments={'ticket_comments' in result}"
                    elif "blocks" in result:
                        summary = f"doc_blocks={len(result.get('blocks', []))}"
                    elif "query_type" in result and result.get("query_type") == "sql":
                        summary = f"sql_query_results={result.get('results_count', 0)}/{result.get('total_results', 0)}"
                    elif "error" in result:
                        summary = f"error={result['error']}"
                tr(f"CALL {i} DONE in {dt:.2f}s :: {summary}")

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(item, "call_id", ""),
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            prev_id = response.id
            next_input = tool_outputs

        tr("Reached max rounds")
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
            tr(f"Possible expired response_id error: {e}, clearing context")
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
