# Checklist para Probar el Widget V2 (Mockup)

## 🔧 Configuración del Backend

### 1. Variables de Entorno Necesarias

```bash
# OpenAI API Keys (REQUERIDO para V2)
OPENAI_API_KEY_V2=sk-...          # O usa OPENAI_API_KEY como fallback
# O alternativamente:
OPENAI_API_KEY=sk-...             # Fallback si no existe V2

# Modelo a usar (opcional, default: "gpt-5-mini")
V2_MODEL=gpt-5-mini               # O gpt-4o, gpt-4-turbo, etc.

# Autenticación (para desarrollo local)
SKIP_AUTH=1                       # ⚠️ SOLO para desarrollo local, NO en producción

# Debugging (opcional)
TRACE_V2=1                        # Activa logs detallados de tool calls

# Zell API (para herramientas de tickets)
ZELL_API_KEY=...
ZELL_USER=...
ZELL_PASSWORD=...
```

### 2. Verificar que el Endpoint Esté Registrado

En `main.py` debe estar:
```python
from endpoints.chat_v2 import router as chat_v2_router
app.include_router(chat_v2_router)
```

### 3. CORS Configurado

El backend debe permitir requests desde tu origen:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # O especifica tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🎨 Configuración del Widget (Frontend)

### 1. Archivo HTML de Prueba

Crea un archivo `test-widget.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Widget V2</title>
</head>
<body>
    <h1>Test Widget V2</h1>
    <p>Haz clic en el botón "IA" en la esquina inferior izquierda.</p>
    
    <!-- Configurar variables antes de cargar el widget -->
    <script>
        // ⚠️ IMPORTANTE: Configura estos valores según tu entorno
        
        // Opción 1: Token hardcodeado para testing (solo desarrollo)
        window.zToken = 'YOUR_ZTOKEN_HERE';  // Obtén un token válido desde /start_session
        
        // Opción 2: Obtener token desde endpoint
        // async function obtenerToken() {
        //     const response = await fetch('http://localhost:5050/start_session', {
        //         method: 'POST',
        //         headers: { 'Content-Type': 'application/json' },
        //         body: JSON.stringify({
        //             user_email: 'test@ejemplo.com',
        //             user_hash: 'hash-generado'
        //         })
        //     });
        //     const data = await response.json();
        //     window.zToken = data.token;
        // }
        // obtenerToken();
        
        window.vUserName = 'Usuario Test';
        
        // URL del backend (ajusta según tu entorno)
        window.BACKEND_URL = 'http://localhost:5050';  // Local
        // window.BACKEND_URL = 'https://iaticketsv4.replit.app';  // Producción
    </script>
    
    <!-- Cargar el widget -->
    <script src="chat-widget-v2.js"></script>
</body>
</html>
```

### 2. Ajustar URLs en el Widget

En `chat-widget-v2.js`, línea 9:
```javascript
// Opción A: Usar variable global
const BACKEND_URL = window.BACKEND_URL || 'http://localhost:5050';

// Opción B: Hardcodear (solo para testing)
const BACKEND_URL = 'http://localhost:5050';  // Local
// const BACKEND_URL = 'https://iaticketsv4.replit.app';  // Producción
```

---

## ✅ Checklist de Verificación

### Backend

- [ ] **Servidor corriendo**: `uvicorn main:app --reload` o similar
- [ ] **Puerto correcto**: Verifica que el puerto coincida con `BACKEND_URL` del widget
- [ ] **Variables de entorno cargadas**: `.env` configurado o variables exportadas
- [ ] **OPENAI_API_KEY_V2 o OPENAI_API_KEY**: Debe estar configurado
- [ ] **SKIP_AUTH=1**: Si estás en desarrollo local y no tienes token válido
- [ ] **Endpoint registrado**: `/chat_v2` debe estar disponible
- [ ] **CORS habilitado**: Permite requests desde tu origen

### Frontend

- [ ] **zToken configurado**: Ya sea hardcodeado, desde localStorage, o desde endpoint
- [ ] **BACKEND_URL correcta**: Debe apuntar a tu servidor
- [ ] **Widget cargado**: No hay errores en la consola del navegador
- [ ] **Botón "IA" visible**: Aparece en la esquina inferior izquierda

### Testing

- [ ] **Abrir consola del navegador**: F12 → Console
- [ ] **Hacer clic en botón "IA"**: Debe abrir el widget
- [ ] **Enviar mensaje de prueba**: "Hola"
- [ ] **Verificar respuesta**: Debe llegar una respuesta del bot
- [ ] **Verificar logs del backend**: Debe aparecer en `logs/chat_v2_interactions.csv`

---

## 🐛 Debugging

### Errores Comunes

#### 1. **Error 401/403 (No autorizado)**
```
Solución:
- Verifica que SKIP_AUTH=1 esté configurado (solo desarrollo)
- O genera un token válido desde /start_session
- Verifica que el token esté en window.zToken o localStorage
```

