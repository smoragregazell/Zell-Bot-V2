import os
import faiss
import numpy as np
import openai
import logging
import httpx
import asyncio
import json
import string
from datetime import datetime

from utils.logs import log_ai_call, log_zell_api_call, log_ai_call_postgres
from utils.contextManager.context_handler import get_interaction_id
from utils.tool_response import ToolResponse, make_error_response
from utils.tool_registry import register_tool
from utils.debug_logger import log_debug_event
from utils.contextManager.context_handler import add_to_context
from utils.prompt_loader import load_latest_prompt


# === Config ===
OPENAI_API_KEY_SEMANTIC = os.getenv("OPENAI_API_KEY_Semantic")
FAISS_INDEX_PATH = "Data/faiss_index_ip.bin"
FAISS_IDS_PATH = "Data/faiss_ids.npy"

ZELL_API_KEY = os.getenv("ZELL_API_KEY", "")
ZELL_USER = os.getenv("ZELL_USER", "")
ZELL_PASSWORD = os.getenv("ZELL_PASSWORD", "")

logger = logging.getLogger(__name__)

SEMANTIC_CLASSIFIER_PROMPT, SEMANTIC_CLASSIFIER_PROMPT_FILE = load_latest_prompt(
    "Semantica",
    "semanticclasificador",
    with_filename=True
)

if not SEMANTIC_CLASSIFIER_PROMPT:
    logger.warning("⚠️ semanticclasificador no fue cargado!")
else:
    logger.info(f"✅ Prompt cargado para semantic_tool: {SEMANTIC_CLASSIFIER_PROMPT_FILE}")

# === Globals ===
faiss_index = None
issue_ids = None
faiss_loaded = False
logger = logging.getLogger(__name__)

def load_faiss_data():
    global faiss_index, issue_ids, faiss_loaded
    if faiss_loaded:
        return True
    try:
        faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        issue_ids = np.load(FAISS_IDS_PATH).astype("int64")
        faiss_loaded = True
        if faiss_index.ntotal != len(issue_ids):
            logger.warning(f"[SemanticTool] ⚠️ Inconsistencia FAISS: index size={faiss_index.ntotal}, ids={len(issue_ids)}")
        else:
            logger.info(f"[SemanticTool] ✅ FAISS cargado: {faiss_index.ntotal} vectores, {len(issue_ids)} IDs")
        return True
    except Exception as e:
        logger.error(f"[SemanticTool] ❌ Falló carga FAISS/IDs: {e}")
        return False

def init_semantic_tool():
    openai.api_key = OPENAI_API_KEY_SEMANTIC
    return load_faiss_data()

