"""
Obtener tickets - Funciones para obtener datos completos de tickets y comentarios.
Complementa a search_tickets.py:
- search_tickets.py: Buscar tickets (keywords, semantic, hybrid)
- get_tickets.py: Obtener detalles de tickets específicos (get_ticket_data + get_ticket_comments)
"""
import os
import json
import logging
import httpx
from typing import Dict, Any

from utils.contextManager.context_handler import get_interaction_id
from utils.logs import log_zell_api_call

logger = logging.getLogger(__name__)


def get_ticket_data(ticket_number: str, conversation_id: str) -> Dict[str, Any]:
    """
    Obtiene los datos completos de un ticket desde la API de Zell.
    
    Args:
        ticket_number: Número del ticket a obtener
        conversation_id: ID de la conversación (para logging)
    
    Returns:
        Dict con los datos del ticket o {"error": "mensaje"} si falla
    """
    api_url = f"https://tickets.zell.mx/apilink/info?source=1&sourceid={ticket_number}"
    api_headers = {
        "x-api-key": os.getenv("ZELL_API_KEY", ""),
        "user": os.getenv("ZELL_USER", ""),
        "password": os.getenv("ZELL_PASSWORD", ""),
        "action": "5001"
    }
    interaction_id = get_interaction_id(conversation_id)
    sanitized_headers = {k: v for k, v in api_headers.items() if k.lower() != "password"}

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(api_url, headers=api_headers)

        raw_response_text = response.text
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(f"❌ Error decoding JSON for ticket {ticket_number}")
            return {"error": "La API respondió con un formato no válido", "raw_response": raw_response_text}

        if isinstance(data, dict) and data.get("code") == 145125:
            return {"error": "La API no encontró el ticket solicitado.", "raw": data}

        log_zell_api_call(
            action="Fetch Ticket Data",
            api_action="5001",
            endpoint=api_url,
            request_data={"ticket_number": ticket_number},
            response_data=data,
            status_code=response.status_code,
            headers=sanitized_headers,
            conversation_id=conversation_id,
            interaction_id=interaction_id
        )

        # Normalizar respuesta: agregar ticket_id si existe IdTicket
        if isinstance(data, dict) and "IdTicket" in data:
            data["ticket_id"] = data["IdTicket"]
            return data
        if isinstance(data, list) and data and "IdTicket" in data[0]:
            d = data[0]
            d["ticket_id"] = d["IdTicket"]
            return d

        return {"error": "Formato de respuesta de API inesperado", "data": data}

    except httpx.TimeoutException:
        error_msg = f"⏳ Timeout: No se pudo obtener datos del ticket {ticket_number} en el tiempo esperado."
        logger.error(error_msg)
        return {"error": error_msg}
    except httpx.HTTPStatusError as e:
        error_msg = f"❌ HTTP Error al obtener datos del ticket: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error inesperado al obtener ticket: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}


def get_ticket_comments(ticket_number: str, conversation_id: str) -> Dict[str, Any]:
    """
    Obtiene los comentarios de un ticket desde la API de Zell.
    
    Args:
        ticket_number: Número del ticket
        conversation_id: ID de la conversación (para logging)
    
    Returns:
        Dict con los comentarios del ticket o {"error": "mensaje"} si falla
    """
    api_url = f"https://tickets.zell.mx/apilink/info?source=1&sourceid={ticket_number}"
    api_headers = {
        "x-api-key": os.getenv("ZELL_API_KEY", ""),
        "user": os.getenv("ZELL_USER", ""),
        "password": os.getenv("ZELL_PASSWORD", ""),
        "action": "5002"
    }
    interaction_id = get_interaction_id(conversation_id)
    sanitized_headers = {k: v for k, v in api_headers.items() if k.lower() not in ["password"]}

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(api_url, headers=api_headers)

        raw_response_text = response.text
        response.raise_for_status()

        try:
            comments_data = response.json()
        except json.JSONDecodeError as e:
            error_msg = f"❌ Error decoding JSON (comments): {str(e)}"
            logger.error(f"{error_msg} | Raw response: {raw_response_text}")
            return {"error": "La API respondió con un formato no válido", "raw_response": raw_response_text}

        if isinstance(comments_data, dict) and comments_data.get("code") == 145125:
            return {"error": "La API no encontró comentarios para el ticket solicitado.", "raw": comments_data}

        log_zell_api_call(
            action="Fetch Ticket Comments",
            api_action="5002",
            endpoint=api_url,
            request_data={"ticket_number": ticket_number},
            response_data=comments_data,
            status_code=response.status_code,
            headers=sanitized_headers,
            conversation_id=conversation_id,
            interaction_id=interaction_id
        )

        return comments_data

    except httpx.TimeoutException:
        error_msg = f"⏳ Timeout: No se pudo obtener comentarios del ticket {ticket_number} en el tiempo esperado."
        logger.error(error_msg)
        return {"error": error_msg}
    except httpx.HTTPStatusError as e:
        error_msg = f"❌ HTTP Error al obtener comentarios del ticket: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error inesperado al obtener comentarios: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

