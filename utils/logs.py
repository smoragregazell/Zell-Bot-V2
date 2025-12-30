import sqlite3
import asyncpg
import os
import csv
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# CSV HEADERS INITIALIZER
# ─────────────────────────────────────────────────────────────────────────────

def ensure_csv_headers(file_path, headers):
    file_exists = os.path.isfile(file_path)
    if not file_exists or os.path.getsize(file_path) == 0:
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

# ─────────────────────────────────────────────────────────────────────────────
# FILE PATHS & HEADERS
# ─────────────────────────────────────────────────────────────────────────────

AI_LOG_FILE = os.path.join(LOGS_DIR, "ai_calls.csv")
CONTEXT_LOG_FILE = os.path.join(LOGS_DIR, "context_log.csv")
ZELL_API_LOG_FILE = os.path.join(LOGS_DIR, "zell_api_calls.csv")
CONVERSATION_LOG_FILE = os.path.join(LOGS_DIR, "conversation_log.csv")

ensure_csv_headers(AI_LOG_FILE, [
    "conversation_id", "interaction_id", "call_type", "model", "provider", "temperature",
    "messages", "confidence_score", "response", "token_usage", "timestamp"
])
ensure_csv_headers(CONTEXT_LOG_FILE, [
    "conversation_id", "interaction_id", "action", "context_data", "timestamp"
])
ensure_csv_headers(ZELL_API_LOG_FILE, [
    "conversation_id", "interaction_id", "action", "api_action", "endpoint",
    "request_data", "response_data", "status_code", "headers", "timestamp"
])
ensure_csv_headers(CONVERSATION_LOG_FILE, [
    "userName", "conversation_id", "interaction_id", "step_id",
    "user_input", "system_output", "classification", "extra_info", "timestamp"
])

# ─────────────────────────────────────────────────────────────────────────────
# INTERACTION LOG
# ─────────────────────────────────────────────────────────────────────────────