def generate_openai_embedding(query, conversation_id, interaction_id):
    try:
        log_debug_event("Búsqueda Semántica", conversation_id, interaction_id, "Generate Embedding", {"query": query})
        resp = openai.embeddings.create(model="text-embedding-ada-002", input=query)
        vec = np.array(resp.data[0].embedding, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(vec)
        return vec
    except Exception as e:
        logger.error(f"[SemanticTool] ❌ Error embedding: {e}")
        log_debug_event("Búsqueda Semántica", conversation_id, interaction_id, "Embedding Error", {"error": str(e)})
        return None

def perform_faiss_search(vector, k=10):
    distances, indices = faiss_index.search(vector, k)
    results = []
    for i, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        results.append({"ticket_id": int(idx), "score": float(distances[0][i])})
    return results, {"distances": distances.tolist(), "indices": indices.tolist()}

def second_classifier_via_llm(user_question: str, base_inputs: dict = None, base_confidence: float = 1.0, conversation_id: str = None, interaction_id: int = None ) -> dict:
    print("📍 [semantic_tool] Entrando a second_classifier_via_llm")
    print(f"📌 [semantic_tool] base_inputs recibidos: {base_inputs}")
    try:
        search_query = (base_inputs or {}).get("search_query", user_question)
        prompt_text = (
            f"🔹 Pregunta original del usuario:\n{user_question}\n\n"
            f"🔹 Búsqueda optimizada para FAISS:\n{search_query}\n\n"
            + SEMANTIC_CLASSIFIER_PROMPT
        )
        print("📝 [semantic_tool] Prompt generado (primeros 1000 caracteres):")
        print(prompt_text[:1000])
    except Exception as e:
        print("❌ [semantic_tool] Error al construir el prompt manual:", e)
        return {
            "classification": "Búsqueda Semántica",
            "confidence_score": base_confidence,
            "inputs": base_inputs or {"search_query": user_question},
            "missing_inputs": [],
            "follow_up_prompt": ""
        }
    try:
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un clasificador de preguntas para búsquedas semánticas con filtros SQL."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.0
        )

        print("📥 [semantic_tool] Raw response completa:", resp)
        content = resp.choices[0].message.content.strip()
        print("📥 [semantic_tool] Contenido del mensaje:", content)

    except Exception as e:
        print("❌ [semantic_tool] Error al llamar a OpenAI:", e)
        return {
            "classification": "Búsqueda Semántica",
            "confidence_score": base_confidence,
            "inputs": base_inputs,
            "missing_inputs": [],
            "follow_up_prompt": ""
        }
    print("🧠 [semantic_tool] Contenido LLM crudo:", repr(content))
    if not content:
        print("⚠️ [semantic_tool] El contenido de la respuesta está vacío")
        return {
            "classification": "Búsqueda Semántica",
            "confidence_score": base_confidence,
            "inputs": base_inputs,
            "missing_inputs": [],
            "follow_up_prompt": ""
        }
    if content.startswith("```json"):
        content = content.removeprefix("```json").removesuffix("```").strip()
    elif content.startswith("```"):
        content = content.removeprefix("```").removesuffix("```").strip()
    try:
        print("📥 [semantic_tool] Contenido crudo antes del parseo:", repr(content))
        raw = json.loads(content)
        print("✅ [semantic_tool] JSON parseado correctamente:", raw)
    except json.JSONDecodeError as e:
        print("❌ [semantic_tool] JSON inválido:", repr(content))
        return {
            "classification": "Búsqueda Semántica",
            "confidence_score": base_confidence,
            "inputs": base_inputs or {"search_query": question},
            "missing_inputs": [],
            "follow_up_prompt": ""
        }
    llm_out = {
        "classification": raw.get("classification", "Búsqueda Semántica"),
        "confidence_score": raw.get("confidence_score", base_confidence),
        "inputs": raw.get("inputs", base_inputs or {"search_query": question}),
        "missing_inputs": raw.get("missing_inputs", []),
        "follow_up_prompt": raw.get("follow_up_prompt", "")
    }
    if "filters" in raw:
        llm_out["filters"] = raw["filters"]
    elif "filterkey" in raw and "filtervalue" in raw:
        llm_out["filters"] = [{"filterkey": raw["filterkey"], "filtervalue": raw["filtervalue"]}]

    # Logging del segundo clasificador
    token_usage = getattr(resp, "usage", {})
    if hasattr(token_usage, "to_dict"):
        token_usage = token_usage.to_dict()
    print("🔍 token_usage final:", token_usage, type(token_usage))

    log_ai_call(
        call_type="Semantic Classifier",
        model="gpt-4o",
        provider="openai",
        messages=user_question,
        response=json.dumps(llm_out, ensure_ascii=False),
        token_usage=token_usage,
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        prompt_file="Semantic Classifier",
        temperature=0.0,
        confidence_score=llm_out["confidence_score"]
    )
    

    asyncio.create_task(log_ai_call_postgres(
        call_type="Semantic Classifier",
        model="gpt-4o",
        provider="openai",
        messages=user_question,
        response=json.dumps(llm_out, ensure_ascii=False),
        token_usage=token_usage,
        conversation_id=conversation_id,
        interaction_id=interaction_id,
        prompt_file="Semantic Classifier",
        temperature=0.0,
        confidence_score=llm_out["confidence_score"]
    ))

    return llm_out

