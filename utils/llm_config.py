import os
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class LLMProvider(str, Enum):
    OPENAI   = "openai"
    DEEPSEEK = "deepseek"

# valores globales
GLOBAL_PROVIDER   = os.getenv("LLM_PROVIDER", "openai")
GLOBAL_OPENAI    = os.getenv("OPENAI_MODEL", "gpt-4o")
GLOBAL_DEEPSEEK  = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
GLOBAL_KEY_OPENAI   = os.getenv("OPENAI_API_KEY")
GLOBAL_KEY_DEEPSEEK = os.getenv("DEEPSEEK_API_KEY")

def _pick_env(varname: str) -> str | None:
    v = os.getenv(varname)
    return v.strip() if v and v.strip() else None

def get_llm_config(tool: str | None = None):
    """
    1) Mira si hay override de proveedor para la herramienta (e.g. CLASSIFIER_LLM_PROVIDER).
    2) Si existe, lo usa; si no, cae al global.
    3) Igual para modelo y api_key.
    """
    # construye nombres de variable en UPPER
    t = tool.upper() if tool else ""
    # override de proveedor: e.g. CLASSIFIER_LLM_PROVIDER
    override_provider = _pick_env(f"{t}_LLM_PROVIDER")
    provider = LLMProvider(override_provider) if override_provider else LLMProvider(GLOBAL_PROVIDER)

    # override de modelo según proveedor
    if provider == LLMProvider.OPENAI:
        # Forzar gpt-5-mini para QUERY tool
        if tool and tool.upper() == "QUERY":
            model = _pick_env(f"{t}_OPENAI_MODEL") or "gpt-5-mini"
        else:
            model = _pick_env(f"{t}_OPENAI_MODEL") or GLOBAL_OPENAI
        api_key = _pick_env(f"{t}_OPENAI_API_KEY") or GLOBAL_KEY_OPENAI
        base_url = "https://api.openai.com/v1"
    else:
        model = _pick_env(f"{t}_DEEPSEEK_MODEL") or GLOBAL_DEEPSEEK
        api_key = _pick_env(f"{t}_DEEPSEEK_API_KEY") or GLOBAL_KEY_DEEPSEEK
        base_url = "https://api.deepseek.com/v1"

    return {
        "provider": provider,
        "model":    model,
        "api_key":  api_key,
        "base_url": base_url
    }
