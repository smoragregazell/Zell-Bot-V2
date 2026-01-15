# Propuesta: Tool `analyze_client_email`

## Objetivo
Analizar correos de clientes para determinar si es primer acercamiento, buscar tickets relacionados, casos similares y documentación de procesos para proponer siguientes pasos.

## Estructura

### 1. Tool Definition (en `v2_internal/tools/config.py`)

```python
{
    "type": "function",
    "name": "analyze_client_email",
    "description": (
        "Analiza un correo de cliente para determinar contexto, tickets relacionados, casos similares y procesos. "
        "Úsalo cuando el usuario adjunte o mencione un correo de cliente que requiere análisis. "
        "Este tool automáticamente: busca tickets abiertos del cliente, extrae conceptos clave, "
        "busca casos similares en tickets históricos, obtiene documentación de procesos de atención, "
        "y proporciona recomendaciones estructuradas."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email_content": {
                "type": "string",
                "description": "El contenido completo del correo del cliente (asunto, cuerpo, información del remitente)."
            },
            "client_name": {
                "type": "string",
                "description": "Nombre del cliente (opcional, se extraerá del correo si no se proporciona)."
            },
            "sender_email": {
                "type": "string",
                "description": "Email del remitente (opcional, para búsqueda más precisa)."
            }
        },
        "required": ["email_content"]
    }
}
```

### 2. Implementación (en `v2_internal/tools/implementations.py`)

El tool internamente ejecutará:

1. **Extracción de información del correo**
   - Cliente (nombre/código)
   - Conceptos clave del problema
   - ¿Es primer acercamiento? (basado en historial)

2. **Búsqueda de tickets abiertos del cliente**
   - Usa `query_tickets` para buscar tickets activos del cliente
   - Si encuentra, usa `get_item` para obtener detalles completos

3. **Si hay ticket abierto:**
   - Retorna información del ticket
   - Extrae conceptos clave del correo
   - Busca tickets similares con `search_knowledge` (scope="tickets")
   - Obtiene doc de proceso de atención con `search_knowledge` (scope="docs", universe="user_guides")

4. **Si NO hay ticket abierto:**
   - Extrae conceptos clave
   - Busca tickets similares con `search_knowledge`
   - Obtiene doc de proceso de atención

5. **Retorna estructura unificada** con:
   - Información del cliente
   - Ticket abierto (si existe)
   - Tickets similares encontrados
   - Documentación de proceso relevante
   - Recomendaciones de siguientes pasos

### 3. Instrucciones en `system_instructions.txt`

Agregar una sección pequeña (3-5 líneas):

```
E) ANÁLISIS DE CORREOS DE CLIENTES (analyze_client_email)
- Cuando el usuario adjunte o mencione un correo de cliente que requiere análisis, usa:
  analyze_client_email(email_content="...", client_name="...", sender_email="...")
- Este tool automáticamente: busca tickets abiertos del cliente, extrae conceptos clave, 
  busca casos similares en tickets históricos, obtiene documentación de procesos de atención, 
  y proporciona recomendaciones estructuradas.
- Después de obtener los resultados, presenta la información de forma organizada.
```

## Ventajas de esta solución

✅ **Prompt pequeño**: Solo 3-5 líneas adicionales en system_instructions.txt  
✅ **Lógica encapsulada**: Toda la complejidad está en el tool  
✅ **Reutilización**: Usa tools existentes internamente  
✅ **Mantenible**: Cambios en la lógica solo afectan el tool  
✅ **Testeable**: Se puede probar el tool independientemente  

## Alternativa (NO recomendada)

Poner toda la lógica en system_instructions.txt haría el prompt mucho más largo y difícil de mantener.
