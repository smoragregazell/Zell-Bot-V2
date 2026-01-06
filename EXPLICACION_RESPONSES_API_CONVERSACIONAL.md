# Cómo hacer `chat_v2.py` conversacional con Responses API

## Diferencia clave: Responses API vs Chat Completions

### Chat Completions API (tradicional)
- Necesitas pasar **todo el historial** de mensajes en cada request
- El formato es: `[{role: "user", content: "..."}, {role: "assistant", content: "..."}, ...]`
- El cliente debe gestionar y enviar todo el contexto

### Responses API (más simple)
- OpenAI **guarda el contexto internamente** usando `response.id`
- Solo necesitas pasar el `previous_response_id` de la última respuesta
- No necesitas enviar todo el historial de mensajes
- El contexto se mantiene automáticamente en el lado de OpenAI

## Cómo funciona actualmente (sin contexto entre requests)

```python
# Request 1: "¿Qué tickets hay sobre errores?"
prev_id = None  # Primera interacción
response = client.responses.create(
    input=[{"role": "user", "content": "¿Qué tickets hay sobre errores?"}],
    previous_response_id=prev_id  # None = nueva conversación
)
# response.id = "resp_abc123"
# Se retorna al cliente, pero NO se guarda

# Request 2: "¿Y cuáles son los más recientes?"
prev_id = None  # ❌ Se pierde el contexto!
response = client.responses.create(
    input=[{"role": "user", "content": "¿Y cuáles son los más recientes?"}],
    previous_response_id=prev_id  # None = nueva conversación (sin contexto)
)
# El modelo NO sabe qué tickets se mencionaron antes
```

## Cómo debería funcionar (con contexto conversacional)

```python
# Request 1: "¿Qué tickets hay sobre errores?"
prev_id = None  # Primera interacción
response = client.responses.create(
    input=[{"role": "user", "content": "¿Qué tickets hay sobre errores?"}],
    previous_response_id=prev_id
)
# response.id = "resp_abc123"
# ✅ GUARDAR: conversation_id -> "resp_abc123"

# Request 2: "¿Y cuáles son los más recientes?"
prev_id = obtener_ultimo_response_id(conversation_id)  # "resp_abc123"
response = client.responses.create(
    input=[{"role": "user", "content": "¿Y cuáles son los más recientes?"}],
    previous_response_id=prev_id  # ✅ Continúa desde la respuesta anterior
)
# response.id = "resp_def456"
# ✅ ACTUALIZAR: conversation_id -> "resp_def456"
# El modelo SÍ sabe qué tickets se mencionaron antes
```

## Implementación necesaria

### 1. Almacenamiento del último `response.id`

Necesitas guardar el `response.id` final de cada conversación:

```python
# Opción A: En memoria (simple, se pierde al reiniciar)
conversation_last_response = {}  # {conversation_id: response_id}

# Opción B: En base de datos (persistente)
# Tabla: conversation_sessions
# Campos: conversation_id, last_response_id, updated_at
```

### 2. Modificar el endpoint

```python
@router.post("/chat_v2")
async def chat_v2(req: ChatV2Request):
    # 1. Obtener el último response_id de esta conversación
    last_response_id = get_last_response_id(req.conversation_id)
    
    # 2. Usar ese response_id como punto de partida
    prev_id = last_response_id  # None si es primera vez
    
    # 3. En el loop, usar prev_id en la PRIMERA llamada
    for round_idx in range(1, 7):
        response = client.responses.create(
            model=os.getenv("V2_MODEL", "gpt-5-mini"),
            instructions=SYSTEM_INSTRUCTIONS,
            tools=TOOLS,
            input=next_input,
            previous_response_id=prev_id,  # ✅ Solo en round 1 usa el de la conversación anterior
        )
        
        # ... resto del código ...
        
        prev_id = response.id  # Para el siguiente round del mismo request
    
    # 4. Guardar el response.id final cuando termina
    final_response_id = prev_id  # El último del loop
    save_last_response_id(req.conversation_id, final_response_id)
    
    return {"classification": "V2", "response": response.output_text}
```

### 3. Flujo completo en la UI

```
Usuario envía mensaje 1: "Hola"
  → POST /chat_v2 {conversation_id: "conv_123", user_message: "Hola"}
  → prev_id = None (primera vez)
  → OpenAI crea respuesta, response.id = "resp_abc"
  → Guardar: conv_123 -> resp_abc
  → Retornar respuesta al usuario

Usuario envía mensaje 2: "¿Qué tickets hay?"
  → POST /chat_v2 {conversation_id: "conv_123", user_message: "¿Qué tickets hay?"}
  → prev_id = obtener("conv_123") = "resp_abc" ✅
  → OpenAI continúa desde resp_abc (tiene contexto de "Hola")
  → response.id = "resp_def"
  → Actualizar: conv_123 -> resp_def
  → Retornar respuesta al usuario

Usuario envía mensaje 3: "Muéstrame el primero"
  → POST /chat_v2 {conversation_id: "conv_123", user_message: "Muéstrame el primero"}
  → prev_id = obtener("conv_123") = "resp_def" ✅
  → OpenAI continúa desde resp_def (sabe qué tickets se mencionaron)
  → response.id = "resp_ghi"
  → Actualizar: conv_123 -> resp_ghi
  → Retornar respuesta al usuario
```

## Ventajas del Responses API

1. **Más simple**: No necesitas gestionar arrays de mensajes
2. **Menos tokens**: No envías todo el historial en cada request
3. **Contexto automático**: OpenAI maneja el contexto internamente
4. **Mejor para tool-calling**: El contexto de tool calls también se mantiene

## Consideraciones importantes

1. **Límite de contexto**: OpenAI tiene límites en cuánto contexto puede mantener. Si la conversación es muy larga, puede necesitar resetear.

2. **Expiración**: Los `response.id` pueden expirar después de cierto tiempo. Necesitas manejar errores y resetear si es necesario.

3. **Nuevas conversaciones**: Si el usuario quiere empezar de nuevo, simplemente no pases `previous_response_id` o usa un nuevo `conversation_id`.

4. **Múltiples usuarios**: Cada `conversation_id` debe ser único por usuario/sesión.

## Ejemplo de código completo

Ver el archivo `endpoints/chat_v2_conversational.py` para la implementación completa.

