# 👉 wrapper que decide a qué proveedor pegarle
from Tools.continuation_tool import TicketRequest
from utils.llm_provider import chat_completion
from utils.llm_config import get_llm_config
import os
import json
import logging
import httpx
from pydantic import BaseModel

from utils.logs import (
    log_interaction,
    log_ai_call,
    log_zell_api_call,
    log_ai_call_postgres
)
from utils.debug_logger import log_debug_event
from utils.contextManager.context_handler import (
    add_to_context,
    get_context,
    get_interaction_id
)
from utils.tool_response import ToolResponse, make_error_response
from utils.tool_registry import register_tool
from utils.prompt_loader import load_latest_prompt


logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# PROMPT BASE
# ──────────────────────────────────────────────────────────────
TICKET_AI_PROMPT, TICKET_PROMPT_FILE = load_latest_prompt(
    "Ticket",          # carpeta Prompts/
    "ticketprompt",    # prefijo
    with_filename=True
)
if not TICKET_AI_PROMPT:
    logger.warning("⚠️ ticketprompt no fue cargado!")

# ──────────────────────────────────────────────────────────────
# LÓGICA PARA EXTRAER EL TICKET DEL API DE ZELL
# ──────────────────────────────────────────────────────────────
def get_ticket_data(ticket_number, conversation_id):
    api_url = f"https://tickets.zell.mx/apilink/info?source=1&sourceid={ticket_number}"
    api_headers = {
        "x-api-key": os.getenv("ZELL_API_KEY", ""),
        "user":     os.getenv("ZELL_USER", ""),
        "password": os.getenv("ZELL_PASSWORD", ""),
        "action":   "5001"
    }
    interaction_id = get_interaction_id(conversation_id)
    sanitized_headers = {k: v for k, v in api_headers.items() if k.lower() != "password"}

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(api_url, headers=api_headers)

        raw_response_text = response.text
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            return {"error": "La API respondió con un formato no válido", "raw_response": raw_response_text}

        if isinstance(data, dict) and data.get("code") == 145125:
            return {"error": "La API no encontró el ticket solicitado.", "raw": data}

        log_zell_api_call(
            action="Fetch Ticket Data",
            api_action="5001",
            endpoint=api_url,
            request_data={"ticket_number": ticket_number},
            response_data=data,
            status_code=response.status_code,
            headers=sanitized_headers,
            conversation_id=conversation_id,
            interaction_id=interaction_id
        )

        # Formato esperado → asegúrate de regresar dict con ticket_id
        if isinstance(data, dict) and "IdTicket" in data:
            data["ticket_id"] = data["IdTicket"]
            return data
        if isinstance(data, list) and data and "IdTicket" in data[0]:
            d = data[0]
            d["ticket_id"] = d["IdTicket"]
            return d

        return {"error": "Formato de respuesta de API inesperado", "data": data}

    except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
        return {"error": f"Error al obtener datos del ticket: {str(e)}"}

