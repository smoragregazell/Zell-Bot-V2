"""
Centraliza las llamadas a OpenAI.
Soporta tanto chat.completions como responses API.
"""
import os
from typing import Any, Dict, List, Optional
from openai import OpenAI
from utils.llm_config import get_llm_config


def get_openai_client(tool: Optional[str] = None) -> OpenAI:
    """
    Obtiene un cliente de OpenAI configurado según el tool.
    """
    cfg = get_llm_config(tool)
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])


async def chat_completion(
    messages: List[Dict[str, Any]],
    *,
    tool: Optional[str] = None,
    **params
) -> Dict[str, Any]:
    """
    Llamada tradicional a chat.completions.create (async)
    
    Args:
        messages: Lista de mensajes en formato OpenAI
        tool: Nombre del tool para configuración (ej: "QUERY", "TICKET")
        **params: Parámetros adicionales (temperature, max_tokens, etc.)
    
    Returns:
        Dict con la respuesta completa de OpenAI
    """
    import httpx
    
    cfg = get_llm_config(tool)
    
    body = {
        "model": cfg["model"],
        "messages": messages,
        **params
    }
    
    # OPENAI: usa sdk porque da manejo automático de reintentos y streaming
    if cfg["provider"].value == "openai":
        client = get_openai_client(tool)
        resp = client.chat.completions.create(**body)
        return resp.model_dump()
    
    # Otros proveedores (DeepSeek / Anthropic) con API "tipo‑OpenAI"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{cfg['base_url']}/chat/completions",
                              headers=headers, json=body)
        r.raise_for_status()
        return r.json()


async def responses_create(
    model: Optional[str] = None,
    instructions: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    input: Optional[List[Dict[str, Any]]] = None,
    previous_response_id: Optional[str] = None,
    tool: Optional[str] = None,
    **params
) -> Any:
    """
    Llamada a Responses API (client.responses.create)
    
    Args:
        model: Modelo a usar (si no se especifica, usa el del tool o V2_MODEL)
        instructions: Instrucciones del sistema
        tools: Lista de tools disponibles
        input: Lista de mensajes/inputs
        previous_response_id: ID de respuesta anterior para continuar contexto
        tool: Nombre del tool para configuración de API key
        **params: Parámetros adicionales
    
    Returns:
        Response object de OpenAI Responses API
    """
    # Si no se especifica model, usar el del tool o V2_MODEL
    if model is None:
        if tool:
            cfg = get_llm_config(tool)
            model = cfg["model"]
        else:
            model = os.getenv("V2_MODEL", "gpt-5-mini")
    
    import asyncio
    
    client = get_openai_client(tool)
    
    # Construir parámetros
    call_params = {
        "model": model,
        **params
    }
    
    if instructions is not None:
        call_params["instructions"] = instructions
    if tools is not None:
        call_params["tools"] = tools
    if input is not None:
        call_params["input"] = input
    if previous_response_id is not None:
        call_params["previous_response_id"] = previous_response_id
    
    # Ejecutar en thread separado para no bloquear (el SDK de OpenAI es síncrono)
    return await asyncio.to_thread(client.responses.create, **call_params)

