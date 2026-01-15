"""
Ejecutor de herramientas para chat_v2
"""
import json
import inspect
import time
from typing import Any, Dict, List

from ..live_steps import tr
from ..tool_description import TOOL_IMPL
from ..context_manager import (
    can_use_web_search,
    get_web_search_count,
    increment_web_search_count,
)
from ..config import MAX_WEB_SEARCHES_PER_CONV


def execute_tool_call(
    item: Any,
    conversation_id: str,
    validate_web_search: bool = True
) -> tuple[Dict[str, Any], bool, str]:
    """
    Ejecuta una llamada a tool individual.
    
    Args:
        item: Item de function_call de OpenAI
        conversation_id: ID de la conversación
        validate_web_search: Si True, valida límite de web_search (para endpoint principal)
    
    Returns:
        Tuple de (result, web_search_used, tool_name)
    """
    name = getattr(item, "name", "")
    tool_type = getattr(item, "type", None)
    
    # Detectar si es web_search (tool integrado de OpenAI)
    is_web_search = (tool_type == "web_search" or name == "web_search")
    
    # Validar límite de búsquedas web (solo en endpoint principal)
    if is_web_search and validate_web_search:
        if not can_use_web_search(conversation_id):
            current_count = get_web_search_count(conversation_id)
            tr(f"Límite de búsquedas web alcanzado (count={current_count}/{MAX_WEB_SEARCHES_PER_CONV}) - BLOQUEADO")
            result = {
                "error": f"Límite de búsquedas web alcanzado. Se han realizado {current_count} búsquedas web en esta conversación (máximo: {MAX_WEB_SEARCHES_PER_CONV}).",
                "limit_reached": True,
                "current_count": current_count,
                "max_allowed": MAX_WEB_SEARCHES_PER_CONV
            }
            return result, False, "web_search"
        else:
            # Incrementar contador antes de procesar
            new_count = increment_web_search_count(conversation_id)
            
            # Intentar extraer la query del contexto si está disponible
            web_query = ""
            try:
                if hasattr(item, "arguments") and item.arguments:
                    args_dict = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                    web_query = args_dict.get("query", "") or args_dict.get("search_query", "")
            except:
                pass
            
            # Siempre mostrar mensaje cuando se ejecuta web_search
            if web_query:
                tr(f"Ejecutando web_search para: {web_query[:100]}")
            else:
                tr(f"Ejecutando web_search para: [query procesada por OpenAI]")
            
            tr(f"Búsqueda web permitida (count={new_count}/{MAX_WEB_SEARCHES_PER_CONV}) - OpenAI ejecutará la búsqueda internamente")
            # web_search es manejado por OpenAI, retornar None para indicar que no hay output manual
            return None, True, "web_search"
    
    # Para web_search sin validación (en process_chat_v2_core)
    if is_web_search:
        web_search_used = True
        tools_called = "web_search"
        
        # Intentar extraer la query si está disponible
        web_query = ""
        try:
            if hasattr(item, "arguments") and item.arguments:
                args_dict = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                web_query = args_dict.get("query", "") or args_dict.get("search_query", "")
        except:
            pass
        
        if web_query:
            tr(f"Ejecutando web_search para: {web_query[:100]}")
        else:
            tr(f"Ejecutando web_search para: [query procesada por OpenAI]")
        
        tr(f"[DEBUG] web_search mensaje emitido - OpenAI ejecutará la búsqueda internamente")
        # OpenAI maneja web_search automáticamente
        return None, web_search_used, tools_called
    
    # Procesar tool normal
    try:
        args = json.loads(getattr(item, "arguments", "") or "{}")
    except Exception:
        args = {"_raw_arguments": getattr(item, "arguments", "")}
    
    tool_name_display = name or tool_type or "unknown"
    tr(f"Ejecutando tool: {tool_name_display}...")
    
    fn = TOOL_IMPL.get(name)
    if not fn:
        tr(f"Tool {name} no implementada")
        return {"error": f"Tool no implementada: {name}"}, False, tool_name_display
    
    # Retornar función para ejecutar (el caller manejará async/sync)
    return (fn, args), False, tool_name_display
    
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
    
    return result, False, tool_name_display


def build_tool_output(result: Any, call_id: str) -> Dict[str, Any]:
    """Construye el output de tool en formato Responses API"""
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(result, ensure_ascii=False),
    }

