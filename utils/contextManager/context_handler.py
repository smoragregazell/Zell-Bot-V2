import json
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.logs import log_context_update
from utils.contextManager.short_term_memory import clear_short_term_memory

# Stores long-term conversation context
conversation_context = {}

CONVERSATION_TIMEOUT = 1800  # 30 minutes in seconds

def generate_conversation_id():
    """Generate a unique conversation ID."""
    return f"conv_{datetime.now(ZoneInfo('America/Mexico_City')).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

def is_conversation_expired(conversation_id):
    """Check if the conversation has been inactive longer than CONVERSATION_TIMEOUT."""
    ctx = conversation_context.get(conversation_id)
    if not ctx:
        return True  # No context => treat as expired

    last_activity = ctx.get("last_activity", 0)
    return (time.time() - last_activity) > CONVERSATION_TIMEOUT

def get_or_create_conversation_id(incoming_id: str = None):
    """
    Returns a valid conversation_id.
    - If incoming_id is valid & not expired, reuse it.
    - Otherwise, generate a new one.
    """
    if incoming_id and incoming_id in conversation_context:
        if not is_conversation_expired(incoming_id):
            conversation_context[incoming_id]["last_activity"] = time.time()
            return incoming_id
        else:
            remove_conversation(incoming_id)

    new_id = generate_conversation_id()
    initialize_context(new_id)
    return new_id

def get_interaction_id(conversation_id):
    """Retrieve and increment the interaction_id for the given conversation."""
    if conversation_id not in conversation_context:
        initialize_context(conversation_id)

    ctx = conversation_context[conversation_id]
    ctx["interaction_id"] = ctx.get("interaction_id", 0) + 1
    ctx["last_activity"] = time.time()

    return ctx["interaction_id"]

def initialize_context(conversation_id):
    """Ensures a context entry exists for a conversation."""
    if conversation_id not in conversation_context:
        conversation_context[conversation_id] = {
            "active_tool": None,
            "history": [],
            "interaction_id": 0,
            "last_activity": time.time()
        }
        log_context_update(
            conversation_id=conversation_id,
            interaction_id=0,  # Since it's a new conversation
            action="Initialized",
            context_data=conversation_context[conversation_id]
        )

def remove_conversation(conversation_id):
    """Removes all data for a conversation (context + short-term memory)."""
    if conversation_id in conversation_context:
        log_context_update(
            conversation_id=conversation_id,
            interaction_id=conversation_context[conversation_id].get("interaction_id", 0),
            action="Cleared",
            context_data={"message": "Conversation context removed"}
        )
        del conversation_context[conversation_id]

    clear_short_term_memory(conversation_id)

def add_to_context(conversation_id, active_tool, user_input, system_output, data_used=None):
    """
    Adds a structured entry to the conversation history.
    If a new tool is used (excluding continuation), previous context is cleared.
    """
    initialize_context(conversation_id)

    # Get and increment the interaction ID
    interaction_id = get_interaction_id(conversation_id)

    ctx = conversation_context[conversation_id]
    last_tool = ctx.get("active_tool")

    # 🔹 Reset context if switching tools (except continuation)
    if last_tool and last_tool != active_tool and last_tool != "Pregunta Continuada":
        ctx["history"] = []
        log_context_update(
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            action="Reset",
            context_data={"previous_tool": last_tool, "new_tool": active_tool}
        )

    # 🔹 Update active tool
    ctx["active_tool"] = active_tool

    # 🔹 Append structured entry
    new_entry = {
        "usersinput": user_input,
        "systemoutput": system_output,
        "datautilized": data_used
    }
    ctx["history"].append(new_entry)

    # Update last_activity
    ctx["last_activity"] = time.time()

    # ✅ Log context update with the current interaction ID
    log_context_update(
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        action="Updated",
        context_data=new_entry
    )

def get_context(conversation_id):
    """Retrieves the full conversation context."""
    return conversation_context.get(conversation_id, {})

def reset_context(conversation_id):
    """Resets conversation history (except for 'Pregunta Continuada')."""
    if conversation_id in conversation_context:
        context_data = conversation_context[conversation_id]
        context_data.update({
            "active_tool": None,
            "history": [],
            "interaction_id": 0,
            "last_activity": time.time()
        })

        log_context_update(
            conversation_id=conversation_id,
            interaction_id=context_data.get("interaction_id", 0),
            action="Reset",
            context_data={"message": "Context reset"}
        )
# ✅ Nuevo: Guardar nombre del usuario
def set_user_info(conversation_id, user_name):
    initialize_context(conversation_id)
    conversation_context[conversation_id]["user_info"] = user_name
    log_context_update(
        conversation_id=conversation_id,
        interaction_id=conversation_context[conversation_id].get("interaction_id", 0),
        action="SetUserInfo",
        context_data={"user_info": user_name}
    )

# ✅ Nuevo: Obtener nombre del usuario
def get_user_info(conversation_id):
    return conversation_context.get(conversation_id, {}).get("user_info")
