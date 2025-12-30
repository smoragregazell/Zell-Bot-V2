from utils.llm_provider import chat_completion
from utils.llm_config import get_llm_config
import os
import json
import logging
import requests
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv

from utils.tool_response import ToolResponse, make_error_response
from utils.logs import log_ai_call_postgres, log_interaction, log_ai_call
from utils.contextManager.context_handler import add_to_context, get_interaction_id
from utils.debug_logger import log_debug_event
from utils.prompt_loader import load_latest_prompt
from utils.tool_registry import register_tool

load_dotenv()

router = APIRouter()

logging.basicConfig(
    filename="logs/query_tool.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

debug_logger = logging.getLogger("debug_logger")
debug_logger.setLevel(logging.DEBUG)
dh = logging.FileHandler("logs/debug_tools.log")
dh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"))
if not debug_logger.handlers:
    debug_logger.addHandler(dh)

try:
    QUERY_PROMPT,    QUERY_PROMPT_FILE    = load_latest_prompt("Query",          "queryprompt",         with_filename=True)
    ANALYSIS_PROMPT, ANALYSIS_PROMPT_FILE = load_latest_prompt("AnalisisQuery", "analisisqueryprompt", with_filename=True)
except Exception as e:
    logging.error(f"❌ Error cargando prompts de Query: {e}")
    QUERY_PROMPT, ANALYSIS_PROMPT = None, None
    QUERY_PROMPT_FILE, ANALYSIS_PROMPT_FILE = "N/A", "N/A"

if not (QUERY_PROMPT and ANALYSIS_PROMPT):
    logging.warning("⚠️ One or more query-related prompts could not be loaded!")

class QueryRequest(BaseModel):
    conversation_id: str
    user_question:  str
    step_id:        int = 1

# ─────────────────────────────────────────────
@router.post("/query_tool")
@register_tool("Búsqueda de Query")
async def execute_query(inputs, conversation_id, interaction_id=None, userName=None, step_id=1):
    user_question = inputs.get("user_question", "").strip()
    logging.info(f"📥 New query_tool call | conversation_id={conversation_id}, question={user_question}")

    print("🧪 Revisando interaction_id inicial:", interaction_id)

    if not user_question:
        return make_error_response("La pregunta no puede estar vacía.")
    print("🧪 interaction_id inicial:", interaction_id, type(interaction_id))
    if interaction_id is None:
        interaction_id = get_interaction_id(conversation_id)
        try:
            interaction_id = int(interaction_id)
        except Exception as e:
            raise ValueError(f"❌ interaction_id no es entero válido: {interaction_id} | Error: {e}")

    log_interaction( userName, conversation_id, interaction_id, step_id,
                    user_question, "Generating SQL Query", "Búsqueda de Query")

    # 1️⃣ Generar la consulta SQL
    sql_response = await generate_sql_query(user_question, conversation_id, interaction_id)
    if not isinstance(sql_response, dict):
        return make_error_response("No se pudo generar la consulta SQL.")

    sql_query       = sql_response.get("sql_query", "").strip()
    sql_description = sql_response.get("mensaje", "")

    if not sql_query or sql_query.lower() == "no viable":
        return handle_invalid_sql(user_question, conversation_id, interaction_id, step_id)

    # 2️⃣ Ejecutar consulta en Zell
    api_data, status_code, _, _ = fetch_query_results(sql_query)
    if api_data is None:
        return make_error_response("Error llamando API de Zell.")
    if isinstance(api_data, list) and not api_data:
        return ToolResponse(classification="Búsqueda de Query",
                            response="No hay resultados para esa consulta.").model_dump()

    # 3️⃣ Interpretar resultados
    response_text = await process_query_results(
        api_data, user_question, sql_query,
        conversation_id, interaction_id
    )

    # 4️⃣ Guarda contexto
    add_to_context(
        conversation_id, "Búsqueda de Query", user_question, response_text,
        {"sql_query": sql_query, "query_description": sql_description, "query_results": api_data}
    )

    return ToolResponse(classification="Búsqueda de Query", response=response_text).model_dump()

# ─────────────────────────────────────────────
def handle_invalid_sql(user_question, conversation_id, interaction_id, step_id):
    msg = ("No pude generar una consulta basada en tu pregunta. Puede deberse a que:\n"
           "🔹 Falta información o la pregunta es ambigua.\n"
           "🔹 Solicitas datos a los que no tengo acceso.\n"
           "🔹 Los datos no existen en la base.\n"
           "Intenta reformularla o agrega más detalle.")
    log_interaction(userName, conversation_id, interaction_id, step_id,
                    user_question, "Query Not Viable", "Búsqueda de Query")
    return ToolResponse(classification="Búsqueda de Query", response=msg).model_dump()

# ─────────────────────────────────────────────
async def generate_sql_query(user_question, conversation_id, interaction_id):
    
    messages = [
        {"role": "system", "content": QUERY_PROMPT},
        {"role": "user",   "content": user_question}
    ]
    try:
        llm_resp = await chat_completion(            # 👈 wrapper
                    messages,
                    tool="QUERY_SQL",                        # nombre libre
                    response_format={"type": "json_object"},
                    temperature=0,
                    timeout=30
                )
        
        result = json.loads(
                llm_resp["choices"][0]["message"]["content"].strip()
                )

        # Log con sólo el nombre del prompt
        safe_messages = [
            {"role": "system", "content": f"[PROMPT:{QUERY_PROMPT_FILE}]"},
            {"role": "user",   "content": user_question}
        ]
        cfg = get_llm_config("QUERY")              # modelo / proveedor reales

        log_ai_call(                               # usa tu helper preferido
            call_type      = "SQL Generation",
            model          = cfg["model"],         # modelo real (openai o deepseek)
            provider       = cfg["provider"].value,# nuevo campo en el CSV
            messages       = safe_messages,
            response       = result,
            token_usage    = llm_resp.get("usage", {}),   # ▶︎  cambio: usa llm_resp
            conversation_id= conversation_id,
            interaction_id = interaction_id,
            prompt_file    = QUERY_PROMPT_FILE,
            temperature    = 0
        )

        await log_ai_call_postgres(
            call_type      = "SQL Generation",
            model          = cfg["model"],         # modelo real (openai o deepseek)
            provider       = cfg["provider"].value,# nuevo campo en el CSV
            messages       = safe_messages,
            response       = result,
            token_usage    = llm_resp.get("usage", {}),   # ▶︎  cambio: usa llm_resp
            conversation_id= conversation_id,
            interaction_id = interaction_id,
            prompt_file    = QUERY_PROMPT_FILE,
            temperature    = 0
        )
        return result

    except Exception as e:
        logging.error(f"❌ Exception during SQL generation: {e}")
        return None

# ─────────────────────────────────────────────
def fetch_query_results(sql_query):
    api_url = f"https://tickets.zell.mx/apilink/info?query={sql_query}"
    headers = {
        "x-api-key": os.getenv("ZELL_API_KEY"),
        "user":      os.getenv("ZELL_USER"),
        "password":  os.getenv("ZELL_PASSWORD"),
        "action":    "7777"
    }
    try:
        r = requests.get(api_url, headers=headers)
        r.raise_for_status()
        return r.json(), r.status_code, {}, headers["action"]
    except Exception as e:
        logging.error(f"❌ Zell API error: {e}")
        return None, 500, {}, headers["action"]

# ─────────────────────────────────────────────
async def process_query_results(api_data, user_question, sql_query,
                          conversation_id, interaction_id):
    payload = (
        f"Pregunta del usuario: {user_question}\n"
        f"Consulta SQL ejecutada: {sql_query}\n"
        f"{json.dumps(api_data, indent=2, default=str)}"
    )
    
    messages = [
        {"role": "system", "content": ANALYSIS_PROMPT},
        {"role": "user",   "content": payload}
    ]
    try:
        llm_resp = await chat_completion(
            messages,
            tool="QUERY_ANALYSIS",
            response_format={"type": "json_object"},
            temperature=0.3,
            timeout=30
        )
        result = json.loads(
            llm_resp["choices"][0]["message"]["content"].strip()
        ).get("respuesta")

        safe_messages = [
            {"role": "system", "content": f"[PROMPT:{ANALYSIS_PROMPT_FILE}]"},
            {"role": "user",   "content": "[DATA]"}
        ]

        cfg = get_llm_config("QUERY")

        log_ai_call(
            call_type      = "Result Analysis",
            model          = cfg["model"],
            provider       = cfg["provider"].value,
            messages       = safe_messages,
            response       = result,
            token_usage    = llm_resp.get("usage", {}),
            conversation_id= conversation_id,
            interaction_id = interaction_id,
            prompt_file    = ANALYSIS_PROMPT_FILE,
            temperature    = 0.3
        )

        await log_ai_call_postgres(
            call_type      = "Result Analysis",
            model          = cfg["model"],
            provider       = cfg["provider"].value,
            messages       = safe_messages,
            response       = result,
            token_usage    = llm_resp.get("usage", {}),
            conversation_id= conversation_id,
            interaction_id = interaction_id,
            prompt_file    = ANALYSIS_PROMPT_FILE,
            temperature    = 0.3
            )
        
        return result

    except Exception as e:
        logging.error(f"❌ Exception during GPT result analysis: {e}")
        return f"Error procesando los resultados: {e}"