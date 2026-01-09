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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

# --- Auth (optional skip in local) ---
from utils.token_verifier import verificar_token

# --- Logging V2 ---
from utils.logs_v2 import (
    log_chat_v2_interaction,
    log_token_usage,
    extract_token_usage,
    calculate_cost,
    set_trace_function,
)

# --- OpenAI client (usando ai_calls centralizado) ---
from utils.ai_calls import responses_create

# --- Imports del módulo chat_v2 ---
from v2_internal import (
    ChatV2Request,
    TRACE_V2,
    SKIP_AUTH,
    MAX_WEB_SEARCHES_PER_CONV,
    get_last_response_id,
    save_last_response_id,
    clear_conversation_context,
    get_web_search_count,
    increment_web_search_count,
    can_use_web_search,
    StepEmitter,
    get_step_emitter,
    set_step_emitter,
    tr,
    TOOLS,
    SYSTEM_INSTRUCTIONS,
    TOOL_IMPL,
    process_chat_v2_core,
)

router = APIRouter()

# Configurar función de trace para logs_v2
set_trace_function(tr)


# --------------------------
# Endpoint principal
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
        for round_idx in range(1, 13):  # Máximo 12 rounds
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
            
            # Extraer información de tokens y costos (con manejo robusto de errores)
            try:
                token_info = extract_token_usage(response)
                model_used = os.getenv("V2_MODEL", "gpt-5-mini")
                
                # Asegurar que token_info es un dict válido antes de accederlo
                if not isinstance(token_info, dict):
                    tr(f"⚠️ token_info no es un dict después de extract_token_usage: {type(token_info)}, usando valores por defecto")
                    token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                
                # Debug: verificar que token_info tiene cached_tokens
                cached_val = token_info.get("cached_tokens", 0)
                if cached_val > 0:
                    tr(f"[DEBUG chat_v2] token_info después de extract_token_usage: {token_info}")
                
                total_tokens = token_info.get("total_tokens", 0)
                if total_tokens > 0:
                    input_tokens_real = token_info.get("input_tokens_real", 0)
                    input_tokens_total = token_info.get("input_tokens_total", 0)
                    cached_tokens = token_info.get("cached_tokens", 0)
                    output_tokens = token_info.get("output_tokens", 0)
                    
                    cached_info = f", cached={cached_tokens}" if cached_tokens > 0 else ""
                    tr(f"Tokens: input_total={input_tokens_total}, input_real={input_tokens_real}{cached_info}, output={output_tokens}, total={total_tokens}")
                    
                    try:
                        costs = calculate_cost(model_used, input_tokens_real, output_tokens, cached_tokens)
                        cached_cost_info = f", cached: ${costs.get('cost_cached_usd', 0):.6f}" if costs.get("cost_cached_usd", 0) > 0 else ""
                        tr(f"Cost: ${costs.get('cost_total_usd', 0):.6f} (input: ${costs.get('cost_input_usd', 0):.6f}{cached_cost_info}, output: ${costs.get('cost_output_usd', 0):.6f})")
                    except Exception as cost_err:
                        tr(f"⚠️ Error calculando costos (continuando sin bloquear bot): {cost_err}")
                        import traceback
                        tr(f"Traceback: {traceback.format_exc()}")
            except Exception as token_err:
                tr(f"⚠️ Error extrayendo información de tokens (continuando sin bloquear bot): {token_err}")
                import traceback
                tr(f"Traceback: {traceback.format_exc()}")
                # Crear token_info por defecto seguro
                token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                model_used = os.getenv("V2_MODEL", "gpt-5-mini")
            
            # Validación final: asegurar que token_info siempre es un dict válido antes de usar
            if not isinstance(token_info, dict):
                tr(f"⚠️ token_info no es un dict antes de usar: {type(token_info)}, usando valores por defecto")
                token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            rounds_used = round_idx
            final_response_id = response.id

            # Final answer
            if getattr(response, "output_text", None):
                tr(f"Generando respuesta final para el usuario...")
                tr(f"Respuesta final generada ({len(response.output_text)} caracteres)")
                
                # Log token usage para este round (respuesta final, sin tool calls) - con manejo robusto de errores
                try:
                    # Asegurar que token_info es un dict válido
                    if not isinstance(token_info, dict):
                        token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                    
                    total_tokens_val = token_info.get("total_tokens", 0)
                    if total_tokens_val > 0:
                        log_token_usage(
                            conversation_id=req.conversation_id,
                            response_id=response.id,
                            round_num=round_idx,
                            model=model_used,
                            input_tokens_total=token_info.get("input_tokens_total", 0),
                            input_tokens_real=token_info.get("input_tokens_real", 0),
                            cached_tokens=token_info.get("cached_tokens", 0),
                            output_tokens=token_info.get("output_tokens", 0),
                            total_tokens=total_tokens_val,
                            web_search_used=False,  # Si hay respuesta final, no hubo tool calls
                            tools_called=[]  # Si hay respuesta final, no hubo tool calls
                        )
                except Exception as log_err:
                    tr(f"⚠️ Error logueando token usage (continuando): {log_err}")
                    import traceback
                    tr(f"Traceback: {traceback.format_exc()}")
                except Exception as log_err:
                    tr(f"⚠️ Error logueando token usage (continuando): {log_err}")
                
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
                is_web_search = (tool_type == "web_search" or name == "web_search")
                
                # Debug: loguear cuando detectamos web_search
                if is_web_search:
                    tr(f"[DEBUG] web_search detectado - tool_type={tool_type}, name={name}, arguments={getattr(item, 'arguments', 'N/A')}")
                
                # Validar límite de búsquedas web
                if is_web_search:
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
                        continue  # web_search es manejado por OpenAI, no necesitamos procesarlo
                
                try:
                    args = json.loads(getattr(item, "arguments", "") or "{}")
                except Exception:
                    args = {"_raw_arguments": getattr(item, "arguments", "")}

                tool_name_display = name or tool_type or "unknown"
                tr(f"Ejecutando tool: {tool_name_display}...")
                tools_called_this_round.append(tool_name_display)

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

            # Log token usage para este round (cuando hay tool calls) - con manejo robusto de errores
            try:
                # Asegurar que token_info es un dict válido
                if not isinstance(token_info, dict):
                    token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                
                total_tokens_val = token_info.get("total_tokens", 0)
                if total_tokens_val > 0:
                    log_token_usage(
                        conversation_id=req.conversation_id,
                        response_id=response.id,
                        round_num=round_idx,
                        model=model_used,
                        input_tokens_total=token_info.get("input_tokens_total", 0),
                        input_tokens_real=token_info.get("input_tokens_real", 0),
                        cached_tokens=token_info.get("cached_tokens", 0),
                        output_tokens=token_info.get("output_tokens", 0),
                        total_tokens=total_tokens_val,
                        web_search_used=web_search_used_this_round,
                        tools_called=tools_called_this_round
                    )
            except Exception as log_err:
                tr(f"⚠️ Error logueando token usage (continuando): {log_err}")
                import traceback
                tr(f"Traceback: {traceback.format_exc()}")
                import traceback
                tr(f"Traceback: {traceback.format_exc()}")
            
            prev_id = response.id
            next_input = tool_outputs

        tr("Límite de rounds alcanzado (máximo 12)")
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
# ENDPOINT SSE: /chat_v2/stream
# ============================================

