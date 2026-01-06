# Guía de Adaptación del Widget V1 → V2

## Cambios Principales

### 1. **Endpoint Cambiado**
- **V1**: `/classify`
- **V2**: `/chat_v2`

### 2. **Estructura de Respuesta**
- **V1**: `{ conversation_id, interaction_id, response }`
- **V2**: `{ classification: "V2", response: "..." }`

### 3. **Contexto Conversacional**
- **V1**: El backend generaba un nuevo `conversation_id` en cada respuesta
- **V2**: El frontend genera el `conversation_id` una vez y lo reutiliza en todas las interacciones
- **V2**: El backend mantiene el contexto automáticamente usando `response_id` de OpenAI

### 4. **Autenticación (zToken)**

El widget V2 tiene un sistema mejorado para obtener el `zToken`:

#### Opción 1: Variable Global del Servidor (Recomendado)
```javascript
// En tu página HTML/ASP, antes de cargar el widget:
<script>
    window.zToken = '<%=Session("zToken")%>';  // O desde donde tengas el token
    window.vUserName = '<%=Session("vUserName")%>';
</script>
<script src="chat-widget-v2.js"></script>
```

#### Opción 2: localStorage
```javascript
// Si el token ya está guardado en localStorage:
localStorage.setItem('zToken', 'tu-token-aqui');
```

#### Opción 3: Endpoint de Sesión
Si tienes un endpoint que genera tokens (como `/start_session`), puedes llamarlo antes:

```javascript
// Ejemplo de obtención de token desde endpoint
async function obtenerToken() {
    const response = await fetch('/start_session', {
        method: 'POST',
        body: JSON.stringify({
            user_email: 'usuario@ejemplo.com',
            user_hash: 'hash-generado'
        })
    });
    const data = await response.json();
    return data.token;
}
```

## Configuración del Widget

### Variables a Configurar

1. **BACKEND_URL**: URL de tu backend
   ```javascript
   const BACKEND_URL = 'https://iaticketsv4.replit.app';
   ```

2. **SUPABASE_URL y SUPABASE_KEY**: Para el sistema de feedback
   ```javascript
   const SUPABASE_URL = 'https://lnelwrjmhggndokkjdes.supabase.co';
   const SUPABASE_KEY = 'tu-key-aqui';
   ```

## Diferencias Clave V1 vs V2

| Aspecto | V1 | V2 |
|---------|----|----|
| **Endpoint** | `/classify` | `/chat_v2` |
| **Conversation ID** | Backend lo genera | Frontend lo genera y reutiliza |
| **Contexto** | Se envía historial completo | Se mantiene automáticamente con `response_id` |
| **Interaction ID** | Viene del backend | Se genera localmente para feedback |
| **Respuesta** | `{conversation_id, interaction_id, response}` | `{classification: "V2", response: "..."}` |
| **zToken** | Hardcodeado | Sistema dinámico con múltiples fuentes |

## Flujo de Conversación V2

```
1. Usuario envía primer mensaje
   → Frontend genera: conversationId = "conv_123..."
   → POST /chat_v2 { conversation_id: "conv_123", user_message: "...", zToken: "...", userName: "..." }
   → Backend: prev_id = None (primera vez)
   → Backend: Guarda response_id para contexto
   → Frontend: Mantiene conversationId para siguiente mensaje

2. Usuario envía segundo mensaje
   → Frontend: Usa mismo conversationId = "conv_123"
   → POST /chat_v2 { conversation_id: "conv_123", ... }  ✅ Mismo ID
   → Backend: prev_id = obtener("conv_123") = "resp_abc" ✅
   → Backend: Continúa desde respuesta anterior (tiene contexto)
   → Backend: Actualiza response_id guardado
```

## Manejo de Errores

El widget V2 incluye mejor manejo de errores:

- **401/403**: Error de autenticación → Mensaje específico
- **500**: Error del servidor → Mensaje genérico
- **Otros**: Error de comunicación → Mensaje genérico

## Feedback

El sistema de feedback (👍/👎) funciona igual que en V1:
- Usa `conversation_id` y `interaction_id` (generado localmente)
- Se envía a Supabase mediante RPC `grade_response`

## Testing

Para probar el widget:

1. **Configura el zToken**:
   ```html
   <script>
       window.zToken = 'tu-token-valido';
       window.vUserName = 'Usuario Test';
   </script>
   <script src="chat-widget-v2.js"></script>
   ```

2. **Verifica la consola**:
   - Deberías ver: `V2 Response: { classification: "V2", response: "..." }`
   - Si hay errores, aparecerán en la consola

3. **Prueba el contexto**:
   - Envía: "Hola"
   - Luego: "¿Qué tickets hay?"
   - El bot debería recordar el saludo inicial

## Migración desde V1

Si ya tienes el widget V1 funcionando:

1. **Reemplaza el archivo**:
   ```html
   <!-- Antes -->
   <script src="chat-widget-nuevo.js"></script>
   
   <!-- Después -->
   <script src="chat-widget-v2.js"></script>
   ```

2. **Configura el zToken** (ver sección de autenticación arriba)

3. **Actualiza el BACKEND_URL** si es necesario

4. **Prueba la funcionalidad**:
   - Verifica que las respuestas lleguen correctamente
   - Prueba que el contexto se mantenga entre mensajes
   - Verifica que el feedback funcione

## Notas Importantes

1. **Conversation ID**: El widget genera un ID único por sesión. Si el usuario recarga la página, se genera uno nuevo (esto es correcto, es una nueva sesión).

2. **Contexto Persistente**: El backend mantiene el contexto usando `response_id` de OpenAI. Si el `response_id` expira, el backend lo detecta y limpia automáticamente.

3. **zToken**: Es crítico que el token sea válido. Si no se configura correctamente, las peticiones fallarán con error 401/403.

4. **Compatibilidad**: El widget V2 mantiene la misma UI y UX que V1, solo cambia la lógica de comunicación con el backend.

