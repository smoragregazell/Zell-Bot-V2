import os
import csv
from datetime import datetime, timedelta

SESSION_LOG_PATH = "logs/session_tokens.csv"
VALIDATION_LOG_PATH = "logs/token_validations.csv"
TOKEN_EXPIRY_HOURS = 12

# Asegura que los archivos y carpetas existan
os.makedirs("logs", exist_ok=True)
for path, headers in [
    (SESSION_LOG_PATH, ["token", "user_email", "timestamp_inicio", "estado", "motivo"]),
    (VALIDATION_LOG_PATH, ["tipo", "token", "user_email", "timestamp_utc", "estado", "motivo"])
]:
    if not os.path.isfile(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

def verificar_token(token: str) -> dict:
    """
    Verifica si el token es válido y activo.
    Devuelve:
        {
            "continuar": True/False,
            "usuario": email (si aplica),
            "motivo": descripción del resultado
        }
    """
    now = datetime.utcnow()
    encontrado = False
    valido = False
    usuario = "-"
    motivo = ""
    updated_rows = []

    # Leer y procesar todos los tokens
    with open(SESSION_LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_token = row["token"]
            row_email = row["user_email"]
            row_estado = row["estado"]
            ts = datetime.fromisoformat(row["timestamp_inicio"])

            if row_token == token:
                encontrado = True
                usuario = row_email

                if row_estado == "valido":
                    if now - ts <= timedelta(hours=TOKEN_EXPIRY_HOURS):
                        valido = True
                        motivo = "Token válido"
                    else:
                        row["estado"] = "expirado"
                        row["motivo"] = "Expirado por lazy update"
                        motivo = "Token expirado"
                else:
                    motivo = f"Token en estado: {row_estado}"

            updated_rows.append(row)

    # Reescribir si hubo expiración (lazy update)
    if encontrado:
        with open(SESSION_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["token", "user_email", "timestamp_inicio", "estado", "motivo"])
            writer.writeheader()
            writer.writerows(updated_rows)

    # Registrar intento
    with open(VALIDATION_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "validación",
            token,
            usuario,
            now.isoformat(),
            "valido" if valido else "rechazado",
            motivo if encontrado else "Token no encontrado"
        ])

    if not encontrado:
        return {"continuar": False, "usuario": "-", "motivo": "Token no encontrado"}
    if valido:
        return {"continuar": True, "usuario": usuario, "motivo": "Token válido"}
    return {"continuar": False, "usuario": usuario, "motivo": motivo}

def recuperar_token_conversation_id(conversation_id: str) -> str | None:
    csv_path = "logs/conversation_sessions.csv"
    if not os.path.isfile(csv_path):
        return None
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["conversation_id"] == conversation_id:
                return row["token"]
    return None
