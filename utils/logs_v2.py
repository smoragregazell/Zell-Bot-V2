"""
Sistema de logging para chat_v2.
Maneja logs de interacciones y uso de tokens/costos.
"""
import os
import csv
from typing import Any, Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Archivos de log ---
CHAT_V2_LOG_FILE = os.path.join("logs", "chat_v2_interactions.csv")
TOKEN_USAGE_LOG_FILE = os.path.join("logs", "chat_v2_token_usage.csv")

# --- Precios de modelos (por millón de tokens) ---
# Fuente: https://openai.com/api/pricing/
MODEL_PRICING = {
    "gpt-5-mini": {
        "input": 0.25,   # $0.25 por millón de tokens
        "output": 2.00,  # $2.00 por millón de tokens
    },
    # Agregar otros modelos según sea necesario
}

# --- Función de trace (puede ser configurada desde chat_v2) ---
_trace_fn = None


def set_trace_function(trace_fn):
    """Configura la función de trace para logging."""
    global _trace_fn
    _trace_fn = trace_fn


def _tr(msg: str) -> None:
    """Función interna de trace."""
    if _trace_fn:
        _trace_fn(msg)


def ensure_log_file_exists():
    """Asegura que el archivo de log existe con headers."""
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(CHAT_V2_LOG_FILE) or os.path.getsize(CHAT_V2_LOG_FILE) == 0:
        with open(CHAT_V2_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "userName",
                "conversation_id",
                "user_message",
                "response",
                "response_id",
                "rounds_used",
                "had_previous_context",
                "extra_info"
            ])


def ensure_token_log_file_exists():
    """Asegura que el archivo de log de tokens existe con headers."""
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(TOKEN_USAGE_LOG_FILE) or os.path.getsize(TOKEN_USAGE_LOG_FILE) == 0:
        with open(TOKEN_USAGE_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "conversation_id",
                "response_id",
                "round",
                "model",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cost_input_usd",
                "cost_output_usd",
                "cost_total_usd",
                "web_search_used",
                "tools_called"
            ])


def extract_token_usage(response: Any) -> Dict[str, Any]:
    """
    Extrae información de tokens de una respuesta de Responses API.
    
    Args:
        response: Response object de OpenAI Responses API
    
    Returns:
        Dict con input_tokens, output_tokens, total_tokens
    """
    try:
        # Responses API puede tener usage en diferentes lugares
        usage = None
        
        # Intentar obtener usage directamente
        if hasattr(response, "usage"):
            usage = response.usage
        elif hasattr(response, "response") and hasattr(response.response, "usage"):
            usage = response.response.usage
        elif isinstance(response, dict) and "usage" in response:
            usage = response["usage"]
        
        if usage:
            # Manejar diferentes formatos de usage
            if hasattr(usage, "input_tokens"):
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens
                total_tokens = usage.total_tokens
            elif isinstance(usage, dict):
                input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
                output_tokens = usage.get("output_tokens") or usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
            else:
                return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
            }
    except Exception as e:
        _tr(f"Error extracting token usage: {e}")
    
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
    """
    Calcula el costo basado en tokens y modelo usado.
    
    Args:
        model: Nombre del modelo (ej: "gpt-5-mini")
        input_tokens: Número de tokens de entrada
        output_tokens: Número de tokens de salida
    
    Returns:
        Dict con cost_input_usd, cost_output_usd, cost_total_usd
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-5-mini"])  # Default a gpt-5-mini
    
    cost_input = (input_tokens / 1_000_000) * pricing["input"]
    cost_output = (output_tokens / 1_000_000) * pricing["output"]
    cost_total = cost_input + cost_output
    
    return {
        "cost_input_usd": round(cost_input, 6),
        "cost_output_usd": round(cost_output, 6),
        "cost_total_usd": round(cost_total, 6)
    }


def log_token_usage(
    conversation_id: str,
    response_id: str,
    round_num: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    web_search_used: bool = False,
    tools_called: Optional[List[str]] = None
):
    """
    Log de uso de tokens y costos por llamada a Responses API.
    
    Args:
        conversation_id: ID de la conversación
        response_id: ID de la respuesta de OpenAI
        round_num: Número de round (1-6)
        model: Modelo usado (ej: "gpt-5-mini")
        input_tokens: Tokens de entrada
        output_tokens: Tokens de salida
        total_tokens: Total de tokens
        web_search_used: Si se usó web_search en este round
        tools_called: Lista de tools llamados
    """
    try:
        ensure_token_log_file_exists()
        timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
        
        costs = calculate_cost(model, input_tokens, output_tokens)
        tools_str = ", ".join(tools_called) if tools_called else ""
        
        try:
            with open(TOKEN_USAGE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    conversation_id or "",
                    response_id or "",
                    round_num,
                    model,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    costs["cost_input_usd"],
                    costs["cost_output_usd"],
                    costs["cost_total_usd"],
                    "Yes" if web_search_used else "No",
                    tools_str
                ])
                f.flush()
            _tr(f"Logged token usage: {total_tokens} tokens (${costs['cost_total_usd']:.6f}) to {TOKEN_USAGE_LOG_FILE}")
        except PermissionError as pe:
            _tr(f"Permission denied writing token log: {pe}")
        except IOError as ioe:
            _tr(f"IO error writing token log: {ioe}")
    except Exception as e:
        _tr(f"Error logging token usage: {e}")
        import traceback
        _tr(f"Traceback: {traceback.format_exc()}")


def log_chat_v2_interaction(
    userName: str,
    conversation_id: str,
    user_message: str,
    response: str,
    response_id: Optional[str] = None,
    rounds_used: int = 0,
    had_previous_context: bool = False,
    extra_info: str = ""
):
    """
    Log simple de interacciones de chat_v2 a CSV.
    
    Args:
        userName: Nombre del usuario
        conversation_id: ID de la conversación
        user_message: Mensaje del usuario
        response: Respuesta del sistema
        response_id: ID de la respuesta de OpenAI
        rounds_used: Número de rounds usados
        had_previous_context: Si había contexto previo
        extra_info: Información adicional
    """
    try:
        ensure_log_file_exists()
        timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
        
        # Usar modo append con manejo de errores más robusto
        try:
            with open(CHAT_V2_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    userName or "N/A",
                    conversation_id or "",  # Asegurar que no sea None
                    user_message[:500] if len(user_message) > 500 else user_message,  # Limitar tamaño
                    response[:1000] if len(response) > 1000 else response,  # Limitar tamaño
                    response_id or "",
                    rounds_used,
                    "Yes" if had_previous_context else "No",
                    extra_info
                ])
                f.flush()  # Forzar escritura inmediata
            _tr(f"Logged interaction to {CHAT_V2_LOG_FILE}")
        except PermissionError as pe:
            _tr(f"Permission denied writing to CSV (file may be open): {pe}")
        except IOError as ioe:
            _tr(f"IO error writing to CSV: {ioe}")
    except Exception as e:
        _tr(f"Error logging to CSV: {e}")
        import traceback
        _tr(f"Traceback: {traceback.format_exc()}")

