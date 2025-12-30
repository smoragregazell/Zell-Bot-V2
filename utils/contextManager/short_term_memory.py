# In-memory short-term memory store
short_term_memory = {}

def add_to_short_term_memory(conversation_id, user_message=None, bot_response=None, classification=None):
    """Adds user messages and bot responses to short-term memory, maintaining conversation flow."""

    if conversation_id not in short_term_memory:
        short_term_memory[conversation_id] = {
            "user_last_message": "",
            "bot_last_response": "",
            "second_to_last_interaction": "",
            "third_to_last_interaction": "",
            "recent_classifications": []  # Track recent classifications to detect loops
        }

    memory = short_term_memory[conversation_id]

    # Shift previous messages safely
    memory["third_to_last_interaction"] = memory.get("second_to_last_interaction", "")
    memory["second_to_last_interaction"] = f"User: {memory.get('user_last_message', '')} | Bot: {memory.get('bot_last_response', '')}"

    # Update last user message
    if user_message:
        memory["user_last_message"] = user_message

    # Update last bot response
    if bot_response:
        memory["bot_last_response"] = bot_response

    # Update classification history if provided
    if classification:
        memory.setdefault("recent_classifications", [])
        # Keep only the last 5 classifications
        memory["recent_classifications"] = (memory["recent_classifications"][-4:] + [classification])

def get_short_term_memory(conversation_id):
    """Retrieves the short-term memory for the given conversation."""
    return short_term_memory.get(conversation_id, {
        "user_last_message": "",
        "bot_last_response": "",
        "second_to_last_interaction": "",
        "third_to_last_interaction": "",
        "recent_classifications": []
    })

def reset_short_term_memory(conversation_id):
    """Resets short-term memory when a tool is used."""
    if conversation_id in short_term_memory:
        short_term_memory[conversation_id] = {
            "user_last_message": "",
            "bot_last_response": "",
            "second_to_last_interaction": "",
            "third_to_last_interaction": "",
            "recent_classifications": []
        }

def clear_short_term_memory(conversation_id):
    """Completely remove short-term memory for a conversation."""
    short_term_memory.pop(conversation_id, None)
