"""
Implementaciones de herramientas para chat_v2
"""
from typing import Any, Dict

from Tools.get_tickets import (
    get_ticket_data,
    get_ticket_comments,
)
from Tools.search_tickets import (
    search_tickets_by_keywords,
    search_tickets_semantic,
    search_tickets_hybrid,
)
from Tools.search_docs import search_docs
from Tools.get_docs import get_doc_context
from Tools.query_tool import (
    generate_sql_query,
    fetch_query_results,
)
from utils.contextManager.context_handler import get_interaction_id

from ..live_steps import tr
from .helpers import _dedupe_hits


def tool_search_knowledge(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    scope = args.get("scope", "all")
    policy = args.get("policy", "auto")
    top_k = int(args.get("top_k", 3))
    # Limitar top_k para evitar saturación del contexto
    if top_k > 5:
        tr(f"⚠️ top_k={top_k} es demasiado alto, limitando a 5 para evitar saturación del contexto")
        top_k = 5
    universe = (args.get("universe") or "docs_org").strip()

    if not query:
        return {"hits": [], "notes": ["query vacío"]}

    # Simple AUTO heuristic
    if policy == "auto":
        policy = "hybrid" if len(query.split()) <= 8 else "keyword"

    tr(f"Buscando en documentación interna Zell...")
    tr(f"Explorando scope={scope} ejecutando estrategia={policy}")
    tr(f"Obteniendo top {top_k} resultados para query: '{query[:120]}'")

    hits: list[Dict[str, Any]] = []
    notes: list[str] = []

    # ---- TICKETS ----
    if scope in ("tickets", "all"):
        if policy == "hybrid":
            # Usar función híbrida dedicada
            tr(f"Ejecutando búsqueda híbrida (keywords + semántica)...")
            try:
                hybrid_results = search_tickets_hybrid(query, conversation_id, top_k=top_k)
                count = len(hybrid_results) if hybrid_results else 0
                if count > 0:
                    tr(f"Encontrados {count} tickets con búsqueda híbrida")
                else:
                    tr(f"No se encontraron tickets con búsqueda híbrida")

                for r in hybrid_results or []:
                    tid = r.get("ticket_id")
                    if tid is not None:
                        method = r.get("method", "hybrid")
                        hits.append(
                            {
                                "type": "ticket",
                                "id": str(tid),
                                "score": float(r.get("score", 0.0)),
                                "method": method,
                                "snippet": (r.get("title") or "")[:220] if "title" in r else "",
                                "metadata": {"title": r.get("title", "")} if "title" in r else {},
                            }
                        )
            except Exception as e:
                tr(f"Error en búsqueda híbrida: {e}")
                notes.append(f"hybrid error: {e}")

        elif policy == "keyword":
            # Solo búsqueda por keywords
            words = [w.strip(".,:;!?()[]{}\"'").lower() for w in query.split()]
            words = [w for w in words if len(w) >= 4][:6] or [query]
            tr(f"Buscando en tickets con palabras clave: {words}")
            try:
                keyword_results = search_tickets_by_keywords(words, max_results=top_k)
                count = len(keyword_results) if keyword_results else 0
                if count > 0:
                    tr(f"Encontrados {count} tickets con búsqueda por palabras clave")
                else:
                    tr(f"No se encontraron tickets con palabras clave")

                for r in keyword_results or []:
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
            except Exception as e:
                tr(f"Error en búsqueda por keywords: {e}")
                notes.append(f"keyword error: {e}")

        elif policy == "semantic":
            # Solo búsqueda semántica
            tr(f"Buscando en tickets con búsqueda semántica...")
            try:
                semantic_results = search_tickets_semantic(query, conversation_id, top_k=top_k)
                count = len(semantic_results) if semantic_results else 0
                if count > 0:
                    tr(f"Encontrados {count} tickets con búsqueda semántica")
                else:
                    tr(f"No se encontraron tickets con búsqueda semántica")

                for r in semantic_results or []:
                    tid = r.get("ticket_id")
                    if tid is not None:
                        hits.append(
                            {
                                "type": "ticket",
                                "id": str(tid),
                                "score": float(r.get("score", 0.0)),
                                "method": "semantic",
                                "snippet": "",
                                "metadata": {},
                            }
                        )
            except Exception as e:
                tr(f"Error en búsqueda semántica: {e}")
                notes.append(f"semantic error: {e}")

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
                    # Para user_guides, agregar info adicional (paso, objetivo)
                    if h.get("step_label"):
                        snippet_parts.append(f"Paso {h.get('step_label')}")
                    if h.get("objetivo"):
                        snippet_parts.append(f"Objetivo: {h.get('objetivo')[:80]}")
                    
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
                    # Metadata específica para user_guides
                    if h.get("objetivo"):
                        metadata["objetivo"] = h.get("objetivo")
                    if h.get("step_label"):
                        metadata["step_label"] = h.get("step_label")
                    if h.get("step_number"):
                        metadata["step_number"] = h.get("step_number")
                    if h.get("doc_number"):
                        metadata["doc_number"] = h.get("doc_number")
                    if h.get("referencia_cliente_ticket"):
                        metadata["referencia_cliente_ticket"] = h.get("referencia_cliente_ticket")
                    
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

    # ---- DOC ----
    if item_type == "doc":
        universe = (args.get("universe") or "docs_org").strip()
        try:
            # item_id = chunk_id
            result = get_doc_context(universe=universe, chunk_ids=[item_id], max_chunks=6)
            if result.get("ok") and result.get("blocks"):
                blocks_count = len(result.get("blocks", []))
                title = result.get("blocks", [{}])[0].get("title", "N/A") if result.get("blocks") else "N/A"
                # Mensaje con nombre del documento (no ID)
                if title and title != "N/A":
                    tr(f"Obteniendo información del documento: {title}")
                else:
                    tr(f"Obteniendo información del documento...")
            else:
                tr(f"Obteniendo información del documento...")
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
            ticket_data = get_ticket_data(item_id, conversation_id)
            # Verificar si hubo error
            if "error" in ticket_data:
                tr(f"Error al obtener ticket: {ticket_data['error']}")
                return {"error": ticket_data["error"]}
            
            title = ticket_data.get("Titulo") or ticket_data.get("title") or "N/A"
            tr(f"Ticket obtenido: {title}")
        except Exception as e:
            tr(f"Error al obtener ticket: {e}")
            return {"error": f"get_ticket_data falló: {e}"}

        out: Dict[str, Any] = {"ticket_data": ticket_data}

        if include_comments:
            tr(f"Obteniendo comentarios del ticket...")
            try:
                comments_result = get_ticket_comments(item_id, conversation_id)
                # Verificar si hubo error
                if "error" in comments_result:
                    tr(f"Error al obtener comentarios: {comments_result['error']}")
                    out["ticket_comments_error"] = comments_result["error"]
                else:
                    out["ticket_comments"] = comments_result
                    comments_count = len(comments_result) if isinstance(comments_result, list) else 1
                    tr(f"Comentarios obtenidos: {comments_count}")
            except Exception as e:
                tr(f"Error al obtener comentarios: {e}")
                out["ticket_comments_error"] = str(e)

        return out

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

