"""
StepEmitter: Emite eventos de progreso para live steps en el frontend
"""
import asyncio
import time
from typing import Any, Dict, Optional
from contextvars import ContextVar

from ..config import TRACE_V2

# ContextVar para el emitter actual (por request, thread-safe)
_step_emitter: ContextVar[Optional['StepEmitter']] = ContextVar('step_emitter', default=None)


class StepEmitter:
    """Emite eventos de progreso para live steps en el frontend"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.last_sent_time = 0.0
        self.last_message = ""
        self.throttle_ms = 0  # Sin throttle - mostrar TODOS los mensajes (para debug)
    
    async def emit_status(self, message: str):
        """Emite un mensaje de estado si pasa el throttle/dedupe"""
        now = time.time() * 1000  # milliseconds
        
        # Dedupe: si es EXACTAMENTE el mismo mensaje, ignorar
        # Pero permitir mensajes similares con IDs diferentes (ej: "Obteniendo ticket #123" vs "#456")
        if message == self.last_message:
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Mensaje duplicado filtrado: '{message}'", flush=True)
            return
        
        # Throttle: si pasó menos tiempo, ignorar (pero más permisivo)
        time_since_last = now - self.last_sent_time
        if time_since_last < self.throttle_ms:
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Mensaje throttled (esperando {self.throttle_ms - time_since_last:.1f}ms más): '{message}'", flush=True)
            return
        
        self.last_sent_time = now
        self.last_message = message
        
        if TRACE_V2:
            print(f"[V2-TRACE-DEBUG] Mensaje enviado a queue: '{message}'", flush=True)
        
        try:
            await self.queue.put({
                'type': 'status',
                'message': message,
                'timestamp': now
            })
        except Exception as e:
            # No bloquear si hay error (ej: queue cerrada)
            if TRACE_V2:
                print(f"[V2-TRACE-DEBUG] Error enviando a queue: {e}", flush=True)
            pass
    
    async def get_event(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """Obtiene un evento de la queue con timeout"""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    async def emit_response(self, response: str):
        """Emite la respuesta final"""
        try:
            await self.queue.put({
                'type': 'response',
                'content': response,
                'timestamp': time.time() * 1000
            })
        except Exception:
            pass
    
    async def emit_error(self, error: str):
        """Emite un error"""
        try:
            await self.queue.put({
                'type': 'error',
                'message': error,
                'timestamp': time.time() * 1000
            })
        except Exception:
            pass


def get_step_emitter() -> Optional[StepEmitter]:
    """Obtiene el emitter actual del contexto"""
    return _step_emitter.get()


def set_step_emitter(emitter: Optional[StepEmitter]) -> None:
    """Establece el emitter en el contexto"""
    _step_emitter.set(emitter)

