import os
import hmac
import uuid
import csv
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

SECRET_KEY = os.getenv("WIDGET_SECRET_KEY", "clave_secreta_segura")
LOG_PATH = "logs/session_tokens.csv"
TOKEN_EXPIRATION_HOURS = 12

# Asegúrate de que el archivo de log exista
os.makedirs("logs", exist_ok=True)
if not os.path.isfile(LOG_PATH):
    with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["token", "user_email", "timestamp_inicio", "estado", "motivo"])


class SessionRequest(BaseModel):
    user_email: str
    user_hash: str


@router.post("/start_session")
def start_session(data: SessionRequest):
    user_email = data.user_email.strip().lower()
    user_hash = data.user_hash.strip()

    # Validar el hash
    computed_hash = hmac.new(
        key=SECRET_KEY.encode(),
        msg=user_email.encode(),
        digestmod="sha256"
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, user_hash):
        registrar_token("-", user_email, "rechazado", "Hash inválido")
        raise HTTPException(status_code=401, detail="Hash inválido")

    # Generar token
    token = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    # Registrar token válido
    registrar_token(token, user_email, "valido", "login correcto")

    return {"status": "success", "token": token}


def registrar_token(token: str, email: str, estado: str, motivo: str):
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([token, email, datetime.utcnow().isoformat(), estado, motivo])


def validar_token(token: str) -> tuple[bool, str]:
    """
    Retorna (True, email) si el token es válido y activo.
    Retorna (False, motivo) si es inválido o expirado.
    """
    updated_rows = []
    token_encontrado = False
    valido = False
    email_encontrado = "-"
    motivo = ""

    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_token = row["token"]
            estado = row["estado"]
            email = row["user_email"]
            ts = datetime.fromisoformat(row["timestamp_inicio"])

            if row_token == token:
                token_encontrado = True
                email_encontrado = email

                if estado == "valido":
                    if datetime.utcnow() - ts <= timedelta(hours=TOKEN_EXPIRATION_HOURS):
                        valido = True
                        motivo = "Token válido"
                        updated_rows.append(row)
                    else:
                        # Lazy update → marcar como expirado
                        row["estado"] = "expirado"
                        row["motivo"] = "expirado por uso"
                        motivo = "Token expirado"
                        updated_rows.append(row)
                else:
                    motivo = f"Token en estado: {estado}"
                    updated_rows.append(row)
            else:
                updated_rows.append(row)

    # Reescribe el CSV con los cambios (lazy update si hubo expiración)
    if token_encontrado:
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["token", "user_email", "timestamp_inicio", "estado", "motivo"])
            writer.writeheader()
            writer.writerows(updated_rows)

    if not token_encontrado:
        return False, "Token no encontrado"
    if valido:
        return True, email_encontrado
    return False, motivo
