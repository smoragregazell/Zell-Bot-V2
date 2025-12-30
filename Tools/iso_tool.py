import openai
import os
import json
import logging
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from dotenv import load_dotenv

from utils.tool_response import ToolResponse, make_error_response
from utils.logs import log_interaction, log_ai_call, log_ai_call_postgres
from utils.contextManager.context_handler import add_to_context, get_context, get_interaction_id
from utils.debug_logger import log_debug_event  # Added debug logger
from utils.prompt_loader import load_latest_prompt
from utils.tool_registry import register_tool

router = APIRouter()
logger = logging.getLogger(__name__)

class ISORequest(BaseModel):
    conversation_id: str
    user_question: str
    step_id: int = 1

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT_PATH", os.path.abspath(os.path.join(os.getcwd())))

def load_iso_prompt():
    try:
        # 1️⃣ Carga el prompt base más reciente (Prompts/ISO/isoprompt_v*.txt)
        base_prompt, prompt_file = load_latest_prompt("ISO", "isoprompt", with_filename=True)
        if not base_prompt:
            raise FileNotFoundError("No se encontró ningún isoprompt_v*.txt en Prompts/ISO")

        kb_files = [
            "Declaracion_de_Aplicabilidad.txt",
            "Manual_de_calidad_y_seguridad_de_la_informacion_final.txt"
        ]

        kb_content = ""
        kb_folder = os.path.join(PROJECT_ROOT, "knowledgebase/")

        for kb_file in kb_files:
            kb_path = os.path.join(kb_folder, kb_file)
            if os.path.isfile(kb_path):
                with open(kb_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    kb_content += f"\n\n=== Inicio de {kb_file} ===\n{content}\n=== Fin de {kb_file} ===\n"
            else:
                logger.error(f"❌ Archivo de KB no encontrado: {kb_file}")
                
        full_prompt = (
            f"{base_prompt}\n\n"
            "A continuación tienes la información completa del knowledgebase ISO:\n"
            f"{kb_content}"
        )
        return full_prompt, prompt_file
    except Exception as e:
        logger.error(f"❌ Error loading ISO prompt: {e}")
        return None, "N/A"
        
@router.post("/iso/chat")
@register_tool("ISO")
async def iso_chat(req: ISORequest, userName: str):
    conversation_id = req.conversation_id
    user_question = req.user_question.strip()
    step_id = req.step_id

    if not user_question:
        return make_error_response("La pregunta no puede estar vacía.")

    interaction_id = get_interaction_id(conversation_id)
    api_key = os.getenv("OPENAI_API_KEY_ISO")
    if not api_key:
        logger.error("❌ Falta OPENAI_API_KEY_ISO.")
        return make_error_response("No se pudo conectar con OpenAI - falta API key.")

    iso_prompt, ISO_PROMPT_FILE = load_iso_prompt()
    if not iso_prompt:
        logger.error("❌ No se pudo cargar el ISO prompt en tiempo de ejecución.")
        return make_error_response("No se pudo cargar el prompt ISO.")
    
    client = openai.OpenAI(api_key=api_key)
    conversation_data = get_context(conversation_id)
    last_tool = conversation_data.get("active_tool")
    context_history = conversation_data.get("history", [])

    additional_context = ""
    if last_tool == "ISO" and context_history:
        previous_messages = [
            f"Usuario: {entry['usersinput']} | Bot: {entry['systemoutput']}"
            for entry in context_history[-3:]
            if isinstance(entry, dict) and "usersinput" in entry and "systemoutput" in entry
        ]
        additional_context = "\n".join(previous_messages)

    messages = [
        {"role": "system", "content": iso_prompt},
        {"role": "system", "content": f"Historial relevante:\n{additional_context}"} if additional_context else {},
        {"role": "user", "content": user_question}
    ]

    token_estimate = len(iso_prompt.split())
    log_debug_event(
        tool="ISO",
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        step="Prompt Construction",
        input_data={"user_question": user_question},
        output_data={"token_estimate": token_estimate}
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[msg for msg in messages if msg],
            response_format={"type": "json_object"},
            timeout=40,
            temperature=1
        )

        raw_content = response.choices[0].message.content.strip()

        log_debug_event(
            tool="ISO",
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step="OpenAI Raw",
            input_data={"response_raw": raw_content}
        )

        if raw_content.startswith("```json") and raw_content.endswith("```"):
            raw_content = raw_content.removeprefix("```json").removesuffix("```").strip()
        elif raw_content.startswith("```") and raw_content.endswith("```"):
            raw_content = raw_content.removeprefix("```").removesuffix("```").strip()

        log_debug_event(
            tool="ISO",
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step="Backtick Handling",
            input_data={"raw_pre": response.choices[0].message.content.strip()},
            output_data={"raw_post": raw_content}
        )

        try:
            response_json = json.loads(raw_content)
            actual_response = response_json.get("respuesta", raw_content)
        except json.JSONDecodeError:
            logger.error(f"[ISOTool] Failed to parse OpenAI JSON response: {raw_content}")
            actual_response = "Lo siento, no entendí tu pregunta correctamente."

        log_debug_event(
            tool="ISO",
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step="Final Parsing",
            input_data={},
            output_data={"response": actual_response}
        )

        safe_messages = [
            {"role": "system", "content": f"[PROMPT:{ISO_PROMPT_FILE}]"},
            {"role": "user",   "content": user_question}
        ]

        # extrae sólo los campos primitivos que te importan
        usage = getattr(response, "usage", {})
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        elif hasattr(usage, "__dict__"):
            usage = usage.__dict__
        else:
            usage = {"raw": usage}

        log_ai_call(
            call_type       = "ISO Answer",
            model           = "gpt-4o-mini",
            provider        = "openai",
            messages        = safe_messages,
            response        = actual_response,
            token_usage     = usage,
            conversation_id = conversation_id,
            interaction_id  = interaction_id,
            prompt_file     = ISO_PROMPT_FILE,
            temperature     = 1
        )

        await log_ai_call_postgres(
            call_type       = "ISO Answer",
            model           = "gpt-4o-mini",
            provider        = "openai",
            messages        = safe_messages,
            response        = actual_response,
            token_usage     = usage,
            conversation_id = conversation_id,
            interaction_id  = interaction_id,
            prompt_file     = ISO_PROMPT_FILE,
            temperature     = 1,
        )

        add_to_context(
            conversation_id=conversation_id,
            active_tool="ISO",
            user_input=user_question,
            system_output=actual_response
        )

        log_interaction(
            userName=userName,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step_id=step_id,
            user_input=user_question,
            system_output=actual_response,
            classification="ISO",
            extra_info="ISO raw GPT data"
        )

        return ToolResponse(
            classification="ISO",
            response=actual_response
        ).model_dump()

    except Exception as e:
        error_msg = f"Error in ISO tool: {str(e)}"
        logger.error(error_msg)

        log_debug_event(
            tool="ISO",
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step="EXCEPTION",
            input_data={"user_question": user_question},
            output_data={"error": error_msg}
        )

        log_interaction(
            userName=userName,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            step_id=step_id,
            user_input=user_question,
            system_output=error_msg,
            classification="ISO",
            extra_info="ERROR"
        )
        return make_error_response(error_msg)

@router.post("/iso/search")
async def execute_iso_search(inputs, conversation_id, userName):
    request_data = ISORequest(
        conversation_id=conversation_id,
        user_question=inputs.get("iso_question", "").strip(),
        step_id=1
    )
    return await iso_chat(request_data, userName)
