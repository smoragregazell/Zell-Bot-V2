from utils.ai_calls import responses_create
from utils.llm_config import get_llm_config
from utils.llm_provider import chat_completion
import os
import json
import logging
import requests
from dotenv import load_dotenv

from utils.logs import log_ai_call
# TODO: Comentado temporalmente - trabajar en Postgres después
# from utils.logs import log_ai_call_postgres
from utils.prompt_loader import load_latest_prompt

load_dotenv()

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

# ─────────────────────────────────────────────
async def generate_sql_query(user_question, conversation_id, interaction_id):
    # Verificar que el prompt esté cargado
    if not QUERY_PROMPT:
        logging.error("❌ QUERY_PROMPT no está cargado!")
        return None
    
    try:
        logging.info(f"🔍 Calling responses_create with tool=QUERY, user_question length={len(user_question)}")
        
        # Usar Responses API
        # instructions = QUERY_PROMPT (el prompt completo)
        # input = mensaje del usuario
        response = await responses_create(
            instructions=QUERY_PROMPT + "\n\nIMPORTANTE: Responde SOLO en formato JSON con la estructura: {\"sql_query\": \"...\", \"mensaje\": \"...\"}",
            input=[{"role": "user", "content": user_question}],
            tool="QUERY",  # Usa configuración QUERY (gpt-5-mini)
        )
        
        # Responses API retorna un objeto con output_text
        if not response or not hasattr(response, 'output_text'):
            logging.error(f"❌ Invalid response from responses_create: {response}")
            return None
        
        content = response.output_text.strip()
        logging.info(f"✅ Got response, content length={len(content)}")
        
        # Limpiar el contenido si viene con markdown
        if content.startswith("```json"):
            content = content.removeprefix("```json").removesuffix("```").strip()
        elif content.startswith("```"):
            content = content.removeprefix("```").removesuffix("```").strip()
        
        result = json.loads(content)

        # Log con sólo el nombre del prompt
        safe_messages = [
            {"role": "system", "content": f"[PROMPT:{QUERY_PROMPT_FILE}]"},
            {"role": "user",   "content": user_question}
        ]
        cfg = get_llm_config("QUERY")              # modelo / proveedor reales

        # Obtener token usage si está disponible (Responses API puede tenerlo diferente)
        token_usage = {}
        if hasattr(response, 'usage'):
            token_usage = response.usage
        elif hasattr(response, 'token_usage'):
            token_usage = response.token_usage
        
        log_ai_call(                               # usa tu helper preferido
            call_type      = "SQL Generation",
            model          = cfg["model"],         # modelo real (openai o deepseek)
            provider       = cfg["provider"].value,# nuevo campo en el CSV
            messages       = safe_messages,
            response       = result,
            token_usage    = token_usage if isinstance(token_usage, dict) else {},
            conversation_id= conversation_id,
            interaction_id = interaction_id,
            prompt_file    = QUERY_PROMPT_FILE,
            temperature    = 0
        )

        # TODO: Comentado temporalmente - trabajar en Postgres después
        # await log_ai_call_postgres(
        #     call_type      = "SQL Generation",
        #     model          = cfg["model"],         # modelo real (openai o deepseek)
        #     provider       = cfg["provider"].value,# nuevo campo en el CSV
        #     messages       = safe_messages,
        #     response       = result,
        #     token_usage    = token_usage if isinstance(token_usage, dict) else {},
        #     conversation_id= conversation_id,
        #     interaction_id = interaction_id,
        #     prompt_file    = QUERY_PROMPT_FILE,
        #     temperature    = 0
        # )
        return result

    except json.JSONDecodeError as je:
        logging.error(f"❌ JSON decode error: {je}")
        try:
            content_preview = llm_resp.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:500]
            logging.error(f"   Response content: {content_preview}")
        except:
            logging.error(f"   Could not extract response content")
        return None
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"❌ Exception during SQL generation: {e}\n{error_details}")
        logging.error(f"   User question: {user_question[:200]}")
        logging.error(f"   Exception type: {type(e).__name__}")
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
