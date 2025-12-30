# utils/debug_logger.py

import os
import json
import logging
from datetime import datetime

# Setup debug log directory and file
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
DEBUG_LOG_FILE = os.path.join(LOGS_DIR, "debugging.log")

# Configure debug logger
debug_logger = logging.getLogger("debugging")
debug_logger.setLevel(logging.DEBUG)

if not debug_logger.handlers:
    handler = logging.FileHandler(DEBUG_LOG_FILE, encoding='utf-8')
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    debug_logger.addHandler(handler)

def log_debug_event(tool, conversation_id, interaction_id, step, input_data=None, output_data=None):
    """
    Log structured debugging info for internal dev use.
    """
    entry = {
        "tool": tool,
        "conversation_id": conversation_id,
        "interaction_id": interaction_id,
        "step": step,
        "input_data": input_data or {},
        "output_data": output_data or {}
    }

    try:
        debug_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception as e:
        logging.error(f"[DebugLogger] ❌ Failed to write debug entry: {str(e)}")
