from utils.llm_provider import chat_completion
from utils.llm_config   import get_llm_config
import json
import logging
import os
from fastapi import APIRouter

from utils.logs import log_ai_call, log_ai_call_postgres
from utils.tool_registry import register_tool
from utils.contextManager.context_handler import get_interaction_id, add_to_context
from utils.tool_response import ToolResponse, make_error_response
from Tools.busquedacombinada_tool import ejecutar_busqueda_combinada
from utils.prompt_loader import load_latest_prompt

# — carga del prompt —
COMPARACION_PROMPT_FULL, COMPARACION_PROMPT_FILE = load_latest_prompt(
    "CompararTicket", "comparacionfinalprompt", with_filename=True
)


router = APIRouter()

@router.post("/comparar_ticket")
@register_tool("Comparar ticket")
async def comparar_ticket(*args, **kwargs) -> dict:
    """
    puede recibir:
      - args[0] = inputs (dict)
      - args[1] = conversation_id (str)
    o bien venir en kwargs:
      - inputs
      - conversation_id
    """
    # 1) Extraer inputs y conversation_id
    if len(args) >= 2:
        inputs = args[0]
        conversation_id = args[1]
    else:
        inputs = kwargs.get("inputs", {})
        conversation_id = kwargs.get("conversation_id")

    # validamos
    if not isinstance(inputs, dict):
        return make_error_response("Inputs inválidos.").model_dump()
    if not conversation_id:
        return make_error_response("Falta conversation_id.").model_dump()

    interaction_id = get_interaction_id(conversation_id)

    try:
        # 2) Validar ticket_number y pregunta
        ticket_number = inputs.get("ticket_number")
        user_question = inputs.get("user_question")
        if not ticket_number:
            return make_error_response("Falta el número de ticket.").model_dump()
        if not user_question:
            return make_error_response("Falta la pregunta del usuario.").model_dump()

        # 3) Búsqueda combinada
        raw_combined = ejecutar_busqueda_combinada(ticket_number, conversation_id, interaction_id)
        if hasattr(raw_combined, "model_dump"):
            combined_results = raw_combined.model_dump()
        else:
            combined_results = raw_combined
        if not isinstance(combined_results, dict) or "ticket_data" not in combined_results:
            return make_error_response("Búsqueda combinada no devolvió datos válidos.").model_dump()

        # 4) Prepara payload y mensajes
        prompt_final = {
            "ticket_principal": combined_results["ticket_data"],
            "key_sentences":    combined_results.get("key_sentences", []),
            "keywords":         combined_results.get("keywords", []),
            "similar_by_faiss": combined_results.get("by_faiss", []),
            "similar_by_query": combined_results.get("by_query", [])
        }
        messages = [
            {"role": "system", "content": COMPARACION_PROMPT_FULL},
            {"role": "user",   "content": json.dumps(prompt_final, ensure_ascii=False)}
        ]

        messages[0]["content"] = (
            "IMPORTANTE: devuelve *solo* JSON* válido sin nada más.\n\n"
            + messages[0]["content"]
        )

        # … dentro de comparar_ticket(), antes de get_llm_config …
        print("[ENV CHECK]     LLM_PROVIDER       =", os.getenv("LLM_PROVIDER"))
        print("[ENV CHECK]     COMPARAR_TICKET_LLM_PROVIDER =", os.getenv("COMPARAR_TICKET_LLM_PROVIDER"))
        print("[ENV CHECK]     OPENAI_MODEL       =", os.getenv("OPENAI_MODEL"))
        print("[ENV CHECK]     COMPARAR_TICKET_OPENAI_MODEL =", os.getenv("COMPARAR_TICKET_OPENAI_MODEL"))

        # 5) Carga cfg y debug print
        cfg = get_llm_config("COMPARAR_TICKET")
        provider = cfg["provider"].value
        model = cfg["model"]
        print(f"[DEBUG] get_llm_config COMPARAR_TICKET → provider={provider}, model={model}")

        # 6) Llamada al LLM según proveedor
        if provider == "openai":
            resp = await chat_completion(
                messages,
                tool="COMPARAR_TICKET",
                model=model,
                response_format={"type": "json_object"},
                temperature=0.5,
                timeout=45
            )
        else:
            resp = await chat_completion(
                messages,
                tool="COMPARAR_TICKET",
                model=model,
                temperature=0.5,
                timeout=45
            )


        # 7) Procesa respuesta del LLM
        raw = resp["choices"][0]["message"]["content"].strip()
        logging.info(f"RAW LLM OUTPUT: {raw!r}")

        # 💡 Imprimir directamente la respuesta cruda del modelo
        print("\n[DEBUG - RAW AI RESPONSE] =====================")
        print(raw)
        print("==============================================\n")
        

        # Convertir a texto plano formateado directamente
        response_text = json.loads(raw).get("analisis_final", "").strip()


        # 8) Log seguro
        safe_messages = [
            {"role": "system", "content": f"[PROMPT:{COMPARACION_PROMPT_FILE}]"},
            {"role": "user",   "content": user_question}
        ]
        token_usage = resp.get("usage", {})
        log_ai_call(
            call_type="Comparar Ticket",
            model=model,
            provider=provider,
            messages=safe_messages,
            response=response_text,
            token_usage=token_usage,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            prompt_file=COMPARACION_PROMPT_FILE,
            temperature=0.5
        )

        await log_ai_call_postgres(
            call_type="Comparar Ticket",
            model=model,
            provider=provider,
            messages=safe_messages,
            response=response_text,
            token_usage=token_usage,
            conversation_id=conversation_id,
            interaction_id=interaction_id,
            prompt_file=COMPARACION_PROMPT_FILE,
            temperature=0.5
        )
                 
        add_to_context(
            conversation_id=conversation_id,
            active_tool="Comparar Ticket",
            user_input=user_question,
            system_output=response_text,
            data_used={"ticket_data": ticket_number}
        )

        # 8) Retorno exitoso
        return ToolResponse(
            classification="Comparar ticket",
            response=response_text.strip(),
            error="",
            results=[]
        ).model_dump()


    except Exception as e:
        logging.exception("Error en Comparar ticket")
        error_msg = f"Error en Comparar ticket: {type(e).__name__}: {e}"
        return make_error_response(error_msg).model_dump()




   