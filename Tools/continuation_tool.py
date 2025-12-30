from utils.llm_provider import chat_completion
from utils.llm_config import get_llm_config
import os
import json
import logging
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from utils.logs import log_interaction, log_ai_call
from utils.debug_logger import log_debug_event  # ✅ Corrected import

from utils.contextManager.context_handler import get_context, add_to_context, get_interaction_id
from utils.contextManager.short_term_memory import get_short_term_memory
from endpoints.classifier import classify_message, MessageRequest
from utils.tool_response import ToolResponse, make_error_response
from utils.prompt_loader import load_latest_prompt
from utils.tool_registry import register_tool

router = APIRouter()

class ContinuationRequest(BaseModel):
    conversation_id: str
    user_question: str
    step_id: int = 1

# █ Cargamos contenido + nombre de archivo del prompt de continuación
try:
    CONTINUATION_PROMPT, CONT_PROMPT_FILE = load_latest_prompt(
        "Continuada",         # carpeta dentro de Prompts
        "continuadaprompt",   # prefijo del prompt (sin _v y sin extensión)
        with_filename=True    # devuelve (texto, nombre_de_archivo)
    )
except Exception as e:
    logging.error(f"❗️ Error loading continuation prompt: {e}")
    CONTINUATION_PROMPT, CONT_PROMPT_FILE = None, "N/A"

if not CONTINUATION_PROMPT:
    logging.warning("⚠️ Continuation prompt could not be loaded!")

class TicketRequest(BaseModel):
    conversation_id: str
    user_question: str
    step_id: int = 1  # Valor por defecto si no se envía
    userName: str

@router.post("/continuation/query")
@register_tool("Pregunta Continuada")
async def execute_continuation_query(inputs, conversation_id, userName, interaction_id=None):
    user_question = inputs.get("user_question", "").strip()
    step_id = inputs.get("step_id", 1)

    if not user_question:
        logging.warning("⚠️ User question is empty.")
        return make_error_response("La pregunta del usuario está vacía.").model_dump()

    if interaction_id is None:
        interaction_id = get_interaction_id(conversation_id)

    conversation_data   = get_context(conversation_id)
    short_term_memory   = get_short_term_memory(conversation_id)
    conversation_history = conversation_data.get("history", [])
    last_tool           = conversation_data.get("active_tool")

    log_debug_event(
        "Pregunta Continuada",
        conversation_id,
        interaction_id,
        {
            "user_question": user_question,
            "last_tool": last_tool,
            "short_term_memory": short_term_memory,
            "conversation_history_length": len(conversation_history)
        }
    )

    if not last_tool or not conversation_history:
        log_interaction(
            userName=userName,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step_id=step_id,
            user_input=user_question,
            system_output="No context found for continuation",
            classification="Pregunta Continuada",
            extra_info="No previous interaction"
        )
        return make_error_response("No entiendo a qué te refieres. ¿Podrías proporcionar más contexto?").model_dump()

    # ── ARMADO DE MENSAJES PARA IA ──
    ai_messages = []

    # ① Prompt de continuación
    if CONTINUATION_PROMPT:
        ai_messages.append({
            "role": "system",
            "content": CONTINUATION_PROMPT
        })

    # ② Si venimos de ISO, inyectamos el prompt ISO más reciente
    if last_tool == "ISO":
        try:
            iso_full, iso_file = load_latest_prompt("ISO", "isoprompt", with_filename=True)
        except Exception as e:
            logging.error(f"❌ Error loading ISO prompt for continuation: {e}")
            iso_full = None

        if iso_full:
            ai_messages.append({
                "role": "system",
                "content": iso_full
            })

    # ③ Memoria y contexto
    ai_messages += [
        {"role": "system", "content": "Aquí está la memoria a corto plazo del usuario:"},
        {"role": "user",   "content": json.dumps(short_term_memory, ensure_ascii=False, indent=2)},
        {"role": "system", "content": "Aquí está la historia completa de la conversación hasta ahora:"},
        {"role": "user",   "content": json.dumps(conversation_history, ensure_ascii=False, indent=2)},
        {"role": "user",   "content": user_question}
    ]

    # ④ Filtramos solo contenidos válidos (strings no vacíos)
    ai_messages = [
        m for m in ai_messages
        if isinstance(m.get("content"), str) and m["content"].strip()
    ]

    # ── Llamada al modelo ───────────────────────────────
    try:
        resp = await chat_completion(
            ai_messages,
            tool="CONTINUATION",
            response_format={"type": "json_object"},
            timeout=30,
            temperature=1
        )

        if not resp or not resp.get("choices"):
            return make_error_response("Respuesta inválida del LLM.").model_dump()

        raw_content = resp["choices"][0]["message"]["content"].strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content.removeprefix("```json").removesuffix("```").strip()

        # Parseo seguro
        try:
            parsed_result = json.loads(raw_content)
            if not isinstance(parsed_result, dict):
                parsed_result = {"message": raw_content, "sufficient_info": False}
        except json.JSONDecodeError:
            parsed_result = {"message": raw_content, "sufficient_info": False}

        # ── Decide si contesto o reclasifico ───────────
        if parsed_result.get("sufficient_info", False):
            response_message = parsed_result["message"]
            add_to_context(conversation_id, "Pregunta Continuada",
                           user_question, response_message)
            log_interaction(userName, conversation_id, interaction_id, step_id,
                            user_question, response_message,
                            "Pregunta Respondida", "Continuada")
            return ToolResponse(
                classification="Pregunta Respondida",
                response=response_message
            ).model_dump()

        # ←── NO HAY INFO SUFICIENTE: reclasifico aquí mismo ───────────
        else:
            new_input = parsed_result.get("message", user_question)
            log_interaction(
            userName=userName,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step_id=step_id,
            user_input=user_question,
            system_output=f"Reclassified Query: {new_input}",
            classification="Reclassified",
            extra_info="Continuada"
        )
             
        from utils.token_verifier import recuperar_token_conversation_id
        token = inputs.get("zToken") or recuperar_token_conversation_id(conversation_id) or "NO-TOKEN"
        new_request = MessageRequest(
            userName=userName,
            conversation_id=conversation_id,
            user_message=new_input,
            zToken=token,
            step_id=step_id + 1,
            reclassified=True
        )
        return await classify_message(new_request)

        # llamamos al clasificador y envolvemos su respuesta
        #clsf = await classify_message(new_req)
#text = clsf.get("response", "")
#return ToolResponse(
#classification=clsf.get("classification", "Pregunta Continuada"),
#response=text
#).model_dump()

    # ── BLOQUES DE EXCEPCIÓN ALINEADOS CON EL try ─────
#except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
#error_msg = f"⏳ API timeout: {e}"
#log_interaction(conversation_id, interaction_id, step_id,
#user_question, error_msg, "TIMEOUT", "Continuada")
#return make_error_response("La operación tomó demasiado tiempo. Intenta de nuevo.").model_dump()

    except Exception as e:
        err = f"Error en Pregunta Continuada: {e}"
        logging.error(err)
        log_interaction(userName, conversation_id, interaction_id, step_id,
                        user_question, err, "ERROR", "Continuada Failure")
        return make_error_response(err).model_dump()








    




        