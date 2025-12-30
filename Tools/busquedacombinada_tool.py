from utils.llm_config import get_llm_config   # (si aún no está importado)
import json
import logging
import os
import openai
import traceback
import httpx
import requests

from utils.contextManager.context_handler import get_interaction_id
from utils.logs import log_zell_api_call
from utils.logs import log_ai_call
from utils.prompt_loader import load_latest_prompt
from utils.tool_response import make_error_response
from Tools.semantic_tool import generate_openai_embedding, perform_faiss_search, init_semantic_tool

logging.basicConfig(level=logging.INFO)

def fetch_ticket_data(ticket_number):
    sql_query = sql_query = f"""
    SELECT TOP 1 
        iError = 0, 
        vError = '', 
        vJsonType = 'Query',
        IdTicket, 
        Cliente, 
        Titulo, 
        Descripcion 
    FROM dbo.Tickets 
    WHERE IdTicket = {ticket_number}
    """
    api_url = f"https://tickets.zell.mx/apilink/info?query={sql_query}"
    headers = {
        "x-api-key": os.getenv("ZELL_API_KEY"),
        "user": os.getenv("ZELL_USER"),
        "password": os.getenv("ZELL_PASSWORD"),
        "action": "7777"
    }
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        print("🔍 DEBUG - Respuesta completa del API:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict) and "IdTicket" in data:
            return data
        return {"error": "Ticket no encontrado o respuesta inesperada"}
    except Exception as e:
        logging.error(f"❌ Zell API error: {e}")
        return {"error": str(e)}


def get_ticket_comments(ticket_number, conversation_id):
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
        logging.info(f"🔍 Fetching comments for ticket {ticket_number} from Zell API...")

        with httpx.Client(timeout=30) as client:
            response = client.get(api_url, headers=api_headers)

        raw_response_text = response.text
        response.raise_for_status()

        try:
            comments_data = response.json()
        except json.JSONDecodeError as e:
            error_msg = f"❌ Error decoding JSON (comments): {str(e)}"
            logging.error(f"{error_msg} | Raw response: {raw_response_text}")
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
    except httpx.HTTPStatusError as e:
        error_msg = f"❌ HTTP Error al obtener comentarios del ticket: {str(e)}"
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"

    logging.error(error_msg)
    return {"error": error_msg}

def search_tickets_by_keywords(keywords, max_results=3):
    if not keywords:
        return []

    all_results = []
    seen_ids = set()

    for kw in keywords:
        words = kw.split()
        if not words:
            continue  # si está vacío, lo saltamos

        sanitized_words = [w.replace("'", "''") for w in words]
        like_titulo = " AND ".join([f"Titulo COLLATE Latin1_General_CI_AI LIKE '%{w}%'" for w in sanitized_words])
        like_desc = " AND ".join([f"Descripcion COLLATE Latin1_General_CI_AI LIKE '%{w}%'" for w in sanitized_words])
        like_clause = f"(({like_titulo}) OR ({like_desc}))"

        print(f"🔍 Ejecutando búsqueda LIKE para keyword '{kw}':\n{like_clause}")

        sql_query = f"""
            SELECT TOP {max_results}
                iError = 0,
                vError = '',
                vJsonType = 'Query',
                IdTicket,
                Cliente,
                Titulo,
                Descripcion
            FROM Tickets
            WHERE {like_clause}
            ORDER BY CONVERT(datetime, FechaCreado, 101) DESC
        """

        api_url = f"https://tickets.zell.mx/apilink/info?query={sql_query}"
        headers = {
            "x-api-key": os.getenv("ZELL_API_KEY"),
            "user": os.getenv("ZELL_USER"),
            "password": os.getenv("ZELL_PASSWORD"),
            "action": "7777"
        }

        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            results = response.json()

            for r in results:
                if not isinstance(r, dict):
                    logging.warning(f"[Keyword Search] salto resultado no dict: {r!r}")
                    continue
                ticket_id = r.get("IdTicket")
                if ticket_id and ticket_id not in seen_ids:
                    seen_ids.add(ticket_id)
                    all_results.append(r)

        except Exception as e:
            logging.error(f"❌ Error en búsqueda LIKE con keyword '{kw}': {e}")
            continue

    return all_results


def ejecutar_busqueda_combinada(ticket_number: str, conversation_id: str, interaction_id: int = None):
    print("🚀 Ejecutando búsqueda combinada para ticket:", ticket_number)  # <-- AQUÍ
    if interaction_id is None:
        interaction_id = get_interaction_id(conversation_id)

    try:
        ticket_info = fetch_ticket_data(ticket_number)
        print("🔍 ticket_info:", ticket_info)
        if "error" in ticket_info:
            print("❌ Error en ticket_info")
            return make_error_response(ticket_info["error"])

        ticket_comments = get_ticket_comments(ticket_number, conversation_id)
        print("📝 ticket_comments:", ticket_comments)
        if isinstance(ticket_comments, dict) and "error" in ticket_comments:
            print("❌ Error en ticket_comments")
            return make_error_response(ticket_comments["error"])

        print("📂 Intentando cargar prompt desde carpeta CompararTicket con patrón compararticketprompt")
        prompt_full, prompt_file = load_latest_prompt("BusquedaCombinada", "busquedacombinadaprompt", with_filename=True)


        payload = {
            "ticket_data": ticket_info,
            "ticket_comments": ticket_comments
        }

        model_input = json.dumps(payload, ensure_ascii=False)
        api_key = os.getenv("OPENAI_API_KEY_CompararTicket")
        if not api_key:
            return make_error_response("Falta clave API para extracción de claves.")


        client = openai.OpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": f"[PROMPT:{prompt_file}]"},
            {"role": "system", "content": prompt_full},
            {"role": "user", "content": model_input}
        ]

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            timeout=30,
            temperature=0
        )
        content = resp.choices[0].message.content
        parsed = json.loads(content) if isinstance(content, str) else content
        key_sentences = parsed.get("key_sentences", [])
        keywords = parsed.get("keywords", [])
        
        cfg = get_llm_config("COMPARAR_TICKET")       # usa el prefijo que quieras

        log_ai_call(
            call_type      = "Key Extraction",
            model          = cfg["model"],            # "gpt-4o-mini" o el tuyo
            provider       = cfg["provider"].value,   # "openai" o "deepseek"
            messages       = messages,
            response       = key_sentences,
            token_usage    = getattr(resp, "usage", {}),   # si quieres registrar tokens
            conversation_id= conversation_id,
            interaction_id = interaction_id,
            prompt_file    = prompt_file,
            temperature    = 0
        )

        init_semantic_tool()
        all_similar_ids = set()
        for sentence in key_sentences[:2]:
            vector = generate_openai_embedding(sentence, conversation_id, interaction_id)
            results, _ = perform_faiss_search(vector, k=3)
            for r in results:
                all_similar_ids.add(r["ticket_id"])

        similar_tickets_faiss = []
        for tid in all_similar_ids:
            if str(tid) == str(ticket_number):
                continue
            data = fetch_ticket_data(tid)
            comments = get_ticket_comments(tid, conversation_id)
            similar_tickets_faiss.append({"ticket_data": data, "ticket_comments": comments})

        query_results_raw = search_tickets_by_keywords(keywords, max_results=3)
        similar_tickets_like = []
        for result in query_results_raw:
            tid = result.get("IdTicket")
            if str(tid) == str(ticket_number):
                continue
            data = fetch_ticket_data(tid)
            comments = get_ticket_comments(tid, conversation_id)
            similar_tickets_like.append({"ticket_data": data, "ticket_comments": comments})
            
        print("✅ Terminó búsqueda combinada, devolviendo resultados")
        return {
            "ticket_data": ticket_info,
            "ticket_comments": ticket_comments,
            "key_sentences": key_sentences,
            "keywords": keywords,
            "by_faiss": similar_tickets_faiss,
            "by_query": similar_tickets_like
        }

    except Exception:
        logging.error("❌ Error inesperado durante ejecución de búsqueda combinada:")
        traceback.print_exc()
        raise

