from utils.llm_provider import chat_completion
from utils.llm_config import get_llm_config  # o  config.llm_config
import os
import json
import logging
import csv
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request
from pydantic import BaseModel

from utils.logs import log_interaction, log_ai_call, log_interaction_sqlite, log_to_postgres, log_ai_call_postgres
from utils.tool_response import ToolResponse, make_error_response
from utils.contextManager.short_term_memory import (add_to_short_term_memory,
                                                    get_short_term_memory)
from utils.contextManager.context_handler import (
    get_or_create_conversation_id, get_interaction_id, set_user_info)
from utils.tool_registry import get_tool_by_classification
from utils.token_verifier import verificar_token
from utils.prompt_loader import load_latest_prompt

router = APIRouter()

CONV_LOG_PATH = "logs/conversation_sessions.csv"
os.makedirs("logs", exist_ok=True)

if not os.path.isfile(CONV_LOG_PATH):
    with open(CONV_LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["conversation_id", "token", "user_email", "timestamp_inicio"])


def registrar_conversacion_si_no_existe(conversation_id, token, userName):
    ya_registrado = False
    registros = []
    if os.path.isfile(CONV_LOG_PATH):
        with open(CONV_LOG_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                registros.append(row)
                if row["conversation_id"] == conversation_id:
                    ya_registrado = True
    if not ya_registrado:
        with open(CONV_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                conversation_id, token, userName,
                datetime.now(ZoneInfo("America/Mexico_City"))
            ])


class MessageRequest(BaseModel):
    conversation_id: str
    user_message: str
    zToken: str
    userName: str
    step_id: int = 1
    reclassified: bool = False


class ClassificationResponse(BaseModel):
    classification: str
    confidence_score: float
    inputs: dict
    missing_inputs: list
    follow_up_prompt: str


