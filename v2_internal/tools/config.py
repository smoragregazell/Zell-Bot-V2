"""
Configuración de herramientas para chat_v2
"""
import os
from typing import Any, Dict, List

from ..live_steps import tr


def load_system_instructions() -> str:
    """Carga las instrucciones del sistema desde el archivo de texto."""
    # Encontrar la raíz del proyecto buscando hacia arriba desde __file__ hasta encontrar main.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # current_dir = .../v2_internal/tools
    
    # Subir niveles hasta encontrar main.py
    project_root = None
    for _ in range(5):  # Máximo 5 niveles hacia arriba
        if os.path.exists(os.path.join(current_dir, "main.py")):
            project_root = current_dir
            break
        parent = os.path.dirname(current_dir)
        if parent == current_dir:  # Llegamos a la raíz del sistema
            break
        current_dir = parent
    
    # Si no encontramos main.py, usar el directorio actual
    if project_root is None:
        project_root = os.getcwd()
        # Verificar si estamos en la raíz correcta
        if not os.path.exists(os.path.join(project_root, "main.py")):
            # Intentar desde __file__ subiendo 3 niveles como fallback
            script_dir = os.path.dirname(os.path.abspath(__file__))
            v2_internal_dir = os.path.dirname(script_dir)
            project_root = os.path.dirname(v2_internal_dir)
    
    instructions_path = os.path.join(project_root, "Prompts", "V2", "system_instruccions.txt")
    
    try:
        with open(instructions_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        tr(f"WARNING: No se encontró {instructions_path}, usando instrucciones por defecto")
        return "Eres un asistente interno para Zell."
    except Exception as e:
        tr(f"ERROR al cargar instrucciones: {e}, usando instrucciones por defecto")
        return "Eres un asistente interno para Zell."


SYSTEM_INSTRUCTIONS = load_system_instructions()


TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_knowledge",
        "description": (
            "Busca en tickets/docs por keyword, semántica o híbrido. "
            "Devuelve IDs y scores; luego usa get_item para detalle."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {
                    "type": "string",
                    "enum": ["tickets", "docs", "etiquetas", "quotes", "cotizaciones", "all"],
                    "default": "all",
                    "description": "Scope de búsqueda: 'tickets' para tickets, 'docs' para documentos, 'etiquetas' para etiquetas del sistema ZELL, 'quotes'/'cotizaciones' para cotizaciones, 'all' para todos.",
                },
                "policy": {
                    "type": "string",
                    "enum": ["auto", "keyword", "semantic", "hybrid"],
                    "default": "auto",
                },
                "universe": {
                    "type": "string",
                    "description": (
                        "Universo de documentos cuando scope=docs. "
                        "Opciones: "
                        "'user_guides' (PRIMERO para preguntas sobre el sistema Zell - guías de usuario del sistema Zell). "
                        "**ÚSALO PRIMERO** cuando el usuario pregunte sobre: cómo usar el sistema Zell, cómo hacer algo en Zell/en el sistema, "
                        "procedimientos paso a paso en el sistema, configuración de módulos, captura de información, "
                        "filtros, botones, pantallas del sistema, guías de usuario, nombres de módulos (Cobranza, Domiciliación, Tickets, etc.). "
                        "Ejemplos: '¿cómo hacer X en Zell?', '¿cómo hacer X en el sistema?', 'pasos para configurar módulo...', "
                        "'procedimiento de domiciliación en Zell', 'cómo capturar... en el sistema', 'manual de usuario'. "
                        "'docs_org' (documentos organizacionales: políticas, procedimientos administrativos, manuales ISO, reglamentos, códigos de ética). "
                        "Úsalo SOLO cuando la pregunta sea sobre políticas organizacionales o procedimientos administrativos (NO del sistema Zell). "
                        "'meetings_weekly' (minutas de reuniones semanales - PROBLEMAS Y SOLUCIONES). "
                        "Úsalo cuando el usuario pregunte sobre: problemas similares que otros han enfrentado, soluciones ya discutidas, "
                        "situaciones que el equipo ya vivió ('¿alguien ha tenido este problema?', 'experiencia similar', 'caso parecido', "
                        "'¿cómo se resolvió esto antes?', '¿esto ya pasó?'). "
                        "También para: reuniones específicas, temas tratados en juntas, asistentes, fechas de reuniones, decisiones o acuerdos. "
                        "'all' (ÚLTIMO RECURSO - buscar en TODOS los universos: docs_org, user_guides, meetings_weekly). "
                        "Úsalo SOLO cuando: (1) el usuario preguntó '¿dónde se habla sobre X?' o 'busca en todos lados' Y (2) ya preguntaste al usuario dónde buscar Y (3) el usuario no sabe o no especificó dónde buscar. "
                        "Los resultados se combinan y ordenan por relevancia. "
                        "REGLA CRÍTICA: Si la pregunta menciona 'en Zell', 'en el sistema', nombres de módulos, o acciones operativas del sistema → usa 'user_guides' PRIMERO. "
                        "Si no estás seguro dónde buscar, PREGUNTA AL USUARIO primero: '¿Dónde te gustaría que busque? ¿En tickets, documentos organizacionales, minutas o guías de usuario?'"
                    ),
                    "default": "docs_org",
                },
                "top_k": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Número máximo de resultados a obtener. RECOMENDADO: 3 (default). MÁXIMO: 5. Valores altos (>5) saturan el contexto y causan que se alcance el límite de rounds sin respuesta. IMPORTANTE: Después de search_knowledge, SIEMPRE llama get_item para obtener el contenido real.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_item",
        "description": (
            "Trae detalle de un item (ticket, doc). "
            "Úsalo DIRECTAMENTE cuando el usuario pida un ticket específico por número/ID "
            "(ej: 'traeme el ticket 36816', 'ticket #12345', 'muéstrame el ticket 5000'). "
            "NO uses search_knowledge primero si el usuario especifica un número de ticket."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string", 
                    "enum": ["ticket", "doc", "etiqueta", "quote"],
                    "description": "Tipo de item: 'ticket' para tickets, 'doc' para documentos, 'etiqueta' para etiquetas del sistema ZELL, 'quote' para cotizaciones."
                },
                "id": {"type": "string", "description": "ID del item. Para tickets, usa el número del ticket (ej: '36816', '12345'). Para etiquetas, usa el número de etiqueta (ej: '101') o chunk_id (ej: 'etiqueta_101'). Para cotizaciones, usa el número de ticket (i_issue_id, mismo que el ticket) o chunk_id (ej: 'quote_1054'). IMPORTANTE: Las cotizaciones comparten el mismo ID que los tickets (i_issue_id = ticket ID), puedes usar el mismo ID para obtener el ticket completo con type='ticket'."},
                "include_comments": {"type": "boolean", "default": True},
                "universe": {
                    "type": "string",
                    "description": (
                        "Universo de documentos cuando type=doc. "
                        "Debe coincidir con el universo usado en search_knowledge para obtener el chunk_id. "
                        "Opciones: 'docs_org', 'meetings_weekly', u otros."
                    ),
                    "default": "docs_org",
                },
            },
            "required": ["type", "id"],
        },
    },
    {
        "type": "function",
        "name": "query_tickets",
        "description": (
            "Ejecuta consultas SQL sobre tickets para responder preguntas cuantitativas o de filtrado. "
            "Úsalo cuando el usuario pregunte: cuántos tickets, tickets abiertos/cerrados en un período, "
            "tickets por persona (Javier, Alfredo, etc.), tickets por cliente, tickets por estatus/categoría, "
            "tickets con filtros de fecha (diciembre, último mes, etc.), o cualquier pregunta que requiera "
            "contar, agregar o filtrar tickets con criterios específicos. "
            "Ejemplos: '¿Cuántos tickets se abrieron en diciembre por Javier?', "
            "'Tickets activos de Exitus', 'Tickets en estatus Desarrollo'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_question": {
                    "type": "string",
                    "description": "La pregunta del usuario sobre tickets que requiere una consulta SQL.",
                },
            },
            "required": ["user_question"],
        },
    },
    {
        "type": "function",
        "name": "analyze_client_email",
        "description": (
            "Analiza un correo de cliente para determinar contexto, tickets relacionados con soluciones y siguientes pasos. "
            "Úsalo cuando el usuario adjunte o mencione un correo de cliente. "
            "Este tool automáticamente: extrae conceptos clave del problema/situación/requerimiento, "
            "busca tickets similares en histórico para ver si hay soluciones, y obtiene el procedimiento de atención completo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email_content": {
                    "type": "string",
                    "description": "El contenido completo del correo del cliente (asunto, cuerpo, información del remitente).",
                },
            },
            "required": ["email_content"],
        },
    },
    {
        "type": "function",
        "name": "propose_next_steps",
        "description": (
            "Analiza un ticket y propone los siguientes pasos basándose en el procedimiento de atención. "
            "Úsalo cuando el usuario pregunte '¿qué hago ahora?' o 'siguientes pasos' al analizar un ticket. "
            "Este tool automáticamente: obtiene el ticket completo, obtiene el documento completo del "
            "Procedimiento de Solicitud de atención (P-OPR-01), y propone acciones basadas en el estatus "
            "y contenido del ticket según el procedimiento."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "El ID o número del ticket a analizar (ej: '17532', '12345').",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "type": "web_search"  # Tool integrado de OpenAI para búsquedas web en tiempo real
    },
]

# Nota: FAISS se inicializa en main.py al iniciar la aplicación
# No se inicializa aquí para evitar inicialización duplicada

