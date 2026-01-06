# Ejemplo de UI Conversacional para chat_v2

## Cómo funciona en el Frontend

### 1. Estructura básica del componente

```javascript
// React/Vue/Angular ejemplo
class ChatComponent {
  constructor() {
    this.conversationId = null;  // Se genera o se obtiene del servidor
    this.messages = [];  // Historial visual para el usuario
  }

  // Inicializar o recuperar conversation_id
  async initializeConversation() {
    // Opción A: Generar nuevo ID en el frontend
    this.conversationId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Opción B: Obtener del servidor (si tienes endpoint para crear sesiones)
    // const response = await fetch('/api/conversations/new', { method: 'POST' });
    // this.conversationId = await response.json().conversation_id;
  }

  // Enviar mensaje
  async sendMessage(userMessage) {
    // Agregar mensaje del usuario a la UI
    this.messages.push({ role: 'user', content: userMessage });
    this.renderMessages();

    try {
      // Llamar al endpoint
      const response = await fetch('/chat_v2', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversation_id: this.conversationId,  // ✅ Mismo ID en cada request
          user_message: userMessage,
          zToken: this.getAuthToken(),
          userName: this.getUserName(),
        }),
      });

      const data = await response.json();
      
      // Agregar respuesta del bot a la UI
      this.messages.push({ role: 'assistant', content: data.response });
      this.renderMessages();

    } catch (error) {
      console.error('Error:', error);
      this.messages.push({ 
        role: 'assistant', 
        content: 'Error al procesar tu mensaje. Por favor intenta de nuevo.' 
      });
      this.renderMessages();
    }
  }

  // Limpiar contexto (empezar nueva conversación)
  async clearContext() {
    try {
      await fetch('/chat_v2/clear_context', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversation_id: this.conversationId,
          zToken: this.getAuthToken(),
          userName: this.getUserName(),
        }),
      });
      
      // Opcional: generar nuevo conversation_id
      // this.conversationId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      this.messages = [];
      this.renderMessages();
    } catch (error) {
      console.error('Error al limpiar contexto:', error);
    }
  }
}
```

### 2. Flujo de interacción

```
Usuario: "Hola"
  → POST /chat_v2 {conversation_id: "conv_123", user_message: "Hola"}
  → Backend: prev_id = None (primera vez)
  → OpenAI: Crea respuesta, response.id = "resp_abc"
  → Backend: Guarda conv_123 -> resp_abc
  → Frontend: Muestra "Hola, ¿en qué puedo ayudarte?"

Usuario: "¿Qué tickets hay sobre errores?"
  → POST /chat_v2 {conversation_id: "conv_123", user_message: "¿Qué tickets hay sobre errores?"}
  → Backend: prev_id = obtener("conv_123") = "resp_abc" ✅
  → OpenAI: Continúa desde resp_abc (tiene contexto de "Hola")
  → OpenAI: Usa tools, busca tickets, response.id = "resp_def"
  → Backend: Actualiza conv_123 -> resp_def
  → Frontend: Muestra lista de tickets

Usuario: "Muéstrame el primero"
  → POST /chat_v2 {conversation_id: "conv_123", user_message: "Muéstrame el primero"}
  → Backend: prev_id = obtener("conv_123") = "resp_def" ✅
  → OpenAI: Continúa desde resp_def (sabe qué tickets se mencionaron)
  → OpenAI: Usa get_item para obtener detalles, response.id = "resp_ghi"
  → Backend: Actualiza conv_123 -> resp_ghi
  → Frontend: Muestra detalles del ticket
```

### 3. Ejemplo completo con React

```jsx
import React, { useState, useEffect } from 'react';

function ChatV2() {
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  // Inicializar conversation_id al montar
  useEffect(() => {
    const newId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setConversationId(newId);
  }, []);

  const sendMessage = async () => {
    if (!input.trim() || !conversationId) return;

    const userMessage = input.trim();
    setInput('');
    
    // Agregar mensaje del usuario
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await fetch('/chat_v2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,  // ✅ Mismo ID
          user_message: userMessage,
          zToken: localStorage.getItem('zToken'),
          userName: localStorage.getItem('userName'),
        }),
      });

      const data = await response.json();
      
      // Agregar respuesta del bot
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: data.response 
      }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Error al procesar tu mensaje.' 
      }]);
    } finally {
      setLoading(false);
    }
  };

  const clearContext = async () => {
    try {
      await fetch('/chat_v2/clear_context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          zToken: localStorage.getItem('zToken'),
          userName: localStorage.getItem('userName'),
        }),
      });
      
      setMessages([]);
      // Opcional: generar nuevo conversation_id
      const newId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setConversationId(newId);
    } catch (error) {
      console.error('Error al limpiar contexto:', error);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Chat V2</h2>
        <button onClick={clearContext}>Nueva Conversación</button>
      </div>
      
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <strong>{msg.role === 'user' ? 'Tú' : 'Bot'}:</strong>
            <p>{msg.content}</p>
          </div>
        ))}
        {loading && <div className="loading">Pensando...</div>}
      </div>
      
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Escribe tu mensaje..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          Enviar
        </button>
      </div>
    </div>
  );
}

export default ChatV2;
```

### 4. Puntos clave

1. **Mismo `conversation_id`**: Usa el mismo ID en todos los requests de la misma sesión
2. **No necesitas enviar historial**: El backend maneja el contexto automáticamente
3. **Limpieza opcional**: Puedes limpiar el contexto si el usuario quiere empezar de nuevo
4. **Manejo de errores**: Si el `response_id` expira, el backend lo maneja automáticamente

### 5. Ventajas vs Chat Completions tradicional

| Aspecto | Chat Completions | Responses API |
|---------|------------------|---------------|
| Historial | Debes enviar todo el historial | Solo envías el último `response_id` |
| Tokens | Más tokens (todo el historial) | Menos tokens (solo el mensaje actual) |
| Complejidad | Más complejo (gestionar arrays) | Más simple (solo un ID) |
| Contexto | Cliente gestiona contexto | OpenAI gestiona contexto |

### 6. Consideraciones

- **Persistencia**: Si quieres que las conversaciones sobrevivan reinicios del servidor, migra el almacenamiento a base de datos
- **Múltiples pestañas**: Si el usuario abre múltiples pestañas, cada una debería tener su propio `conversation_id`
- **Expiración**: Los `response_id` pueden expirar después de cierto tiempo (el backend lo maneja automáticamente)
- **Límites**: OpenAI tiene límites en el contexto. Conversaciones muy largas pueden necesitar resetear