#### 2. **Error CORS**
```
Solución:
- Verifica que CORS esté habilitado en el backend
- Verifica que el origen esté permitido
- Si usas file://, prueba con un servidor local (python -m http.server)
```

#### 3. **Error 500 (Error del servidor)**
```
Solución:
- Revisa los logs del backend
- Verifica que OPENAI_API_KEY esté configurado
- Activa TRACE_V2=1 para ver más detalles
- Revisa logs/chat_v2_interactions.csv
```

#### 4. **"zToken no encontrado"**
```
Solución:
- Configura window.zToken antes de cargar el widget
- O genera un token desde /start_session
- O usa SKIP_AUTH=1 en el backend (solo desarrollo)
```

#### 5. **Widget no aparece**
```
Solución:
- Verifica que el script se cargue correctamente
- Revisa la consola del navegador por errores JavaScript
- Verifica que no haya conflictos con otros scripts
```

### Activar Logs Detallados

En el backend, configura:
```bash
export TRACE_V2=1
```

Esto mostrará en la consola del servidor:
- Cada round del tool-calling loop
- Tool calls realizados
- Respuestas de las tools
- Response IDs guardados

### Verificar Logs

1. **Logs del backend**: `logs/chat_v2_interactions.csv`
   - Timestamp, usuario, mensaje, respuesta, etc.

2. **Logs del navegador**: F12 → Console
   - Requests/responses
   - Errores de JavaScript
   - Warnings del widget

---

## 🧪 Casos de Prueba Sugeridos

### Test 1: Saludo Inicial
```
Usuario: "Hola"
Esperado: Respuesta de saludo del bot
```

### Test 2: Contexto Conversacional
```
Usuario: "Hola"
Bot: "¡Hola! ¿En qué puedo ayudarte?"

Usuario: "¿Qué tickets hay sobre errores?"
Esperado: El bot debe recordar el saludo y buscar tickets
```

### Test 3: Búsqueda de Tickets
```
Usuario: "¿Qué tickets hay sobre errores?"
Esperado: Lista de tickets relacionados con errores
```

### Test 4: Ticket Específico
```
Usuario: "Tráeme el ticket 36816"
Esperado: Información completa del ticket 36816
```

### Test 5: Documentos ISO
```
Usuario: "¿Cuál es la política de calidad?"
Esperado: Información de documentos ISO/políticas
```

### Test 6: Reuniones
```
Usuario: "¿Qué temas se trataron en la reunión del 4 de julio?"
Esperado: Información de la minuta de reunión
```

### Test 7: Consultas SQL
```
Usuario: "¿Cuántos tickets abiertos hay en diciembre?"
Esperado: Conteo de tickets con filtros aplicados
```

---

## 📝 Notas Importantes

### Desarrollo Local

1. **SKIP_AUTH=1**: Úsalo SOLO en desarrollo local. En producción, siempre valida tokens.

2. **Servidor Local**: Si pruebas con `file://`, usa un servidor HTTP:
   ```bash
   python -m http.server 8000
   # Luego abre: http://localhost:8000/test-widget.html
   ```

3. **CORS Local**: Si el backend está en `localhost:5050` y el frontend en `localhost:8000`, CORS debe permitir ambos orígenes.

### Producción

1. **Token Real**: Nunca uses `SKIP_AUTH=1` en producción. Siempre valida tokens.

2. **HTTPS**: Asegúrate de usar HTTPS en producción.

3. **URLs Correctas**: Verifica que `BACKEND_URL` apunte a tu servidor de producción.

---

## 🚀 Pasos Rápidos para Empezar

1. **Backend**:
   ```bash
   # Configurar .env
   echo "SKIP_AUTH=1" >> .env
   echo "OPENAI_API_KEY_V2=sk-..." >> .env
   echo "TRACE_V2=1" >> .env
   
   # Iniciar servidor
   uvicorn main:app --reload --port 5050
   ```

2. **Frontend**:
   ```bash
   # Crear test-widget.html (ver arriba)
   # Ajustar BACKEND_URL en chat-widget-v2.js
   # Abrir en navegador: http://localhost:8000/test-widget.html
   ```

3. **Probar**:
   - Abrir consola del navegador (F12)
   - Clic en botón "IA"
   - Enviar mensaje: "Hola"
   - Verificar respuesta

---

## 📊 Verificar que Funciona

### Señales de Éxito

✅ Widget aparece al hacer clic en "IA"  
✅ Mensajes se envían sin errores en consola  
✅ Respuestas llegan del backend  
✅ Se crea/actualiza `logs/chat_v2_interactions.csv`  
✅ El contexto se mantiene entre mensajes (segundo mensaje recuerda el primero)  
✅ No hay errores 401/403/500 en la consola  

### Si Algo Falla

1. Revisa la consola del navegador (F12)
2. Revisa los logs del servidor
3. Revisa `logs/chat_v2_interactions.csv`
4. Activa `TRACE_V2=1` para más detalles
5. Verifica que todas las variables de entorno estén configuradas