logging.basicConfig(filename="logs/classifier_errors.log",
                    level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def load_classification_prompt():
    try:
        return load_latest_prompt(
            "Clasificador",  # carpeta Prompts raíz
            "clasificadorprompt",  # archivo sin carpeta
            with_filename=True)
    except Exception as e:
        logging.error(f"❌ Error loading classification prompt: {e}")
        return None, "N/A"


CLASS_PROMPT_FULL, CLASS_PROMPT_FILE = load_classification_prompt()
if not CLASS_PROMPT_FULL:
    logging.warning("⚠️ Clasificator_prompt no fue cargado!")
#print(f"🔍 [DEBUG] Clasificador usando prompt: {CLASS_PROMPT_FILE}")


@router.post("/classify")
async def classify_message(req: MessageRequest):

    #validation_result = verificar_token(req.zToken)
    #if not validation_result["continuar"]:

    #msg = (
    #"Lo siento, parece que el token que estás utilizando está expirado. Intenta recargar el widget."
    #if "expirado" in validation_result["motivo"].lower()
    #else "Lo siento, el acceso no está autorizado. Contacta a tu proveedor de servicios para más información."
    #)
    #return {
    #"conversation_id": req.conversation_id,
    #"interaction_id": 0,
    #"response": msg,
    #"error": validation_result["motivo"]
    #}

    # Si el validador está comentado, crea un resultado dummy
    validation_result = verificar_token(req.zToken)
    # si tu verificador no devuelve el userName, lo coges del req:
    userName = validation_result.get("userName", req.userName)
    conversation_id = get_or_create_conversation_id(req.conversation_id)
    interaction_id = get_interaction_id(conversation_id)

    registrar_conversacion_si_no_existe(conversation_id, req.zToken, userName)
    set_user_info(conversation_id, userName)

    user_message = req.user_message.strip()
    step_id = req.step_id
    inputs = req.model_dump()

    try:
        add_to_short_term_memory(conversation_id, user_message)
        memory = get_short_term_memory(conversation_id)
        structured_input = {
            "user_last_message":
            memory.get("user_last_message", ""),
            "bot_last_response":
            memory.get("bot_last_response", ""),
            "second_to_last_interaction":
            memory.get("second_to_last_interaction", ""),
            "third_to_last_interaction":
            memory.get("third_to_last_interaction", "")
        }

        if req.reclassified:
            structured_input["reclassified"] = True

        messages = [{
            "role": "system",
            "content": f"[PROMPT:{CLASS_PROMPT_FILE}]"
        }, {
            "role": "system",
            "content": CLASS_PROMPT_FULL
        }, {
            "role": "user",
            "content": json.dumps(structured_input, ensure_ascii=False)
        }]

        cfg = get_llm_config("CLASSIFIER")
        logging.info(f"▶ Usando modelo: {cfg['model']} para TOOL=TU_TOOL")
        real_model = cfg["model"]
        logging.info(f"⚙️ CLASSIFIER usando model={real_model}")

        response = await chat_completion(
            messages,
            tool="CLASSIFIER",
            timeout=30,
            temperature=0,
            response_format={"type": "json_object"})

        raw_content = response["choices"][0]["message"]["content"].strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content.removeprefix("```json").removesuffix(
                "```").strip()

        try:
            data = json.loads(raw_content)
            if not isinstance(data, dict) or "classification" not in data:
                return make_error_response(
                    "Respuesta no es un JSON válido o le falta 'classification'."
                )
        except Exception as e:
            logging.error(
                f"❌ Error parsing classification response: {e}\nRaw:\n{raw_content}"
            )
            return make_error_response(
                "La respuesta del modelo no fue válida. Intenta de nuevo.")

        try:
            validated = ClassificationResponse(**data)
            data = validated.model_dump()
        except Exception as e:
            logging.error(
                f"❌ Error validando estructura de clasificación: {e}")
            return make_error_response("Respuesta mal formada del modelo.")

        classification = data["classification"]
        confidence_score = data["confidence_score"]
        inputs = data.get("inputs", {})
        missing_inputs = data.get("missing_inputs", [])
        follow_up_prompt = data.get("follow_up_prompt", "")

        # ── Log seguro ──
        safe_messages = [{
            "role": "system",
            "content": f"[PROMPT:{CLASS_PROMPT_FILE}]"
        }, {
            "role":
            "user",
            "content":
            json.dumps(structured_input, ensure_ascii=False)[:400]
        }]

        log_ai_call(
            call_type="Classification",
            model=real_model,
            provider=cfg["provider"].value,  # "openai" o "deepseek"
            messages=safe_messages,
            response=data,
            token_usage=response.get("usage", {}),
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            prompt_file=CLASS_PROMPT_FILE,
            temperature=0,
            confidence_score=confidence_score)

        await log_ai_call_postgres(
            call_type="Classification",
            model=real_model,
            provider=cfg["provider"].value,  # "openai" o "deepseek"
            messages=safe_messages,
            response=data,
            token_usage=response.get("usage", {}),
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            prompt_file=CLASS_PROMPT_FILE,
            temperature=0,
            confidence_score=confidence_score)

    except Exception as e:
        print("DEBUG‑EXCEPTION >>", e)
        logging.error(f"❌ Error clasificando mensaje: {str(e)}")
        log_interaction(userName=userName,
                        conversation_id=conversation_id,
                        interaction_id=interaction_id,
                        step_id=step_id,
                        user_input=user_message,
                        system_output="Error en clasificación",
                        classification="ERROR",
                        extra_info="OpenAI Classification Failure")
        return make_error_response(
            "Hubo un problema al procesar tu solicitud. Inténtalo más tarde.")

    log_interaction(userName=userName,
                    conversation_id=conversation_id,
                    interaction_id=interaction_id,
                    step_id=step_id,
                    user_input=user_message,
                    system_output=json.dumps(data, ensure_ascii=False),
                    classification=classification,
                    extra_info="Classifier Response")

    log_interaction_sqlite(userName=userName,
                           conversation_id=conversation_id,
                           user_input=user_message,
                           system_output=json.dumps(data, ensure_ascii=False),
                           classification=classification,
                           extra_info="Classifier Response",
                           timestamp=datetime.now(
                               ZoneInfo("America/Mexico_City")))

    # Esto dentro de tu función classify_message
    await log_to_postgres({
        "conversation_id":
        conversation_id,
        "user_name":
        userName,
        "user_input":
        user_message,
        "system_output":
        json.dumps(data, ensure_ascii=False),
        "classification":
        classification,
        "extra_info":
        "Classifier Response",
        "timestamp":
        datetime.now(ZoneInfo("America/Mexico_City"))
    })

    if classification in ["Clasificación Incierta", "No Relacionado"
                          ] or missing_inputs:
        return {
            "conversation_id": conversation_id,
            "interaction_id": interaction_id,
            "classification": classification,
            "response": follow_up_prompt
            or "Lo siento, no entendí tu pregunta."
        }

    try:
        tool_fn = get_tool_by_classification(classification)
        if not tool_fn:
            return make_error_response(
                f"No se encontró herramienta para: {classification}")

        # Mapa explícito según clasificación
        if classification == "ISO":
            from Tools.iso_tool import ISORequest
            iso_request_obj = ISORequest(conversation_id=conversation_id,
                                         user_question=inputs.get(
                                             "iso_question", req.user_message),
                                         step_id=step_id)
            tool_response = await tool_fn(iso_request_obj, userName)

        elif classification == "Pregunta Continuada":
            tool_response = await tool_fn(inputs, conversation_id, userName,
                                          interaction_id)

        elif classification == "Búsqueda Semántica":
            tool_response = tool_fn(inputs, conversation_id)

        else:
            tool_response = await tool_fn(inputs, conversation_id,
                                          interaction_id, userName, step_id)

        # ── Para el resto de herramientas, validación estándar ──
        validated = ToolResponse.model_validate(tool_response)
        return {
            "conversation_id": conversation_id,
            "interaction_id": interaction_id,
            "classification": validated.classification,
            "response": validated.response
        }

    except Exception as e:
        logging.error(
            f"❌ Error ejecutando herramienta ({classification}): {str(e)}")
        log_interaction(userName=userName,
                        conversation_id=conversation_id,
                        interaction_id=interaction_id,
                        step_id=step_id + 1,
                        user_input="Error while calling tool",
                        system_output="Error en ejecución de herramienta",
                        classification="ERROR",
                        extra_info=f"Tool call error for {classification}")
        return make_error_response(
            "Hubo un problema ejecutando la herramienta. Inténtalo más tarde.")
