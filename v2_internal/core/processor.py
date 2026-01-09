"""
Procesador central de chat_v2
"""
import os
import json
import time
import inspect
from typing import Any, Dict, List, Optional

from utils.token_verifier import verificar_token
from utils.ai_calls import responses_create
from utils.logs_v2 import (
    log_chat_v2_interaction,
    log_token_usage,
    extract_token_usage,
    calculate_cost,
)

from ..models import ChatV2Request
from ..config import SKIP_AUTH
from ..context_manager import (
    get_last_response_id,
    save_last_response_id,
    clear_conversation_context,
)
from ..live_steps import tr, get_step_emitter
from ..tools import TOOLS, SYSTEM_INSTRUCTIONS, TOOL_IMPL
from .tool_executor import execute_tool_call, build_tool_output


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
            
            # Extraer información de tokens y costos (con manejo robusto de errores)
            # Inicializar token_info por defecto para asegurar que siempre esté definido
            token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            model_used = os.getenv("V2_MODEL", "gpt-5-mini")
            
            try:
                token_info = extract_token_usage(response)
                
                # Asegurar que token_info es un dict válido
                if not isinstance(token_info, dict):
                    tr(f"⚠️ token_info no es un dict: {type(token_info)}, usando valores por defecto")
                    token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                
                total_tokens = token_info.get("total_tokens", 0)
                if total_tokens > 0:
                    input_tokens_total = token_info.get("input_tokens_total", 0)
                    input_tokens_real = token_info.get("input_tokens_real", 0)
                    cached_tokens = token_info.get("cached_tokens", 0)
                    output_tokens = token_info.get("output_tokens", 0)
                    
                    cached_info = f", cached={cached_tokens}" if cached_tokens > 0 else ""
                    tr(f"Tokens: input_total={input_tokens_total}, input_real={input_tokens_real}{cached_info}, output={output_tokens}, total={total_tokens}")
                    try:
                        costs = calculate_cost(model_used, input_tokens_real, output_tokens, cached_tokens)
                        cached_cost_info = f", cached: ${costs.get('cost_cached_usd', 0):.6f}" if costs.get("cost_cached_usd", 0) > 0 else ""
                        tr(f"Cost: ${costs.get('cost_total_usd', 0):.6f} (input: ${costs.get('cost_input_usd', 0):.6f}{cached_cost_info}, output: ${costs.get('cost_output_usd', 0):.6f})")
                    except Exception as cost_err:
                        tr(f"⚠️ Error calculando costos (continuando): {cost_err}")
            except Exception as token_err:
                tr(f"⚠️ Error extrayendo información de tokens (continuando sin bloquear bot): {token_err}")
                import traceback
                tr(f"Traceback: {traceback.format_exc()}")
                # Asegurar que token_info siempre tiene valores por defecto
                token_info = {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            
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
                save_last_response_id(req.conversation_id, response.id)
                
                # Emitir respuesta final al emitter si existe (para SSE)
                emitter = get_step_emitter()
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
                try:
                    args = json.loads(getattr(item, "arguments", "") or "{}")
                except Exception:
                    args = {"_raw_arguments": getattr(item, "arguments", "")}

                tr(f"CALL {i}: {name} args={args}")

                # Ejecutar tool (sin validación de web_search para process_core)
                result, web_search_used, tool_name = execute_tool_call(
                    item, req.conversation_id, validate_web_search=False
                )
                
                if web_search_used:
                    web_search_used_this_round = True
                    tools_called_this_round.append(tool_name)
                    # web_search es manejado por OpenAI, no agregamos output
                    continue
                
                # Si result es una tupla (fn, args), ejecutar la función
                if isinstance(result, tuple) and len(result) == 2:
                    fn, fn_args = result
                    t1 = time.time()
                    # Detectar si la función es async o sync
                    if inspect.iscoroutinefunction(fn):
                        result = await fn(fn_args, req.conversation_id)
                    else:
                        result = fn(fn_args, req.conversation_id)
                    dt = time.time() - t1
                    tr(f"Tool {tool_name} completado en {dt:.2f}s")
                elif result is None:
                    # web_search o tool que no necesita output
                    continue
                
                tools_called_this_round.append(tool_name)
                
                tool_outputs.append(build_tool_output(result, getattr(item, "call_id", "")))

            # Log token usage con manejo robusto de errores
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
                tr(f"⚠️ Error logueando token usage (continuando sin bloquear bot): {log_err}")
            
            prev_id = response.id
            next_input = tool_outputs

        tr("Límite de rounds alcanzado (máximo 12)")
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