# ──────────────────────────────────────────────────────────────
# LLAMADA AL LLM (proveedor configurable)
# ──────────────────────────────────────────────────────────────
async def query_ticket_llm(ticket_data, user_question, conversation_id, userName):
    """
    Construye el prompt y dispara la llamada usando chat_completion(),
    que ya decide si usa OpenAI, DeepSeek, Anthropic, etc.
    """
    ticket_data_str = json.dumps(ticket_data, ensure_ascii=False, indent=2)
    ticket_prompt   = TICKET_AI_PROMPT.replace("{ticket_data}", ticket_data_str)\
                                      .replace("{user_question}", user_question)

    # agrega historial corto si la conversación ya estaba en ticket tool
    conv_ctx = get_context(conversation_id)
    if conv_ctx.get("active_tool") == "Consulta de Tickets":
        history = conv_ctx.get("history", [])[-3:]
        extra   = "\n".join(
            f"Usuario: {h['usersinput']}\nBot: {h['systemoutput']}"
            for h in history if isinstance(h, dict)
        )
        if extra:
            ticket_prompt += f"\nHistorial relevante:\n{extra}"

    messages = [
        {"role": "system", "content": "Eres un asistente de soporte que responde sobre tickets."},
        {"role": "user",   "content": ticket_prompt}
    ]

    # 🚀 llamada unificada
    resp = await chat_completion(messages, temperature=0.3, max_tokens=1000)
    raw  = resp["choices"][0]["message"]["content"].strip()

    # intenta parsear JSON si el prompt lo pide
    try:
        if raw.startswith("```json"):
            raw = raw.removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(raw)
        ai_response = parsed.get("respuesta", raw)
    except Exception:
        ai_response = raw

    from utils.llm_config import get_llm_config
    cfg           = get_llm_config("TICKET")   # lee modelo/proveedor efectivos
    real_model    = cfg["model"]
    real_provider = cfg["provider"].value      # "openai" o "deepseek"
    token_usage   = resp.get("usage", {})  # dict con los tokens

    # log limpio
    safe_msgs = [
        {"role": "system", "content": f"[PROMPT:{TICKET_PROMPT_FILE}]"},
        {"role": "user",   "content": user_question}
    ]
    interaction_id = get_interaction_id(conversation_id)

    log_ai_call(
        call_type="Ticket Query",
        model=real_model,
        provider=real_provider,
        messages=safe_msgs,
        response=ai_response,
        token_usage=token_usage,
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        prompt_file=TICKET_PROMPT_FILE,
        temperature=0.3
    )

    await log_ai_call_postgres(
        call_type="Ticket Query",
        model=real_model,
        provider=real_provider,
        messages=json.dumps(safe_msgs, ensure_ascii=False),
        response=json.dumps(ai_response, ensure_ascii=False),
        token_usage=token_usage,
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        prompt_file=TICKET_PROMPT_FILE,
        temperature=0.3
    )

    return ai_response

# ──────────────────────────────────────────────────────────────
# ENDPOINT / TOOL
# ──────────────────────────────────────────────────────────────
@register_tool("Consulta de Tickets")
async def execute_ticket_query(inputs, conversation_id, interaction_id, userName, step_id=1):
    ticket_number = str(inputs.get("ticket_number", "")).strip()
    user_question = inputs.get("user_question", "").strip()

    if not ticket_number:
        return make_error_response("Falta el número del ticket.")

    if interaction_id is None:
        interaction_id = get_interaction_id(conversation_id)

    # 1. Obtén datos del ticket
    ticket_data = get_ticket_data(ticket_number, conversation_id)
    if "error" in ticket_data:
        return make_error_response(ticket_data["error"])

    # 2. Pregunta al LLM
    ai_response = await query_ticket_llm(ticket_data, user_question, conversation_id, userName)
    if isinstance(ai_response, dict) and ai_response.get("error"):
        return make_error_response(ai_response["error"])

    # 3. Guarda contexto + logs
    add_to_context(
        conversation_id=conversation_id,
        active_tool="Consulta de Tickets",
        user_input=user_question,
        system_output=ai_response,
        data_used={"ticket_data": ticket_data}
    )

    log_interaction(
        userName=userName,
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        step_id=step_id,
        user_input=user_question,
        system_output=ai_response,
        classification="Consulta de Tickets",
        extra_info="Ticket Tool"
    )

    if isinstance(ai_response, dict):
        # 🎯 Formatear salida como texto plano para el widget
        lines = []
        if "IdTicket" in ai_response:
            lines.append(f"* IdTicket: {ai_response['IdTicket']}")
        if "Cliente" in ai_response:
            lines.append(f"| Cliente: {ai_response['Cliente']}")
        if "Titulo" in ai_response:
            lines.append(f"| Titulo: {ai_response['Titulo']}")
        if "FechaCreado" in ai_response:
            lines.append(f"| FechaCreado: {ai_response['Creado']}")
        if "DetectadoPor" in ai_response:
            lines.append(f"| DetectadoPor: {ai_response['DetectadoPor']}")
        if "Estatus" in ai_response:
            lines.append(f"| Estatus: {ai_response['Estatus']}")
        if "Resumen" in ai_response:
            lines.append(f"\n{ai_response['Resumen']}")

        ai_response = "\n".join(lines)


    return ToolResponse(
        classification="Consulta de Tickets",
        response=ai_response
    ).model_dump()