def fetch_query_results(ticket_ids, conversation_id, interaction_id, filters=None):
    extra_fields = set()
    if filters:
        for f in filters:
            if "filterkey" in f:
                extra_fields.add(f["filterkey"])

    sql_query = (
        f"SELECT iError=0, vError='', vJsonType='Query', IdTicket, Resumen"
    )
    if extra_fields:
        sql_query += ", " + ", ".join(extra_fields)
    sql_query += f" FROM Tickets WHERE IdTicket IN ({','.join(map(str, ticket_ids))})"

    api_url = f"https://tickets.zell.mx/apilink/info?query={sql_query}"
    headers = {"x-api-key": ZELL_API_KEY, "user": ZELL_USER, "password": ZELL_PASSWORD, "action": "7777"}
    resp = httpx.get(api_url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    log_zell_api_call(
        action="Bulk Ticket Summaries (Faiss)",
        api_action="7777",
        endpoint=api_url,
        request_data={"query": sql_query},
        response_data=data,
        status_code=resp.status_code,
        headers={k: v for k, v in headers.items() if k.lower() != 'password'},
        conversation_id=conversation_id,
        interaction_id=interaction_id
    )
    return data if isinstance(data, list) else []

@register_tool("Búsqueda Semántica")
def execute_semantic_search(inputs, conversation_id, interaction_id=None):
    print("✅ [semantic_tool] Entrando a execute_semantic_search")
    user_question = (
        inputs.get("semantic_keywords") or inputs.get("user_question") or inputs.get("search_query") or ""
    ).strip()
    print(f"🧠 [semantic_tool] Pregunta del usuario: '{user_question}'")
    if not user_question:
        return make_error_response("No se proporcionaron palabras clave para la búsqueda.")
    interaction_id = interaction_id or get_interaction_id(conversation_id)
    log_debug_event("Búsqueda Semántica", conversation_id, interaction_id, "Start", {"user_question": user_question})
    if not faiss_loaded and not init_semantic_tool():
        return make_error_response("No se pudo inicializar el índice semántico.")
    vector = generate_openai_embedding(user_question, conversation_id, interaction_id)
    if vector is None:
        return make_error_response("Error al generar el vector de búsqueda.")
    try:
        print("📨 [semantic_tool] Llamando a second_classifier_via_llm")
        print(f"📌 [semantic_tool] user_question detectado: '{user_question}'")
        clf = second_classifier_via_llm(
            user_question=user_question,
            base_inputs={"search_query": user_question},
            base_confidence=inputs.get("confidence_score", 1.0),
            conversation_id=conversation_id,
            interaction_id=interaction_id
            )
    except Exception as e:
        logger.error(f"[SemanticTool] ⚠️ Clasificador falló: {e}")
        clf = {"classification": "Búsqueda Semántica", "filters": [],
               "confidence_score": inputs.get("confidence_score", 1.0),
               "inputs": {"search_query": user_question}, "missing_inputs": [], "follow_up_prompt": ""}
    top_k = 45 if clf.get("filters") else 10
    results, _ = perform_faiss_search(vector, k=top_k)
    ticket_ids = [r["ticket_id"] for r in results]
    log_debug_event("Búsqueda Semántica", conversation_id, interaction_id, "FAISS IDs", {"ids": ticket_ids})
    filters = clf.get("filters")
    data = fetch_query_results(ticket_ids, conversation_id, interaction_id, filters=filters)
    print(f"🔍 [semantic_tool] Filtros aplicados: {filters}")
    final = []
    response_lines = []
    if filters:
        for f in filters:
            key = f.get("filterkey")
            val = f.get("filtervalue")
            if isinstance(val, dict) and "from" in val and "to" in val:
                # Filtro por rango de fechas
                from_date = val["from"]
                to_date = val["to"]

                def normalize(date_str):
                    return datetime.strptime(date_str, "%m/%d/%Y")

                try:
                    data = [
                        rec for rec in data
                        if key in rec and rec.get(key)
                        and normalize(from_date) <= normalize(rec.get(key)) <= normalize(to_date)
                    ]
                except Exception as e:
                    print(f"❌ Error aplicando filtro de fechas: {e}")
                    continue

            elif isinstance(val, list):
                data = [
                    rec for rec in data
                    if str(rec.get(key, "")).strip().lower() in [v.strip().lower() for v in val]
                ]
            else:
                data = [
                    rec for rec in data
                    if str(rec.get(key, "")).strip().lower() == val.strip().lower()
                ]
        else:
            print("🔍 [semantic_tool] No se aplicó filtro.")

    for rec in data:
        idticket = rec.get("IdTicket")
        resumen = rec.get("Resumen", "(sin resumen)")
        if filters:
            extras = " | ".join(f"{f['filterkey']}: {rec.get(f['filterkey'], '(sin valor)')}" for f in filters)
            response_lines.append(f"*IdTicket: {idticket} | {extras} | Resumen: {resumen}")
        else:
            response_lines.append(f"*IdTicket: {idticket} | Resumen: {resumen}")
        final.append({
            "IdTicket": idticket,
            "Resumen": resumen
        })
    if response_lines:
        response_text = "🧠 **Resultados semánticos:**\n\n" + "\n\n---\n\n".join(response_lines)
    else:
        response_text = "No encontré tickets que coincidan con esos criterios."
    try:
        add_to_context(
            conversation_id=conversation_id,
            active_tool=clf.get("classification"),
            user_input=user_question,
            system_output=response_text.strip(),
            data_used={"results": results}
        )
        log_ai_call(
            call_type="Semantic Search",
            model="text-embedding-ada-002",
            provider="openai",
            messages=user_question,
            response=response_text,
            token_usage="token_usage",
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            prompt_file="Semantic Search",
            temperature=0.3
        )

        asyncio.create_task(log_ai_call_postgres(
            call_type="Semantic Search",
            model="text-embedding-ada-002",
            provider="openai",
            messages=user_question,
            response=response_text,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            prompt_file="Semantic Search",
            temperature=0.3
        ))

        classification = "Búsqueda Semántica"
        return ToolResponse(
            classification=classification,
            response=response_text.strip(),
            results=final
        ).model_dump()
    except Exception as e:
        logger.error(f"❌ [semantic_tool] Error al construir respuesta final: {e}")
        return make_error_response("Error en ejecución de herramienta.")
