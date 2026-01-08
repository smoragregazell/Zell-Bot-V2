"""
Configuración y constantes para chat_v2
"""
import os

# Variables de entorno
TRACE_V2 = os.getenv("TRACE_V2", "0") == "1"
SKIP_AUTH = os.getenv("SKIP_AUTH", "0") == "1"

# Constantes
MAX_WEB_SEARCHES_PER_CONV = 3  # Límite de búsquedas web por conversación

