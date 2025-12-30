import httpx, json, openai
from utils.llm_config import get_llm_config

# utils/llm_client.py
def _clean_params(params: dict):
    params.pop("tool", None)            # <- quita basura
    return params

async def chat_completion(messages, *, tool=None, **params):
    """
    Hace una llamada al proveedor configurado.
    Uso: await chat_completion(msgs, temperature=0.3, max_tokens=1000)
    Devuelve el dict JSON completo de la respuesta.
    """
    cfg = get_llm_config(tool)

    # Normaliza kwargs
    body = {
        "model":      cfg["model"],
        "messages":   messages,
        **params
    }

    # OPENAI: usa sdk porque da manejo automático de reintentos y streaming
    if cfg["provider"].value == "openai":
        client = openai.OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        resp   = client.chat.completions.create(**body)
        return resp.model_dump()

    # Otros proveedores (DeepSeek / Anthropic) con API “tipo‑OpenAI”
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json"
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{cfg['base_url']}/chat/completions",
                              headers=headers, json=body)
        r.raise_for_status()
        return r.json()
