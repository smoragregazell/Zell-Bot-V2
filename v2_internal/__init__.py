"""
Módulo chat_v2 - Sistema de chat V2 con Responses API
"""
from .models import ChatV2Request
from .config import TRACE_V2, SKIP_AUTH, MAX_WEB_SEARCHES_PER_CONV
from .context_manager import (
    get_last_response_id,
    save_last_response_id,
    clear_conversation_context,
    get_web_search_count,
    increment_web_search_count,
    can_use_web_search,
)
from .live_steps import StepEmitter, get_step_emitter, set_step_emitter, tr
from .tool_description import TOOLS, SYSTEM_INSTRUCTIONS, TOOL_IMPL
from .core import process_chat_v2_core

__all__ = [
    "ChatV2Request",
    "TRACE_V2",
    "SKIP_AUTH",
    "MAX_WEB_SEARCHES_PER_CONV",
    "get_last_response_id",
    "save_last_response_id",
    "clear_conversation_context",
    "get_web_search_count",
    "increment_web_search_count",
    "can_use_web_search",
    "StepEmitter",
    "get_step_emitter",
    "set_step_emitter",
    "tr",
    "TOOLS",
    "SYSTEM_INSTRUCTIONS",
    "TOOL_IMPL",
    "process_chat_v2_core",
]

