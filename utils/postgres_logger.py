import asyncpg
import os

async def log_to_postgres(log_data):
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
            log_data["timestamp"]
        )
        await conn.close()
        print("✅ Log guardado en PostgreSQL.")
    except Exception as e:
        print(f"🔥 Error al guardar en PostgreSQL: {e}")
