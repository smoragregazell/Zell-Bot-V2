"""
Sistema de logging para chat_v2.
Maneja logs de interacciones y uso de tokens/costos.
"""
import os
import csv
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

# Cliente de Supabase (lazy loading)
_supabase_client = None

# Cliente de Supabase (lazy loading)
_supabase_client = None

# --- Archivos de log ---
CHAT_V2_LOG_FILE = os.path.join("logs", "chat_v2_interactions.csv")
TOKEN_USAGE_LOG_FILE = os.path.join("logs", "chat_v2_token_usage.csv")

# --- Precios de modelos (por millón de tokens) ---
# Fuente: https://openai.com/api/pricing/
# Precios actualizados: gpt-5-mini
MODEL_PRICING = {
    "gpt-5-mini": {
        "input": 0.25,      # $0.25 por millón de tokens (input no cached)
        "input_cached": 0.025,  # $0.025 por millón de tokens (input cached)
        "output": 2.00,     # $2.00 por millón de tokens (output)
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
    """Asegura que el archivo de log de tokens existe con headers correctos."""
    os.makedirs("logs", exist_ok=True)
    
    # Si el archivo no existe o está vacío, crear con headers nuevos
    if not os.path.exists(TOKEN_USAGE_LOG_FILE) or os.path.getsize(TOKEN_USAGE_LOG_FILE) == 0:
        try:
            with open(TOKEN_USAGE_LOG_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "conversation_id",
                    "response_id",
                    "round",
                    "model",
                    "input_tokens_total",  # Total de input (incluye cached)
                    "cached_tokens",       # Tokens cached
                    "input_tokens_real",   # Input real sin cache (total - cached)
                    "output_tokens",
                    "total_tokens",
                    "cost_input_usd",      # Costo sobre input_tokens_real
                    "cost_cached_usd",     # Costo sobre cached_tokens
                    "cost_output_usd",
                    "cost_total_usd",
                    "web_search_used",
                    "tools_called"
                ])
        except (PermissionError, IOError) as e:
            _tr(f"⚠️ No se pudo crear {TOKEN_USAGE_LOG_FILE}: {e}")
            _tr(f"⚠️ Verifica que el archivo no esté abierto en Excel u otro programa.")
        return
    
    # Si el archivo existe, solo verificar formato (sin intentar migrar)
    # Las nuevas filas se escribirán con el formato nuevo automáticamente
    try:
        with open(TOKEN_USAGE_LOG_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header and "cached_tokens" not in header:
                _tr(f"ℹ️ CSV tiene formato antiguo. Nuevas filas tendrán columnas cached_tokens y cost_cached_usd.")
    except (PermissionError, IOError) as e:
        # Si no puede leer, no es crítico - solo intentará escribir en modo append
        pass
    except Exception as e:
        # Cualquier otro error no es crítico
        pass


def extract_token_usage(response: Any) -> Dict[str, Any]:
    """
    Extrae información de tokens de una respuesta de Responses API.
    
    Args:
        response: Response object de OpenAI Responses API
    
    Returns:
        Dict con input_tokens_total, input_tokens_real, cached_tokens, output_tokens, total_tokens
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
                input_tokens = usage.input_tokens or 0
                output_tokens = usage.output_tokens or 0
                total_tokens = usage.total_tokens or 0
                # Asegurar que son ints
                input_tokens = int(input_tokens) if input_tokens is not None else 0
                output_tokens = int(output_tokens) if output_tokens is not None else 0
                total_tokens = int(total_tokens) if total_tokens is not None else 0
                
                # Intentar obtener cached tokens desde input_tokens_details
                cached_tokens = 0
                if hasattr(usage, "input_tokens_details"):
                    input_details = usage.input_tokens_details
                    if input_details:
                        # input_tokens_details puede ser un objeto con campo "cached_tokens"
                        if hasattr(input_details, "cached_tokens"):
                            cached_tokens = input_details.cached_tokens or 0
                        elif hasattr(input_details, "cache_read_tokens"):
                            cached_tokens = input_details.cache_read_tokens or 0
                        elif isinstance(input_details, dict):
                            cached_tokens = input_details.get("cached_tokens") or input_details.get("cache_read_tokens") or 0
                        
                        # Si no encontramos cached, intentar convertir a dict y buscar
                        if cached_tokens == 0:
                            try:
                                # Intentar convertir a dict si es un objeto Pydantic
                                if hasattr(input_details, "model_dump"):
                                    details_dict = input_details.model_dump()
                                    _tr(f"[DEBUG] input_tokens_details (model_dump): {details_dict}")
                                    cached_tokens = details_dict.get("cached_tokens") or details_dict.get("cache_read_tokens") or 0
                                elif hasattr(input_details, "__dict__"):
                                    details_attrs = [attr for attr in dir(input_details) if not attr.startswith("_")]
                                    _tr(f"[DEBUG] input_tokens_details attributes: {details_attrs}")
                                    # Intentar acceder directamente a los atributos comunes
                                    for attr in ["cached_tokens", "cache_read_tokens", "cached_input_tokens"]:
                                        if hasattr(input_details, attr):
                                            val = getattr(input_details, attr, None) or 0
                                            if val and val > 0:
                                                cached_tokens = val
                                                _tr(f"[DEBUG] ✅ Encontrado {attr} = {val}")
                                                break
                                    if cached_tokens == 0:
                                        # Intentar obtener todos los valores como dict
                                        details_dict = input_details.__dict__
                                        _tr(f"[DEBUG] input_tokens_details __dict__: {details_dict}")
                                        cached_tokens = details_dict.get("cached_tokens") or details_dict.get("cache_read_tokens") or 0
                                elif isinstance(input_details, dict):
                                    _tr(f"[DEBUG] input_tokens_details dict: {input_details}")
                                    cached_tokens = input_details.get("cached_tokens") or input_details.get("cache_read_tokens") or 0
                            except Exception as e:
                                _tr(f"[DEBUG] Error accediendo input_tokens_details: {e}")
                
                # Si no encontramos en input_tokens_details, buscar directamente en usage
                if cached_tokens == 0:
                    cached_tokens = (
                        getattr(usage, "cached_tokens", None) or 
                        getattr(usage, "cache_creation_input_tokens", None) or
                        getattr(usage, "cache_read_input_tokens", None) or
                        0
                    )
                                
            elif isinstance(usage, dict):
                input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
                # Asegurar que son ints
                input_tokens = int(input_tokens) if input_tokens is not None else 0
                output_tokens = int(output_tokens) if output_tokens is not None else 0
                total_tokens = int(total_tokens) if total_tokens is not None else 0
                
                # Intentar obtener cached tokens desde input_tokens_details
                cached_tokens = 0
                input_details = usage.get("input_tokens_details")
                if input_details:
                    if isinstance(input_details, dict):
                        cached_tokens = input_details.get("cached_tokens") or input_details.get("cache_read_tokens") or 0
                        if cached_tokens == 0:
                            _tr(f"[DEBUG] input_tokens_details dict: {input_details}")
                
                if cached_tokens == 0:
                    cached_tokens = (
                        usage.get("cached_tokens") or 
                        usage.get("cache_creation_input_tokens") or
                        usage.get("cache_read_input_tokens") or
                        0
                    )
            else:
                return {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            
            # En Responses API, input_tokens incluye los cached tokens
            # Necesitamos separar:
            # - input_tokens_total: total que viene de la API (incluye cached)
            # - cached_tokens: tokens cached
            # - input_tokens_real: input real sin cache (total - cached)
            # Asegurar que todos los valores son ints válidos
            input_tokens = int(input_tokens) if input_tokens is not None else 0
            cached_tokens = int(cached_tokens) if cached_tokens is not None else 0
            output_tokens = int(output_tokens) if output_tokens is not None else 0
            total_tokens = int(total_tokens) if total_tokens is not None else 0
            
            input_tokens_total = input_tokens  # Guardar el total original
            input_tokens_real = max(0, input_tokens - cached_tokens)  # Asegurar que no sea negativo
            
            # Log de debug si encontramos cached tokens
            if cached_tokens > 0:
                _tr(f"[DEBUG] ✅ Cached tokens encontrados: {cached_tokens} | input_total={input_tokens_total}, input_real={input_tokens_real}")
            elif hasattr(usage, "input_tokens_details") or (isinstance(usage, dict) and "input_tokens_details" in usage):
                _tr(f"[DEBUG] input_tokens_details existe pero cached_tokens=0. Revisar estructura.")
            
            result = {
                "input_tokens_total": input_tokens_total,  # Total de input (incluye cached)
                "input_tokens_real": input_tokens_real,    # Input real sin cache (para calcular costo)
                "cached_tokens": cached_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
            }
            
            # Debug: verificar que se está retornando correctamente
            if cached_tokens > 0:
                _tr(f"[DEBUG extract_token_usage] Retornando: input_total={result['input_tokens_total']}, input_real={result['input_tokens_real']}, cached={result['cached_tokens']}, output={result['output_tokens']}, total={result['total_tokens']}")
            
            return result
    except Exception as e:
        _tr(f"Error extracting token usage: {e}")
        import traceback
        _tr(f"Traceback: {traceback.format_exc()}")
    
    return {"input_tokens_total": 0, "input_tokens_real": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def calculate_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> Dict[str, float]:
    """
    Calcula el costo basado en tokens y modelo usado.
    
    Args:
        model: Nombre del modelo (ej: "gpt-5-mini")
        input_tokens: Número de tokens de entrada (no cached)
        output_tokens: Número de tokens de salida
        cached_tokens: Número de tokens de entrada cached (opcional, default: 0)
    
    Returns:
        Dict con cost_input_usd, cost_cached_usd, cost_output_usd, cost_total_usd
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-5-mini"])  # Default a gpt-5-mini
    
    cost_input = (input_tokens / 1_000_000) * pricing["input"]
    cost_cached = (cached_tokens / 1_000_000) * pricing.get("input_cached", 0.025)
    cost_output = (output_tokens / 1_000_000) * pricing["output"]
    cost_total = cost_input + cost_cached + cost_output
    
    return {
        "cost_input_usd": round(cost_input, 6),
        "cost_cached_usd": round(cost_cached, 6),
        "cost_output_usd": round(cost_output, 6),
        "cost_total_usd": round(cost_total, 6)
    }


def log_token_usage(
    conversation_id: str,
    response_id: str,
    round_num: int,
    model: str,
    input_tokens_total: int,
    input_tokens_real: int,
    cached_tokens: int,
    output_tokens: int,
    total_tokens: int,
    web_search_used: bool = False,
    tools_called: Optional[List[str]] = None
):
    """
    Log de uso de tokens y costos por llamada a Responses API (CSV y PostgreSQL/Supabase).
    
    Args:
        conversation_id: ID de la conversación
        response_id: ID de la respuesta de OpenAI
        round_num: Número de round (1-12)
        model: Modelo usado (ej: "gpt-5-mini")
        input_tokens_total: Total de tokens de entrada (incluye cached)
        input_tokens_real: Tokens de entrada reales sin cache (total - cached)
        cached_tokens: Tokens de entrada cached
        output_tokens: Tokens de salida
        total_tokens: Total de tokens
        web_search_used: Si se usó web_search en este round
        tools_called: Lista de tools llamados
    """
    try:
        ensure_token_log_file_exists()
        timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
        
        # Debug: verificar que cached_tokens se está recibiendo correctamente
        if cached_tokens > 0:
            _tr(f"[DEBUG log_token_usage] Recibido: input_total={input_tokens_total}, input_real={input_tokens_real}, cached={cached_tokens}, output={output_tokens}")
        
        # Calcular costos sobre input_tokens_real (precio normal) y cached_tokens (precio cached)
        costs = calculate_cost(model, input_tokens_real, output_tokens, cached_tokens)
        tools_str = ", ".join(tools_called) if tools_called else ""
        
        # Log cuando se detecta uso de cache
        if cached_tokens > 0:
            normal_cost = (cached_tokens / 1_000_000) * 0.25  # Lo que costaría sin cache
            cached_cost = (cached_tokens / 1_000_000) * 0.025  # Lo que cuesta con cache
            actual_savings = normal_cost - cached_cost
            _tr(f"✅ CACHE DETECTADO: {cached_tokens:,} cached tokens (ahorro: ${actual_savings:.6f}) | Round {round_num} | Conv: {conversation_id[:20] if conversation_id else 'N/A'}...")
        
        # Log a CSV (síncrono)
        try:
            with open(TOKEN_USAGE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    conversation_id or "",
                    response_id or "",
                    round_num,
                    model,
                    input_tokens_total,    # Total de input (incluye cached)
                    cached_tokens,         # Tokens cached
                    input_tokens_real,     # Input real sin cache
                    output_tokens,
                    total_tokens,
                    costs["cost_input_usd"],    # Costo sobre input_tokens_real
                    costs["cost_cached_usd"],   # Costo sobre cached_tokens
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
        
        # Log a Supabase (usando librería oficial - síncrono)
        try:
            log_token_usage_postgres(
                conversation_id, response_id, round_num, model,
                input_tokens_total, input_tokens_real, cached_tokens,
                output_tokens, total_tokens,
                costs["cost_input_usd"], costs["cost_cached_usd"],
                costs["cost_output_usd"], costs["cost_total_usd"],
                web_search_used, tools_called
            )
        except Exception as e:
            _tr(f"Error en logging de tokens a Supabase (continuando): {e}")
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
    Log de interacciones de chat_v2 a CSV y PostgreSQL/Supabase.
    
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
    # Log a CSV (síncrono)
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
    
    # Log a Supabase (usando librería oficial - síncrono)
    try:
        log_chat_v2_interaction_postgres(
            userName, conversation_id, user_message, response,
            response_id, rounds_used, had_previous_context, extra_info
        )
    except Exception as e:
        _tr(f"Error en logging a Supabase (continuando): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# POSTGRES/SUPABASE LOGGING V2
# ─────────────────────────────────────────────────────────────────────────────

def _get_supabase_client():
    """Obtiene o crea el cliente de Supabase (singleton).
    Usa la librería oficial supabase-py según: https://supabase.com/docs/reference/python/introduction
    """
    global _supabase_client
    if _supabase_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            _tr("⚠️ SUPABASE_URL o SUPABASE_KEY no configurados")
            return None
        
        try:
            # Intentar importar supabase
            try:
                from supabase import create_client
            except ImportError:
                # Si falla, verificar si está instalado
                import sys
                import subprocess
                _tr("⚠️ supabase-py no encontrado en este entorno Python")
                _tr(f"⚠️ Python path: {sys.executable}")
                _tr("⚠️ Instala con: pip install supabase")
                # Intentar verificar instalación
                try:
                    result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                                          capture_output=True, text=True, timeout=5)
                    if "supabase" in result.stdout:
                        _tr("⚠️ supabase está instalado pero no se puede importar - reinicia el servidor")
                    else:
                        _tr("⚠️ supabase NO está instalado en este entorno")
                except:
                    pass
                return None
            
            # Crear cliente
            _supabase_client = create_client(supabase_url, supabase_key)
            _tr(f"✅ Cliente Supabase inicializado: {supabase_url}")
            
        except Exception as e:
            error_msg = str(e)
            if "proxy" in error_msg.lower():
                _tr(f"⚠️ Error de versión: problema conocido con 'proxy'")
                _tr("⚠️ Solución: pip install --upgrade supabase httpx")
            elif "websockets" in error_msg.lower() or "ModuleNotFoundError" in error_msg:
                _tr(f"⚠️ Faltan dependencias de supabase: {e}")
                _tr("⚠️ Solución: python -m pip install --upgrade websockets supabase")
            elif "JWT" in error_msg or "invalid api key" in error_msg.lower():
                _tr(f"⚠️ Error de autenticación: Verifica SUPABASE_KEY en tu .env")
            else:
                _tr(f"⚠️ Error inicializando cliente Supabase: {e}")
                import traceback
                _tr(f"Traceback: {traceback.format_exc()}")
            return None
    return _supabase_client

def _schedule_async_log(coro):
    """Helper para ejecutar una corrutina de logging de forma segura."""
    try:
        import asyncio
        loop = None
        try:
            loop = asyncio.get_running_loop()
            # Si hay un loop corriendo, crear task en background
            asyncio.create_task(coro)
        except RuntimeError:
            # No hay loop corriendo, crear uno nuevo
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(coro)
            except RuntimeError:
                # Crear loop completamente nuevo
                asyncio.run(coro)
    except Exception as e:
        _tr(f"Error scheduling async log (continuando): {e}")

def log_chat_v2_interaction_postgres(
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
    Log de interacciones V2 en Supabase usando la librería oficial supabase-py.
    Inserta en la tabla conversation_logs_v2 que coincide exactamente con chat_v2_interactions.csv
    
    Referencia: https://supabase.com/docs/reference/python/introduction
    
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
        supabase = _get_supabase_client()
        if not supabase:
            _tr("⚠️ Cliente Supabase no disponible - saltando logging")
            return
        
        # Convertir had_previous_context a texto "Yes"/"No" (igual que en CSV)
        had_context_str = "Yes" if had_previous_context else "No"
        
        timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
        
        # Insertar usando la librería oficial de Supabase
        # Referencia: https://supabase.com/docs/reference/python/insert-data
        data = {
            "timestamp": timestamp,
            "userName": userName or "N/A",
            "conversation_id": conversation_id,
            "user_message": user_message,
            "response": response,
            "response_id": response_id or "",
            "rounds_used": rounds_used,
            "had_previous_context": had_context_str,
            "extra_info": extra_info
        }
        
        result = supabase.table("conversation_logs_v2").insert(data).execute()
        _tr("✅ Log V2 guardado en Supabase (conversation_logs_v2).")
        
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
            _tr(f"🔥 Error: La tabla 'conversation_logs_v2' no existe. Ejecuta el SQL de creación de tablas primero.")
        elif "JWT" in error_msg or "auth" in error_msg.lower() or "invalid api key" in error_msg.lower():
            _tr(f"🔥 Error de autenticación Supabase: Verifica SUPABASE_KEY en tu .env")
        elif "could not connect" in error_msg.lower() or "network" in error_msg.lower():
            _tr(f"🔥 Error de conexión a Supabase: Verifica SUPABASE_URL en tu .env")
        else:
            _tr(f"🔥 Error al guardar log V2 en Supabase: {e}")


def log_token_usage_postgres(
    conversation_id: str,
    response_id: str,
    round_num: int,
    model: str,
    input_tokens_total: int,
    input_tokens_real: int,
    cached_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cost_input_usd: float,
    cost_cached_usd: float,
    cost_output_usd: float,
    cost_total_usd: float,
    web_search_used: bool = False,
    tools_called: Optional[List[str]] = None,
    provider: str = "openai"
):
    """
    Log de uso de tokens V2 en Supabase usando la librería oficial supabase-py.
    Inserta en token_usage_v2 (coincide con chat_v2_token_usage.csv) 
    y también en ai_calls_v2 (estructura más completa con JSONB).
    
    Referencia: https://supabase.com/docs/reference/python/introduction
    
    Args:
        conversation_id: ID de la conversación
        response_id: ID de la respuesta de OpenAI
        round_num: Número de round (1-12)
        model: Modelo usado (ej: "gpt-5-mini")
        input_tokens_total: Total de tokens de entrada (incluye cached)
        input_tokens_real: Tokens de entrada reales sin cache
        cached_tokens: Tokens de entrada cached
        output_tokens: Tokens de salida
        total_tokens: Total de tokens
        cost_input_usd: Costo de input tokens
        cost_cached_usd: Costo de cached tokens
        cost_output_usd: Costo de output tokens
        cost_total_usd: Costo total
        web_search_used: Si se usó web_search
        tools_called: Lista de tools llamados
        provider: Proveedor del modelo (default: "openai")
    """
    try:
        supabase = _get_supabase_client()
        if not supabase:
            _tr("⚠️ Cliente Supabase no disponible - saltando logging de tokens")
            return
        
        timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
        
        # Convertir web_search_used a texto "Yes"/"No" (igual que en CSV)
        web_search_str = "Yes" if web_search_used else "No"
        
        # Convertir tools_called a string separado por comas (igual que en CSV)
        tools_str = ", ".join(tools_called) if tools_called else ""

        # 1. Insertar en token_usage_v2 (estructura exacta del CSV)
        token_data = {
            "timestamp": timestamp,
            "conversation_id": conversation_id,
            "response_id": response_id,
            "round": round_num,
            "model": model,
            "input_tokens_total": input_tokens_total,
            "cached_tokens": cached_tokens,
            "input_tokens_real": input_tokens_real,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_input_usd": float(cost_input_usd),
            "cost_cached_usd": float(cost_cached_usd),
            "cost_output_usd": float(cost_output_usd),
            "cost_total_usd": float(cost_total_usd),
            "web_search_used": web_search_str,
            "tools_called": tools_str
        }
        
        supabase.table("token_usage_v2").insert(token_data).execute()

        # 2. También insertar en ai_calls_v2 (estructura más completa con JSONB)
        token_usage_json = {
            "input_tokens_total": input_tokens_total,
            "input_tokens_real": input_tokens_real,
            "cached_tokens": cached_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_input_usd": cost_input_usd,
            "cost_cached_usd": cost_cached_usd,
            "cost_output_usd": cost_output_usd,
            "cost_total_usd": cost_total_usd,
            "round": round_num,
            "web_search_used": web_search_used,
            "tools_called": tools_called or []
        }

        messages_json = [{
            "role": "system",
            "content": f"V2 Response API - Round {round_num}"
        }]

        response_json = {
            "response_id": response_id,
            "round": round_num,
            "model": model,
            "version": "V2"
        }
        
        timestamp_dt = datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)
        
        ai_call_data = {
            "conversation_id": conversation_id,
            "interaction_id": response_id,
            "call_type": "V2 Response",
            "model": model,
            "provider": provider,
            "temperature": None,
            "confidence_score": None,
            "messages": messages_json,
            "response": response_json,
            "token_usage": token_usage_json,
            "timestamp": timestamp_dt.isoformat()
        }
        
        supabase.table("ai_calls_v2").insert(ai_call_data).execute()
        
        _tr(f"✅ Token usage V2 log registrado en Supabase (token_usage_v2 + ai_calls_v2, Round {round_num}).")
        
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
            _tr(f"🔥 Error: Las tablas no existen. Ejecuta el SQL de creación de tablas primero.")
        elif "JWT" in error_msg or "auth" in error_msg.lower() or "invalid api key" in error_msg.lower():
            _tr(f"🔥 Error de autenticación Supabase: Verifica SUPABASE_KEY en tu .env")
        elif "could not connect" in error_msg.lower() or "network" in error_msg.lower():
            _tr(f"🔥 Error de conexión a Supabase: Verifica SUPABASE_URL en tu .env")
        else:
            _tr(f"🔥 Error al registrar token usage V2 en Supabase: {e}")

