"""
Context handler for managing conversation state and interaction IDs.
Simplified version for tools that need basic interaction tracking.
"""
import time
from typing import Dict, Any, Optional

# In-memory storage for conversation context
# Format: {conversation_id: {"interaction_id": int, "last_activity": float, ...}}
conversation_context: Dict[str, Dict[str, Any]] = {}


def initialize_context(conversation_id: str) -> None:
    """Ensures a context entry exists for a conversation."""
    if conversation_id not in conversation_context:
        conversation_context[conversation_id] = {
            "interaction_id": 0,
            "last_activity": time.time(),
        }


def get_interaction_id(conversation_id: str) -> int:
    """Retrieve and increment the interaction_id for the given conversation."""
    if conversation_id not in conversation_context:
        initialize_context(conversation_id)
    
    ctx = conversation_context[conversation_id]
    ctx["interaction_id"] = ctx.get("interaction_id", 0) + 1
    ctx["last_activity"] = time.time()
    
    return ctx["interaction_id"]


def get_context(conversation_id: str) -> Dict[str, Any]:
    """Get the full context for a conversation."""
    if conversation_id not in conversation_context:
        initialize_context(conversation_id)
    return conversation_context.get(conversation_id, {})


def add_to_context(
    conversation_id: str,
    active_tool: Optional[str] = None,
    user_input: Optional[str] = None,
    system_output: Optional[str] = None,
    data_used: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """Add information to the conversation context."""
    if conversation_id not in conversation_context:
        initialize_context(conversation_id)
    
    ctx = conversation_context[conversation_id]
    ctx["last_activity"] = time.time()
    
    if active_tool is not None:
        ctx["active_tool"] = active_tool
    
    # Store history if provided
    if user_input is not None or system_output is not None:
        if "history" not in ctx:
            ctx["history"] = []
        ctx["history"].append({
            "usersinput": user_input or "",
            "systemoutput": system_output or "",
            "data_used": data_used or {},
        })
        # Keep only last 10 entries
        if len(ctx["history"]) > 10:
            ctx["history"] = ctx["history"][-10:]
    
    # Add any additional kwargs
    ctx.update(kwargs)