@router.post("/chat_v2/stream")
async def chat_v2_stream(req: ChatV2Request):
    """Endpoint SSE que muestra live steps mientras procesa la solicitud"""
    
    async def event_generator():
        # Crear emitter para este request
        emitter = StepEmitter()
        set_step_emitter(emitter)  # Guardar en contexto
        
        try:
            # Ejecutar el pipeline en un task
            task = asyncio.create_task(process_chat_v2_core(req))
            
            # Enviar eventos mientras procesa
            last_event_time = time.time()
            keep_alive_interval = 8.0  # Enviar keep-alive cada 8 segundos
            response_sent = False
            
            while not task.done() or not response_sent:
                try:
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
                                tr(f"⚠️ Error obteniendo resultado del task (continuando sin bloquear): {e}")
                                import traceback
                                tr(f"Traceback: {traceback.format_exc()}")
                                yield f"data: {json.dumps({'type': 'error', 'message': f'Error procesando respuesta: {str(e)}'}, ensure_ascii=False)}\n\n"
                                response_sent = True
                                break
                        
                        # Keep-alive: si pasan 8+ segundos sin eventos, enviar mensaje neutral
                        if time.time() - last_event_time > keep_alive_interval:
                            # Keep-alive sin mensaje visible (solo para mantener conexión)
                            yield f": keep-alive\n\n"
                            last_event_time = time.time()
                except Exception as loop_err:
                    tr(f"⚠️ Error en loop de eventos (continuando): {loop_err}")
                    # Continuar el loop sin bloquear
            
            # Asegurar que el task termine
            if not task.done():
                try:
                    await task
                except Exception as task_err:
                    tr(f"⚠️ Error esperando task (continuando): {task_err}")
            
        except Exception as e:
            tr(f"⚠️ Error en endpoint stream (enviando error al cliente): {e}")
            import traceback
            tr(f"Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error: {str(e)}'}, ensure_ascii=False)}\n\n"
        finally:
            set_step_emitter(None)  # Limpiar contexto
    
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
