"""
Implementaciones de herramientas para chat_v2
"""
import os
import re
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
from Tools.get_etiquetas import get_etiqueta_context
from Tools.search_etiquetas import search_etiquetas
from Tools.get_quotes import get_quotes_context
from Tools.search_quotes import search_quotes
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
    # Para tickets: usar semántica por defecto (mejor calidad de resultados)
    # Para docs: mantener hybrid/keyword según longitud
    if policy == "auto":
        if scope in ("tickets", "all"):
            policy = "semantic"  # Semántica por defecto para tickets
        else:
            policy = "hybrid" if len(query.split()) <= 8 else "keyword"

    tr(f"Buscando en documentación interna Zell...")
    tr(f"Explorando scope={scope} ejecutando estrategia={policy}")
    tr(f"Obteniendo top {top_k} resultados para query: '{query[:120]}'")

    hits: list[Dict[str, Any]] = []
    notes: list[str] = []
    
    # Si universe="all", buscar en todos los scopes automáticamente
    # y ajustar top_k para obtener top_k por cada categoría (no global)
    if universe == "all":
        scope = "all"
        # Cuando es "all", queremos top_k resultados POR CADA categoría, no global
        # Mantener top_k original para cada búsqueda individual
        tr(f"universe='all' detectado: buscando en todos los scopes (tickets, quotes, etiquetas, docs)")
        tr(f"Obtendrá hasta {top_k} resultados por cada categoría (tickets, quotes, etiquetas, cada universo de docs)")

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

    # ---- ETIQUETAS ----
    if scope in ("etiquetas", "all"):
        tr(f"Buscando etiquetas del sistema ZELL...")
        try:
            etiquetas_res = search_etiquetas(query=query, top_k=top_k)
            if etiquetas_res.get("ok"):
                etiquetas_hits = etiquetas_res.get("hits", []) or []
                count = len(etiquetas_hits)
                if count > 0:
                    tr(f"Encontradas {count} etiquetas")
                else:
                    tr(f"No se encontraron etiquetas")
                
                for h in etiquetas_hits:
                    hits.append({
                        "type": "etiqueta",
                        "id": str(h.get("numero", "")),
                        "score": float(h.get("score", 0.0)),
                        "method": "semantic",
                        "snippet": f"{h.get('etiqueta', '')} - {h.get('descripcion', '')}",
                        "metadata": {
                            "numero": h.get("numero"),
                            "etiqueta": h.get("etiqueta"),
                            "descripcion": h.get("descripcion"),
                            "desc_tabla": h.get("desc_tabla"),
                            "tipo_dato": h.get("tipo_dato"),
                            "longitud": h.get("longitud"),
                            "query": h.get("query"),
                        },
                    })
            else:
                err = etiquetas_res.get("error")
                tr(f"Error al buscar etiquetas: {err}")
                notes.append(f"etiquetas: error={err}")
        except Exception as e:
            tr(f"Excepción al buscar etiquetas: {e}")
            notes.append(f"etiquetas: exception={e}")

    # ---- QUOTES (COTIZACIONES) ----
    if scope in ("quotes", "cotizaciones", "all"):
        tr(f"Buscando cotizaciones del sistema ZELL...")
        try:
            quotes_res = search_quotes(query=query, top_k=top_k)
            if quotes_res.get("ok"):
                quotes_hits = quotes_res.get("hits", []) or []
                count = len(quotes_hits)
                if count > 0:
                    tr(f"Encontradas {count} cotizaciones")
                else:
                    tr(f"No se encontraron cotizaciones")
                
                for h in quotes_hits:
                    title = h.get("v_title", "")
                    descriptions = h.get("descriptions") or ""
                    snippet = title
                    if descriptions:
                        snippet = f"{title} - {descriptions[:100]}"
                    
                    hits.append({
                        "type": "quote",
                        "id": str(h.get("i_issue_id", "")),
                        "score": float(h.get("score", 0.0)),
                        "method": "semantic",
                        "snippet": snippet[:220],
                        "metadata": {
                            "i_issue_id": h.get("i_issue_id"),
                            "i_quote_id": h.get("i_quote_id"),
                            "v_title": h.get("v_title"),
                            "i_units": h.get("i_units"),
                            "f_payment_date": h.get("f_payment_date"),
                            "descriptions": h.get("descriptions"),
                        },
                    })
            else:
                err = quotes_res.get("error")
                tr(f"Error al buscar cotizaciones: {err}")
                notes.append(f"quotes: error={err}")
        except Exception as e:
            tr(f"Excepción al buscar cotizaciones: {e}")
            notes.append(f"quotes: exception={e}")

    # ---- DOCS ----
    if scope in ("docs", "all"):
        # Si universe="all", buscar en todos los universos disponibles
        if universe == "all":
            available_universes = ["docs_org", "user_guides", "meetings_weekly"]
            tr(f"Buscando en todos los universos de docs: {available_universes}")
            all_dhits = []
            
            for uni in available_universes:
                try:
                    doc_res = search_docs(query=query, universe=uni, top_k=top_k)
                    if doc_res.get("ok"):
                        uni_hits = doc_res.get("hits", []) or []
                        if uni_hits:
                            tr(f"Encontrados {len(uni_hits)} documentos en {uni}")
                            # Agregar el universo a cada hit para identificarlo después
                            for hit in uni_hits:
                                hit["universe"] = uni
                            all_dhits.extend(uni_hits)
                        else:
                            tr(f"No se encontraron documentos en {uni}")
                except Exception as e:
                    tr(f"Error buscando en {uni}: {e}")
                    notes.append(f"{uni}: error={e}")
            
            # Ordenar todos los resultados por score (menor = mejor)
            all_dhits.sort(key=lambda x: float(x.get("score", 999)))
            # Tomar top_k global
            dhits = all_dhits[:top_k]
            tr(f"Total de resultados combinados: {len(dhits)} de {len(all_dhits)} encontrados")
        else:
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
                else:
                    err = doc_res.get("error")
                    tr(f"Error al buscar documentos: {err}")
                    notes.append(f"docs: error={err}")
                    dhits = []
            except Exception as e:
                tr(f"Excepción al buscar documentos: {e}")
                notes.append(f"docs: exception={e}")
                dhits = []
        
        # Procesar hits (ya sea de un universo o de todos)
        for h in dhits:
                    # Obtener el universo real del hit (si viene de búsqueda "all", el hit tiene su propio universo)
                    hit_universe = h.get("universe") if h.get("universe") else universe
                    
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
                        "universe": hit_universe,
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

    # Si universe="all", NO aplicar top_k global (queremos resultados de todas las categorías)
    # Solo aplicar dedupe para eliminar duplicados
    if universe == "all":
        # Para "all", mantener todos los hits de cada categoría (ya limitados por top_k en cada búsqueda)
        final_hits = _dedupe_hits(hits, top_k=9999)  # Dedupe sin límite global
    else:
        # Para búsquedas normales, aplicar top_k global
        final_hits = _dedupe_hits(hits, top_k=top_k)
    
    total_found = len(final_hits)
    if total_found > 0:
        tr(f"Total de resultados encontrados: {total_found}")
    else:
        tr(f"Sin resultados en ninguna fuente")
    
    # Si universe="all", estructurar resultados por categoría
    if universe == "all":
        results_by_category = {
            "tickets": [],
            "quotes": [],
            "etiquetas": [],
            "meetings_weekly": [],
            "user_guides": [],
            "docs_org": [],
        }
        
        for hit in final_hits:
            hit_type = hit.get("type", "")
            if hit_type == "ticket":
                results_by_category["tickets"].append(hit)
            elif hit_type == "quote":
                results_by_category["quotes"].append(hit)
            elif hit_type == "etiqueta":
                results_by_category["etiquetas"].append(hit)
            elif hit_type == "doc":
                doc_universe = hit.get("metadata", {}).get("universe", "")
                if doc_universe == "meetings_weekly":
                    results_by_category["meetings_weekly"].append(hit)
                elif doc_universe == "user_guides":
                    results_by_category["user_guides"].append(hit)
                elif doc_universe == "docs_org":
                    results_by_category["docs_org"].append(hit)
                else:
                    # Si no tiene universe claro, ponerlo en docs_org por defecto
                    results_by_category["docs_org"].append(hit)
        
        # Ordenar cada categoría según su sistema de scoring:
        # - Tickets: mayor score = mejor (similitud 0-1)
        # - Quotes/Etiquetas: mayor score = mejor (producto interno, típicamente > 0.80)
        # - Docs: menor score = mejor (distancia FAISS, típicamente < 0.6)
        results_by_category["tickets"].sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        results_by_category["quotes"].sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        results_by_category["etiquetas"].sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        # Docs ya vienen ordenados por menor score (mejor) desde search_docs
        results_by_category["meetings_weekly"].sort(key=lambda x: float(x.get("score", 999)))
        results_by_category["user_guides"].sort(key=lambda x: float(x.get("score", 999)))
        results_by_category["docs_org"].sort(key=lambda x: float(x.get("score", 999)))
        
        return {
            "hits": final_hits,
            "notes": notes,
            "results_by_category": results_by_category,
            "universe_all": True,
        }
    
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

    # ---- ETIQUETA ----
    if item_type == "etiqueta":
        tr(f"Obteniendo información de la etiqueta {item_id}")
        try:
            # item_id puede ser chunk_id (ej: "etiqueta_101") o número (ej: "101")
            # Intentar primero como número
            numero = None
            chunk_id = None
            try:
                numero = int(item_id)
                chunk_id = None
            except (ValueError, TypeError):
                # Si no es número, tratar como chunk_id
                chunk_id = item_id
                numero = None
            
            if numero is not None:
                result = get_etiqueta_context(numeros=[numero])
            else:
                result = get_etiqueta_context(chunk_ids=[chunk_id])
            
            if result.get("ok") and result.get("etiquetas"):
                etiqueta = result.get("etiquetas", [{}])[0]
                etiqueta_code = etiqueta.get("etiqueta") or f"#{etiqueta.get('numero', 'N/A')}"
                descripcion = etiqueta.get("descripcion") or "N/A"
                tr(f"Etiqueta obtenida: {etiqueta_code} - {descripcion[:60]}")
            else:
                tr(f"Obteniendo información de la etiqueta...")
            return result
        except Exception as e:
            return {
                "ok": False,
                "error": f"get_etiqueta_context_failed: {e}",
                "item_id": item_id,
            }

    # ---- QUOTE (COTIZACION) ----
    if item_type == "quote":
        tr(f"Obteniendo información de la cotización {item_id}")
        try:
            # item_id puede ser chunk_id (ej: "quote_1054") o i_issue_id (ej: "1054")
            # Intentar primero como número (i_issue_id)
            issue_id = None
            chunk_id = None
            try:
                issue_id = int(item_id)
                chunk_id = None
            except (ValueError, TypeError):
                # Si no es número, tratar como chunk_id
                chunk_id = item_id
                issue_id = None
            
            if issue_id is not None:
                result = get_quotes_context(i_issue_ids=[issue_id])
            else:
                result = get_quotes_context(chunk_ids=[chunk_id])
            
            if result.get("ok") and result.get("quotes"):
                quote = result.get("quotes", [{}])[0]
                title = quote.get("v_title") or "N/A"
                tr(f"Cotización obtenida: {title[:60]}")
            else:
                tr(f"Obteniendo información de la cotización...")
            return result
        except Exception as e:
            return {
                "ok": False,
                "error": f"get_quotes_context_failed: {e}",
                "item_id": item_id,
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


async def tool_analyze_client_email(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    """
    Tool para analizar correos de clientes: retorna el correo completo y obtiene el procedimiento de atención.
    El LLM central debe extraer el bloque relevante del correo y hacer las búsquedas semánticas con search_knowledge.
    """
    email_content = (args.get("email_content") or "").strip()
    
    if not email_content:
        return {"error": "email_content es requerido"}
    
    tr(f"Analizando correo de cliente...")
    
    # Constante del doc_id del procedimiento P-OPR-01
    P_OPR_01_DOC_ID = "077d56bcd4cf"
    
    result: Dict[str, Any] = {
        "email_content": email_content,
        "procedure_document": None,
    }
    
    # Obtener el documento completo del Procedimiento P-OPR-01
    tr(f"Obteniendo documento completo P-OPR-01 (doc_id: {P_OPR_01_DOC_ID})...")
    try:
        doc_result = get_doc_context(
            universe="docs_org",
            doc_id=P_OPR_01_DOC_ID,
            max_chunks=9999  # Obtener todos los chunks
        )
        if doc_result.get("ok"):
            blocks_count = len(doc_result.get("blocks", []))
            tr(f"Documento P-OPR-01 obtenido: {blocks_count} chunks")
            result["procedure_document"] = {
                "title": "P-OPR-01 Procedimiento de Solicitud de atención",
                "doc_id": P_OPR_01_DOC_ID,
                "blocks": doc_result.get("blocks", []),
                "total_chunks": blocks_count,
            }
        else:
            tr(f"Error al obtener documento P-OPR-01: {doc_result.get('error')}")
    except Exception as e:
        tr(f"Excepción al obtener documento: {e}")
    
    result["ok"] = True
    result["note"] = (
        "Correo completo recibido. Debes extraer el bloque relevante del correo (sin saludos/despedidas) "
        "y usar ese bloque para hacer búsquedas semánticas en tickets y cotizaciones con search_knowledge. "
        "Luego propone siguientes pasos según el procedimiento P-OPR-01."
    )
    
    return result


async def tool_propose_next_steps(args: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    """
    Tool para proponer siguientes pasos basándose en un ticket.
    Obtiene el ticket completo, construye query concatenando título y descripción,
    hace búsquedas semánticas en tickets y cotizaciones (top_k=3), obtiene los items completos,
    y obtiene el procedimiento de atención (P-OPR-01).
    """
    ticket_id = str(args.get("ticket_id") or "").strip()
    
    if not ticket_id:
        return {"error": "ticket_id es requerido"}
    
    tr(f"Analizando ticket #{ticket_id} para proponer siguientes pasos...")
    
    # Constante del doc_id del procedimiento P-OPR-01
    P_OPR_01_DOC_ID = "077d56bcd4cf"
    
    # 1. Obtener el ticket completo
    try:
        ticket_result = tool_get_item(
            {"type": "ticket", "id": ticket_id, "include_comments": True},
            conversation_id
        )
        
        if "error" in ticket_result:
            tr(f"Error al obtener ticket: {ticket_result['error']}")
            return {"error": f"No se pudo obtener el ticket: {ticket_result['error']}"}
        
        tr(f"Ticket #{ticket_id} obtenido exitosamente")
    except Exception as e:
        tr(f"Excepción al obtener ticket: {e}")
        return {"error": f"Error al obtener ticket: {str(e)}"}
    
    ticket_data = ticket_result.get("ticket_data", {})
    ticket_comments = ticket_result.get("ticket_comments", [])
    
    # 2. Construir query concatenando título y descripción
    query_parts = []
    title = ticket_data.get("Titulo") or ticket_data.get("title") or ""
    description = ticket_data.get("Descripcion") or ticket_data.get("description") or ""
    
    if title:
        query_parts.append(title)
    if description:
        query_parts.append(description)
    
    search_query = " ".join(query_parts).strip()
    if not search_query:
        search_query = f"ticket {ticket_id}"
    
    tr(f"Query construida (título + descripción) para búsqueda semántica: {search_query[:100]}...")
    
    # 4. Búsqueda semántica en tickets (top_k=3)
    similar_tickets_ids = []
    try:
        tr(f"Buscando tickets similares (top_k=3)...")
        tickets_search_result = tool_search_knowledge(
            {
                "query": search_query,
                "scope": "tickets",
                "policy": "semantic",
                "top_k": 3,
            },
            conversation_id
        )
        if tickets_search_result.get("hits"):
            for hit in tickets_search_result.get("hits", []):
                hit_ticket_id = hit.get("id")
                if hit_ticket_id and hit_ticket_id != ticket_id:  # Excluir el ticket actual
                    similar_tickets_ids.append(hit_ticket_id)
            tr(f"Encontrados {len(similar_tickets_ids)} tickets similares")
    except Exception as e:
        tr(f"Error al buscar tickets similares: {e}")
    
    # 5. Búsqueda semántica en cotizaciones (top_k=3)
    similar_quotes_metadata = []
    try:
        tr(f"Buscando cotizaciones similares (top_k=3)...")
        quotes_search_result = tool_search_knowledge(
            {
                "query": search_query,
                "scope": "quotes",
                "policy": "semantic",
                "top_k": 3,
            },
            conversation_id
        )
        if quotes_search_result.get("hits"):
            for hit in quotes_search_result.get("hits", []):
                # El id en el hit es i_issue_id, y también está en metadata
                issue_id = hit.get("id") or hit.get("metadata", {}).get("i_issue_id")
                if issue_id:
                    similar_quotes_metadata.append({
                        "i_issue_id": str(issue_id),
                        "i_quote_id": hit.get("metadata", {}).get("i_quote_id"),
                        "metadata": hit.get("metadata", {}),
                    })
            tr(f"Encontradas {len(similar_quotes_metadata)} cotizaciones similares")
    except Exception as e:
        tr(f"Error al buscar cotizaciones similares: {e}")
    
    # 6. Obtener tickets similares completos
    similar_tickets_data = []
    for similar_ticket_id in similar_tickets_ids:
        try:
            tr(f"Obteniendo ticket completo #{similar_ticket_id}...")
            similar_ticket_result = tool_get_item(
                {"type": "ticket", "id": similar_ticket_id, "include_comments": True},
                conversation_id
            )
            if "error" not in similar_ticket_result:
                similar_tickets_data.append({
                    "ticket_id": similar_ticket_id,
                    "ticket_data": similar_ticket_result.get("ticket_data"),
                    "ticket_comments": similar_ticket_result.get("ticket_comments", []),
                })
        except Exception as e:
            tr(f"Error al obtener ticket #{similar_ticket_id}: {e}")
    
    # 7. Obtener cotizaciones similares completas
    similar_quotes_data = []
    for quote_meta in similar_quotes_metadata:
        issue_id = quote_meta.get("i_issue_id")
        try:
            tr(f"Obteniendo cotización completa (i_issue_id: {issue_id})...")
            quote_result = tool_get_item(
                {"type": "quote", "id": issue_id},
                conversation_id
            )
            if "error" not in quote_result and quote_result.get("ok"):
                quotes_list = quote_result.get("quotes", [])
                if quotes_list:
                    similar_quotes_data.append({
                        "i_issue_id": issue_id,
                        "i_quote_id": quote_meta.get("i_quote_id"),
                        "quote_data": quotes_list[0],  # Primera cotización encontrada
                    })
        except Exception as e:
            tr(f"Error al obtener cotización (i_issue_id: {issue_id}): {e}")
    
    # 8. Obtener el documento completo del Procedimiento P-OPR-01
    tr(f"Obteniendo documento completo P-OPR-01 (doc_id: {P_OPR_01_DOC_ID})...")
    procedure_document = None
    try:
        doc_result = get_doc_context(
            universe="docs_org",
            doc_id=P_OPR_01_DOC_ID,
            max_chunks=9999  # Obtener todos los chunks
        )
        if doc_result.get("ok"):
            blocks_count = len(doc_result.get("blocks", []))
            tr(f"Documento P-OPR-01 obtenido: {blocks_count} chunks")
            procedure_document = {
                "title": "P-OPR-01 Procedimiento de Solicitud de atención",
                "doc_id": P_OPR_01_DOC_ID,
                "blocks": doc_result.get("blocks", []),
                "total_chunks": blocks_count,
            }
        else:
            tr(f"Error al obtener documento P-OPR-01: {doc_result.get('error')}")
    except Exception as e:
        tr(f"Excepción al obtener documento: {e}")
    
    # 9. Retornar información estructurada
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "ticket_data": ticket_data,
        "ticket_comments": ticket_comments,
        "similar_tickets": similar_tickets_data,
        "similar_quotes": similar_quotes_data,
        "procedure_document": procedure_document,
        "note": (
            "Ticket analizado, tickets similares, cotizaciones similares y procedimiento obtenidos. "
            "Busca soluciones en los tickets y cotizaciones similares. "
            "Usa el procedimiento P-OPR-01 de manera MUY SUTIL solo para analizar el estatus del ticket y mencionar lo que sigue. "
            "El valor real está en la información de tickets y cotizaciones similares."
        ),
    }


TOOL_IMPL = {
    "search_knowledge": tool_search_knowledge,
    "get_item": tool_get_item,
    "query_tickets": tool_query_tickets,
    "analyze_client_email": tool_analyze_client_email,
    "propose_next_steps": tool_propose_next_steps,
}

