# endpoints/chat_v2.py
# V2 chat endpoint: Responses API + tool-calling loop + console tracing
# Notes:
# - Auth can be bypassed ONLY in local via env var SKIP_AUTH=1
# - TRACE_V2=1 prints a detailed trace of tool calls and outputs

import os
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

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

router = APIRouter()

TRACE_V2 = os.getenv("TRACE_V2", "0") == "1"
SKIP_AUTH = os.getenv("SKIP_AUTH", "0") == "1"


def tr(msg: str) -> None:
    if TRACE_V2:
        print(f"[V2-TRACE] {msg}", flush=True)


# --- OpenAI client ---
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY_V2")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("OPENAI_API_KEY_Clasificador")
)

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
                    "description": "Universo de documentos cuando scope=docs (ej: policies_iso, meetings_weekly, manuals_system).",
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
        "description": "Trae detalle de un item (ticket, quote, doc).",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["ticket", "quote", "doc"]},
                "id": {"type": "string"},
                "include_comments": {"type": "boolean", "default": True},
                "universe": {
                    "type": "string",
                    "description": "Universo de documentos cuando type=doc (ej: policies_iso, meetings_weekly, manuals_system).",
                    "default": "policies_iso",
                },
            },
            "required": ["type", "id"],
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
                    hits.append(
                        {
                            "type": "doc",
                            "id": str(h.get("chunk_id")),  # id = chunk_id
                            "score": float(h.get("score", 0.0)),
                            "method": "docs_semantic",
                            "snippet": f'{h.get("title","")} :: {h.get("section") or ""}'.strip()[:260],
                            "metadata": {
                                "doc_id": h.get("doc_id"),
                                "title": h.get("title"),
                                "section": h.get("section"),
                                "source_path": h.get("source_path"),
                                "universe": universe,
                                "codigo": h.get("codigo"),
                                "fecha_emision": h.get("fecha_emision"),
                                "revision": h.get("revision"),
                                "estatus": h.get("estatus"),
                            },
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


TOOL_IMPL = {
    "search_knowledge": tool_search_knowledge,
    "get_item": tool_get_item,
}


# --------------------------
# Endpoint
# --------------------------

@router.post("/chat_v2")
async def chat_v2(req: ChatV2Request):
    try:
        # Auth (skip in local only)
        if not SKIP_AUTH:
            verificar_token(req.zToken)
        else:
            tr("AUTH skipped (SKIP_AUTH=1)")

        tr(f"NEW REQUEST conv_id={req.conversation_id} user={req.userName}")
        tr(f"USER: {req.user_message}")

        prev_id: Optional[str] = None
        next_input: List[Dict[str, Any]] = [{"role": "user", "content": req.user_message}]

        # Tool-calling loop
        for round_idx in range(1, 7):
            tr(f"--- ROUND {round_idx} --- prev_id={prev_id}")

            t0 = time.time()
            response = client.responses.create(
                model=os.getenv("V2_MODEL", "gpt-5-mini"),
                instructions=SYSTEM_INSTRUCTIONS,
                tools=TOOLS,
                input=next_input,
                previous_response_id=prev_id,
            )
            tr(f"OpenAI response.id={response.id} took={time.time() - t0:.2f}s")

            # Final answer
            if getattr(response, "output_text", None):
                tr(f"FINAL OUTPUT len={len(response.output_text)}")
                return {"classification": "V2", "response": response.output_text}

            # Tool calls
            calls = [it for it in response.output if getattr(it, "type", None) == "function_call"]
            tr(f"tool_calls={len(calls)}")

            if not calls:
                tr("No tool calls and no output_text -> stopping")
                return {
                    "classification": "V2",
                    "response": "No hubo tool calls ni output_text (revisar tools/instructions).",
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
                result = fn(args, req.conversation_id) if fn else {"error": f"Tool no implementada: {name}"}
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
        return {"classification": "V2", "response": "Se alcanzó límite de pasos internos (tool loop)."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