def log_interaction(userName, conversation_id, interaction_id, step_id, user_input, system_output, classification, extra_info=""):
    from utils.contextManager.context_handler import get_user_info
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")

    ctx = get_user_info(conversation_id)    

    row = {
        "userName": userName or "N/A",
        "conversation_id": conversation_id,
        "interaction_id": interaction_id,
        "step_id": step_id,
        "user_input": user_input,
        "system_output": system_output,
        "classification": classification,
        "extra_info": extra_info,
        "timestamp": timestamp
    }

    try:
        fieldnames = [
            "userName", "conversation_id", "interaction_id", "step_id",
            "user_input", "system_output", "classification", "extra_info", "timestamp"
        ]

        with open(CONVERSATION_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')

            # Asegura que tenga encabezados si el archivo está vacío
            if f.tell() == 0:
                writer.writeheader()
            print("LOGGING ROW:", row)
            print("TYPE:", type(row))
            writer.writerow(row)
    except Exception as e:
        logging.error(f"❌ Error writing to conversation_log.csv: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# SQLite LOG
# ─────────────────────────────────────────────────────────────────────────────

def log_interaction_sqlite(
    userName,
    conversation_id,
    user_input,
    system_output,
    classification,
    extra_info,
    timestamp
):
    try:
        os.makedirs("logs", exist_ok=True)
        db_path = os.path.join("logs", "conversation_logs.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                conversation_id TEXT,
                user_input TEXT,
                system_output TEXT,
                classification TEXT,
                extra_info TEXT,
                timestamp_inicio TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO conversation_logs (
                user_name, conversation_id, user_input,
                system_output, classification, extra_info, timestamp_inicio
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            userName,
            conversation_id,
            user_input,
            system_output,
            classification,
            extra_info,
            timestamp
        ))

        print(f"🔍 SQLite Path: {db_path}")

        print("✅ Inserted into DB:", {
            "conversation_id": conversation_id,
            "user_name": userName,
            "user_input": user_input,
            "system_output": system_output,
            "classification": classification,
            "extra_info": extra_info,
            "timestamp": timestamp
        })

        conn.commit()
        conn.close()
        print("🧠 Interacción logueada en SQLite.")
    except Exception as e:
        print(f"🔥 Error al loguear interacción en SQLite: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# POSGRES SUPABASE CONVERSATION LOG
# ─────────────────────────────────────────────────────────────────────────────

async def log_to_postgres(log_data):
    print("PG_USER:", os.getenv("PG_USER"))
    print("PG_HOST:", os.getenv("PG_HOST"))
    
    try:
        conn = await asyncpg.connect(
            host=os.getenv("PG_HOST"),
            port=os.getenv("PG_PORT"),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            database=os.getenv("PG_DBNAME")
        )

        await conn.execute('''
            INSERT INTO conversation_logs (
                conversation_id, user_name, user_input, 
                system_output, classification, extra_info, timestamp_inicio
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        ''',
            log_data["conversation_id"],
            log_data["user_name"],
            log_data["user_input"],
            log_data["system_output"],
            log_data["classification"],
            log_data["extra_info"],
            datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)
        )
        await conn.close()
        print("✅ Log guardado en PostgreSQL.")
    except Exception as e:
        print(f"🔥 Error al guardar en PostgreSQL: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# POSGRES SUPABASE AI CALLS LOG
# ─────────────────────────────────────────────────────────────────────────────

async def log_ai_call_postgres(
    call_type, model, provider, messages, response,
    token_usage=None, conversation_id=None, interaction_id=None,
    module=None, tool=None, prompt_file=None, temperature=None, confidence_score=None
):
    try:
        conn = await asyncpg.connect(
            host=os.getenv("PG_HOST"),
            port=int(os.getenv("PG_PORT")),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            database=os.getenv("PG_DBNAME")
        )

        await conn.execute('''
            INSERT INTO ai_calls (
                conversation_id, interaction_id, call_type, model,
                provider, temperature, confidence_score,
                messages, response, token_usage, timestamp
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ''',
            conversation_id,
            interaction_id,
            call_type,
            model,
            provider,
            temperature,
            confidence_score,
            json.dumps(messages, ensure_ascii=False),
            json.dumps(response, ensure_ascii=False),
            json.dumps(token_usage, ensure_ascii=False),
            datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)
        )

        await conn.close()
        print("✅ AI call log registrado en PostgreSQL.")
    except Exception as e:
        print(f"🔥 Error al registrar AI call log en PostgreSQL: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# AI LOG
# ─────────────────────────────────────────────────────────────────────────────

def log_ai_call(call_type, model, provider, messages, response, token_usage="N/A", conversation_id=None, interaction_id=None, module=None, tool=None, prompt_file=None, temperature=None, confidence_score=None):
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[AI Call] [{timestamp}] Module: {module} | Tool: {tool} | Model: {model} | Type: {call_type}")
    logging.info(f"[AI Call] {timestamp} | Type: {call_type} | Model: {model} | Module: {module} | Tool: {tool}")

    row = [
        conversation_id or "", interaction_id or "", call_type, model, provider,                    temperature if temperature is not None else "",
        confidence_score if confidence_score is not None else "",
        json.dumps(messages, ensure_ascii=False),
        json.dumps(response, ensure_ascii=False),
        token_usage or "Not Provided", timestamp
    ]

    try:
        with open(AI_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        logging.error(f"❌ Error writing to OpenAI log: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT & ZELL LOGS
# ─────────────────────────────────────────────────────────────────────────────

def log_context_update(conversation_id, action, context_data, interaction_id=None):
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
    row = [
        conversation_id, interaction_id or "", action,
        json.dumps(context_data, ensure_ascii=False), timestamp
    ]
    try:
        with open(CONTEXT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        print(f"❌ Error writing to context log: {e}")

def log_zell_api_call(action, api_action, endpoint, request_data,
                      response_data, status_code, headers, conversation_id=None, interaction_id=None):
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
    sanitized_headers = {k: v for k, v in headers.items() if k.lower() != "password"}

    row = [
        conversation_id or "", interaction_id or "", action, api_action, endpoint,
        json.dumps(request_data, ensure_ascii=False),
        json.dumps(response_data, ensure_ascii=False),
        status_code, json.dumps(sanitized_headers, ensure_ascii=False), timestamp
    ]

    try:
        with open(ZELL_API_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        print(f"❌ Error writing to Zell API log: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# FULL PAYLOAD DEBUGGING
# ─────────────────────────────────────────────────────────────────────────────

def log_full_openai_payload(conversation_id, model, messages, call_type="DEBUG_PAYLOAD"):
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")

    try:
        debug_log_file = os.path.join(LOGS_DIR, "openai_payloads.log")

        with open(debug_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n===== {timestamp} =====\n")
            f.write(f"Conversation ID: {conversation_id}\n")
            f.write(f"Model: {model}\n")
            f.write(f"Call Type: {call_type}\n\n")
            f.write("MESSAGES STRUCTURE:\n")

            for idx, msg in enumerate(messages):
                if 'content' in msg and isinstance(msg['content'], str) and len(msg['content']) > 500:
                    truncated = msg['content'][:500] + "... [TRUNCATED]"
                    f.write(f"Message {idx} - Role: {msg['role']}\nContent: {truncated}\n\n")
                else:
                    f.write(f"Message {idx} - Role: {msg['role']}\nContent: {json.dumps(msg.get('content', ''), ensure_ascii=False)}\n\n")

            f.write("=" * 80 + "\n")
    except Exception as e:
        print(f"❌ Error logging OpenAI payload: {e}")
