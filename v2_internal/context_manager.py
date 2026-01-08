"""
Gestión de contexto conversacional para chat_v2
"""
import time
from typing import Any, Dict, Optional

# --- Conversational context storage ---
# Almacena el último response_id por conversation_id para mantener contexto
# Formato: {conversation_id: {"last_response_id": "resp_xxx", "updated_at": timestamp}}
_conversation_response_ids: Dict[str, Dict[str, Any]] = {}

# --- Web search tracking ---
# Almacena el conteo de búsquedas web por conversación
# Formato: {conversation_id: count}
_web_search_counts: Dict[str, int] = {}


def get_last_response_id(conversation_id: str) -> Optional[str]:
    """Obtiene el último response_id guardado para esta conversación."""
    entry = _conversation_response_ids.get(conversation_id)
    if entry:
        return entry.get("last_response_id")
    return None


def save_last_response_id(conversation_id: str, response_id: str) -> None:
    """Guarda el último response_id para esta conversación."""
    _conversation_response_ids[conversation_id] = {
        "last_response_id": response_id,
        "updated_at": time.time(),
    }


def clear_conversation_context(conversation_id: str) -> None:
    """Limpia el contexto de una conversación (para empezar de nuevo)."""
    _conversation_response_ids.pop(conversation_id, None)
    _web_search_counts.pop(conversation_id, None)


def get_web_search_count(conversation_id: str) -> int:
    """Obtiene el número de búsquedas web realizadas en esta conversación."""
    return _web_search_counts.get(conversation_id, 0)


def increment_web_search_count(conversation_id: str) -> int:
    """Incrementa el contador de búsquedas web y retorna el nuevo valor."""
    current = _web_search_counts.get(conversation_id, 0)
    new_count = current + 1
    _web_search_counts[conversation_id] = new_count
    return new_count


def can_use_web_search(conversation_id: str) -> bool:
    """Verifica si se puede realizar una búsqueda web (no se ha alcanzado el límite)."""
    from .config import MAX_WEB_SEARCHES_PER_CONV
    return get_web_search_count(conversation_id) < MAX_WEB_SEARCHES_PER_CONV

