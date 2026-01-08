"""
Detección y traducción de mensajes para live steps
"""
import asyncio
import re
from typing import Optional

from ..config import TRACE_V2
from .emitter import get_step_emitter


def is_relevant_for_live_steps(msg: str) -> bool:
    """Detecta si un mensaje tr() es relevante para mostrar en live steps"""
    # Patrones más flexibles que capturan variaciones (con o sin puntos, etc.)
    relevant_patterns = [
        r"Buscando en documentación interna Zell",  # Con o sin "..."
        r"Explorando scope=.+ ejecutando estrategia=.+",
        r"Obteniendo top \d+ resultados para query",  # Con o sin ":"
        r"Buscando en tickets con palabras clave",  # Con o sin ":"
        r"Buscando en tickets con búsqueda semántica",  # Con o sin "..."
        r"Buscando en: .+",  # Debe tener ":"
        r"Obteniendo información del documento",  # Con o sin nombre del documento
        r"Obteniendo datos del ticket #\d+",
        r"Query SQL generado",  # Con o sin ":"
        r"Ejecutando web_search para",  # Con o sin ":"
        r"Generando respuesta final para el usuario",  # Con o sin "..."
    ]
    
    for pattern in relevant_patterns:
        if re.search(pattern, msg, re.IGNORECASE):
            return True
    return False


def extract_live_step_message(msg: str) -> Optional[str]:
    """Extrae el mensaje amigable del mensaje técnico usando regex"""
    
    # Patrones con sus traducciones
    patterns = [
        # "Buscando en documentación interna Zell..."
        (r"Buscando en documentación interna Zell", 
         "Buscando en documentación interna Zell..."),
        
        # "Explorando scope={scope} ejecutando estrategia={policy}"
        (r"Explorando scope=(.+) ejecutando estrategia=(.+)", 
         lambda m: f"Explorando {m.group(1)} con estrategia {m.group(2)}..."),
        
        # "Obteniendo top {top_k} resultados para query: '{query[:120]}'"
        (r"Obteniendo top (\d+) resultados para query", 
         lambda m: f"Se encontraron {m.group(1)} resultados relevantes"),
        
        # "Buscando en tickets con palabras clave: {words}"
        (r"Buscando en tickets con palabras clave", 
         "Buscando en tickets con palabras clave..."),
        
        # "Buscando en tickets con búsqueda semántica..."
        (r"Buscando en tickets con búsqueda semántica", 
         "Buscando en tickets con búsqueda semántica..."),
        
        # "Buscando en: {universe}"
        (r"Buscando en: (.+)", 
         lambda m: f"Buscando en {m.group(1)}..."),
        
        # "Obteniendo información del documento: {title}" o "Obteniendo información del documento..."
        (r"Obteniendo información del documento: (.+)", 
         lambda m: f"Obteniendo información del documento: {m.group(1)}..."),
        (r"Obteniendo información del documento", 
         "Obteniendo información del documento..."),
        
        # "Obteniendo datos del ticket #{item_id}"
        (r"Obteniendo datos del ticket #(\d+)", 
         lambda m: f"Obteniendo datos del ticket #{m.group(1)}..."),
        
        # "Query SQL generado: {sql_query}"
        (r"Query SQL generado", 
         "Ejecutando consulta SQL..."),
        
        # "Ejecutando web_search para: {web_query[:100]}"
        (r"Ejecutando web_search para", 
         "Buscando información en la web..."),
        
        # "Generando respuesta final para el usuario..."
        (r"Generando respuesta final para el usuario", 
         "Generando respuesta final para el usuario..."),
    ]
    
    for pattern, translation in patterns:
        match = re.search(pattern, msg)
        if match:
            try:
                if callable(translation):
                    return translation(match)
                else:
                    return translation
            except Exception as e:
                # Si hay error en la traducción, loguear y continuar
                if TRACE_V2:
                    print(f"[V2-TRACE-DEBUG] Error traduciendo '{msg}' con patrón '{pattern}': {e}", flush=True)
                continue
    
    # Si no se encontró traducción, loguear para debug
    if TRACE_V2:
        print(f"[V2-TRACE-DEBUG] No se encontró traducción para mensaje relevante: {msg}", flush=True)
    return None


def tr(msg: str) -> None:
    """Trace function mejorada: log normal + emisión de eventos live si aplica"""
    # Log normal (siempre funciona, no cambia nada)
    if TRACE_V2:
        print(f"[V2-TRACE] {msg}", flush=True)
    
    # Si es relevante para live steps Y hay emitter activo, emitirlo
    if is_relevant_for_live_steps(msg):
        emitter = get_step_emitter()
        if emitter:
            friendly_msg = extract_live_step_message(msg)
            if friendly_msg:
                # Debug: loguear cuando se emite un mensaje
                if TRACE_V2:
                    print(f"[V2-TRACE-DEBUG] Emitiendo live step: '{friendly_msg}' (original: '{msg}')", flush=True)
                # Emitir sin bloquear (usar create_task si estamos en contexto async)
                try:
                    loop = asyncio.get_running_loop()
                    # Estamos en contexto async, usar create_task
                    asyncio.create_task(emitter.emit_status(friendly_msg))
                except RuntimeError:
                    # No hay event loop corriendo, crear uno nuevo (raro pero posible)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(emitter.emit_status(friendly_msg))
                        else:
                            loop.run_until_complete(emitter.emit_status(friendly_msg))
                    except:
                        # Si falla todo, ignorar (no es crítico)
                        pass
            else:
                # Debug: mensaje relevante pero sin traducción
                if TRACE_V2:
                    print(f"[V2-TRACE-DEBUG] Mensaje relevante pero sin traducción: {msg}", flush=True)
        else:
            # Debug: si el mensaje es relevante pero no hay emitter, loguear
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Mensaje relevante pero sin emitter: {msg}", flush=True)

