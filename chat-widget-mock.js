// Chat Widget V2 Mock - Diseño Moderno estilo ChatGPT
(function() {
    'use strict';

    // Configuración
    const BACKEND_URL = (typeof window !== 'undefined' && window.BACKEND_URL) 
        ? window.BACKEND_URL 
        : 'http://localhost:5050';
    const CHAT_V2_ENDPOINT = `${BACKEND_URL}/chat_v2`;
    
    const SUPABASE_URL = 'https://lnelwrjmhggndokkjdes.supabase.co';
    const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxuZWx3cmptaGdnbmRva2tqZGVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkwODA2NTksImV4cCI6MjA2NDY1NjY1OX0.laY_1H7SeopDU-6fmTucO6ALZMyadYwP_S4EIQqkJ9E';

    // Estado
    let conversationId = '';
    let interactionId = '';
    let isOpen = false;
    let widgetContainer = null;

    // Obtener configuración
    const getUserName = () => {
        return (typeof window !== 'undefined' && window.vUserName) || 'Usuario';
    };

    const getZToken = () => {
        if (typeof window !== 'undefined' && window.zToken) {
            return window.zToken;
        }
        if (typeof localStorage !== 'undefined' && localStorage.getItem('zToken')) {
            return localStorage.getItem('zToken');
        }
        return 'test-token-dev';
    };

    // ============================================
    // ESTILOS Y TEMPLATE
    // ============================================
    const styles = `
        <style>
            #zell-chat-widget {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 10000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            }

            #zell-chat-button {
                width: 64px;
                height: 64px;
                border-radius: 50%;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                border: none;
                cursor: pointer;
                box-shadow: 0 4px 20px rgba(229, 165, 0, 0.4);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
                font-weight: 900;
                color: #000;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
            }

            #zell-chat-button:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 30px rgba(229, 165, 0, 0.6);
            }

            #zell-chat-button:active {
                transform: scale(0.95);
            }

            #zell-chat-popup {
                position: fixed;
                bottom: 90px;
                right: 20px;
                width: 500px;
                height: 700px;
                background: #ffffff;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                display: none;
                flex-direction: column;
                overflow: hidden;
                animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 10001;
            }

            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px) scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }

            #zell-chat-popup.open {
                display: flex;
            }

            .chat-header {
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                padding: 20px;
                color: #000;
                display: flex;
                align-items: center;
                justify-content: space-between;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }

            .chat-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .chat-header button {
                background: transparent;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #000;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                transition: background 0.2s;
            }

            .chat-header button:hover {
                background: rgba(0, 0, 0, 0.1);
            }

            .welcome-screen {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 40px 30px;
                text-align: center;
                background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
            }

            .welcome-screen.hidden {
                display: none;
            }

            .welcome-icon {
                width: 80px;
                height: 80px;
                border-radius: 50%;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 40px;
                margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(229, 165, 0, 0.3);
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0%, 100% {
                    transform: scale(1);
                }
                50% {
                    transform: scale(1.05);
                }
            }

            .welcome-title {
                font-size: 28px;
                font-weight: 700;
                color: #1a1a1a;
                margin-bottom: 12px;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }

            .welcome-subtitle {
                font-size: 16px;
                color: #666;
                margin-bottom: 32px;
                line-height: 1.5;
            }

            .welcome-features {
                display: flex;
                flex-direction: column;
                gap: 16px;
                width: 100%;
                max-width: 300px;
            }

            .feature-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                text-align: left;
            }

            .feature-icon {
                width: 32px;
                height: 32px;
                border-radius: 8px;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                flex-shrink: 0;
            }

            .feature-text {
                font-size: 14px;
                color: #333;
                font-weight: 500;
            }

            .chat-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }

            .chat-container .chat-messages {
                display: none;
            }

            .chat-container.active .chat-messages {
                display: flex;
            }

            .chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 24px;
                background: #f8f9fa;
                display: flex;
                flex-direction: column;
                gap: 16px;
            }

            .chat-messages::-webkit-scrollbar {
                width: 6px;
            }

            .chat-messages::-webkit-scrollbar-track {
                background: transparent;
            }

            .chat-messages::-webkit-scrollbar-thumb {
                background: #ddd;
                border-radius: 3px;
            }

            .message {
                display: flex;
                gap: 12px;
                animation: fadeIn 0.3s;
            }

            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .message.user {
                flex-direction: row-reverse;
            }

            .message-avatar {
                width: 36px;
                height: 36px;
                border-radius: 50%;
                flex-shrink: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                font-weight: 700;
            }

            .message.user .message-avatar {
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                color: #000;
            }

            .message.bot .message-avatar {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .message-content {
                max-width: 75%;
                padding: 12px 16px;
                border-radius: 18px;
                line-height: 1.5;
                font-size: 14px;
                word-wrap: break-word;
            }

            .message.user .message-content {
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                color: #000;
                border-bottom-right-radius: 4px;
            }

            .message.bot .message-content {
                background: white;
                color: #333;
                border-bottom-left-radius: 4px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            }

            .message-content pre {
                background: #f4f4f4;
                padding: 12px;
                border-radius: 8px;
                overflow-x: auto;
                font-size: 13px;
                margin: 8px 0;
            }

            .message-content code {
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 13px;
            }

            .thinking-indicator {
                display: flex;
                gap: 4px;
                padding: 12px 16px;
                background: white;
                border-radius: 18px;
                border-bottom-left-radius: 4px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            }

            .thinking-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #999;
                animation: bounce 1.4s infinite;
            }

            .thinking-dot:nth-child(2) {
                animation-delay: 0.2s;
            }

            .thinking-dot:nth-child(3) {
                animation-delay: 0.4s;
            }

            @keyframes bounce {
                0%, 80%, 100% {
                    transform: scale(0);
                    opacity: 0.5;
                }
                40% {
                    transform: scale(1);
                    opacity: 1;
                }
            }

            .chat-input-container {
                padding: 20px;
                background: white;
                border-top: 1px solid #e5e5e5;
                display: flex;
                gap: 12px;
                align-items: flex-end;
            }

            .chat-input-wrapper {
                flex: 1;
                position: relative;
            }

            .chat-input {
                width: 100%;
                min-height: 56px;
                max-height: 150px;
                padding: 16px 20px;
                border: 2px solid #e5e5e5;
                border-radius: 24px;
                font-size: 15px;
                font-family: inherit;
                resize: none;
                outline: none;
                transition: border-color 0.2s;
                box-sizing: border-box;
                line-height: 1.5;
            }

            .chat-input:focus {
                border-color: #e5a500;
            }

            .chat-send-button {
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
                flex-shrink: 0;
            }

            .chat-send-button:hover:not(:disabled) {
                transform: scale(1.05);
                box-shadow: 0 4px 12px rgba(229, 165, 0, 0.4);
            }

            .chat-send-button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            .chat-send-button svg {
                width: 20px;
                height: 20px;
                fill: #000;
            }

            @media (max-width: 480px) {
                #zell-chat-popup {
                    width: 100vw;
                    height: 100vh;
                    bottom: 0;
                    right: 0;
                    border-radius: 0;
                }
            }
        </style>
    `;

    // ============================================
    // FUNCIONES DE UTILIDAD
    // ============================================
    function formatMessage(text) {
        // Convertir saltos de línea
        let formatted = text.replace(/\n/g, '<br>');
        
        // Formatear código
        formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Formatear negritas
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Formatear listas
        formatted = formatted.replace(/^\- (.+)$/gm, '<li>$1</li>');
        formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        
        return formatted;
    }

    function scrollToBottom(container) {
        container.scrollTop = container.scrollHeight;
    }

    // ============================================
    // FUNCIONES DE UI
    // ============================================
    function createWelcomeScreen() {
        return `
            <div class="welcome-screen" id="welcome-screen">
                <div class="welcome-icon">🤖</div>
                <h2 class="welcome-title">Habla con la IA de Zell</h2>
                <p class="welcome-subtitle">Tu asistente inteligente para tickets, documentos y más</p>
                <div class="welcome-features">
                    <div class="feature-item">
                        <div class="feature-icon">🎫</div>
                        <div class="feature-text">Consulta información de tickets</div>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon">📄</div>
                        <div class="feature-text">Accede a documentos y políticas ISO</div>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon">💬</div>
                        <div class="feature-text">Responde tus preguntas en tiempo real</div>
                    </div>
                </div>
            </div>
        `;
    }

    function createChatContainer() {
        return `
            <div class="chat-container" id="chat-container">
                <div class="chat-messages" id="chat-messages"></div>
                <div class="chat-input-container">
                    <div class="chat-input-wrapper">
                        <textarea 
                            id="chat-input" 
                            class="chat-input" 
                            placeholder="Escribe tu mensaje..."
                            rows="2"
                        ></textarea>
                    </div>
                    <button id="chat-send" class="chat-send-button" title="Enviar">
                        <svg viewBox="0 0 24 24">
                            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }

    function createPopup() {
        return `
            <div id="zell-chat-popup">
                <div class="chat-header">
                    <h3>
                        <span>🤖</span>
                        <span>IA de Zell</span>
                    </h3>
                    <button id="chat-close" title="Cerrar">✕</button>
                </div>
                ${createWelcomeScreen()}
                ${createChatContainer()}
            </div>
        `;
    }

    function addMessage(content, isUser = false) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = isUser ? 'Tú' : '🤖';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = formatMessage(content);
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        
        messagesContainer.appendChild(messageDiv);
        scrollToBottom(messagesContainer);
    }

    function showThinking() {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'message bot';
        thinkingDiv.id = 'thinking-indicator';
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = '🤖';
        
        const thinkingContent = document.createElement('div');
        thinkingContent.className = 'thinking-indicator';
        thinkingContent.innerHTML = `
            <div class="thinking-dot"></div>
            <div class="thinking-dot"></div>
            <div class="thinking-dot"></div>
        `;
        
        thinkingDiv.appendChild(avatar);
        thinkingDiv.appendChild(thinkingContent);
        messagesContainer.appendChild(thinkingDiv);
        scrollToBottom(messagesContainer);
    }

    function removeThinking() {
        const thinking = document.getElementById('thinking-indicator');
        if (thinking) {
            thinking.remove();
        }
    }

    // ============================================
    // FUNCIONES DE COMUNICACIÓN
    // ============================================
    async function sendMessage(message) {
        if (!message.trim()) return;

        // Generar conversation_id si no existe
        if (!conversationId) {
            conversationId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }
        
        interactionId = `inter_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;

        // Mostrar mensaje del usuario
        addMessage(message, true);

        // Ocultar welcome screen y mostrar chat
        const welcomeScreen = document.getElementById('welcome-screen');
        const chatContainer = document.getElementById('chat-container');
        if (welcomeScreen && chatContainer) {
            welcomeScreen.classList.add('hidden');
            chatContainer.classList.add('active');
        }

        // Mostrar indicador de pensamiento
        showThinking();

        // Deshabilitar input
        const input = document.getElementById('chat-input');
        const sendButton = document.getElementById('chat-send');
        if (input) input.disabled = true;
        if (sendButton) sendButton.disabled = true;

        try {
            const response = await fetch(CHAT_V2_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${getZToken()}`
                },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    user_message: message,
                    zToken: getZToken(),
                    userName: getUserName()
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            removeThinking();
            
            const botResponse = data.response || 'Error de comunicación';
            addMessage(botResponse, false);

        } catch (error) {
            console.error('Error:', error);
            removeThinking();
            
            let errorMessage = 'Error de comunicación con el servidor.';
            if (error.message.includes('401') || error.message.includes('403')) {
                errorMessage = 'Error de autenticación. Por favor, verifica tu configuración.';
            } else if (error.message.includes('500')) {
                errorMessage = 'Error interno del servidor. Por favor, intenta de nuevo.';
            }
            
            addMessage(errorMessage, false);
        } finally {
            // Rehabilitar input
            if (input) {
                input.disabled = false;
                input.value = '';
                input.focus();
            }
            if (sendButton) sendButton.disabled = false;
        }
    }

    // ============================================
    // INICIALIZACIÓN
    // ============================================
    function init() {
        // Inyectar estilos
        document.head.insertAdjacentHTML('beforeend', styles);

        // Crear contenedor principal
        widgetContainer = document.createElement('div');
        widgetContainer.id = 'zell-chat-widget';
        widgetContainer.innerHTML = `
            <button id="zell-chat-button" title="Abrir chat">IA</button>
            ${createPopup()}
        `;
        document.body.appendChild(widgetContainer);

        // Event listeners
        const chatButton = document.getElementById('zell-chat-button');
        const chatPopup = document.getElementById('zell-chat-popup');
        const chatClose = document.getElementById('chat-close');
        const chatInput = document.getElementById('chat-input');
        const chatSend = document.getElementById('chat-send');

        // Toggle popup
        chatButton.addEventListener('click', () => {
            isOpen = !isOpen;
            if (isOpen) {
                chatPopup.classList.add('open');
                // Asegurar que el input esté habilitado y enfocado
                setTimeout(() => {
                    if (chatInput) {
                        chatInput.disabled = false;
                        chatInput.focus();
                    }
                }, 100);
            } else {
                chatPopup.classList.remove('open');
            }
        });

        // Cerrar popup
        chatClose.addEventListener('click', () => {
            isOpen = false;
            chatPopup.classList.remove('open');
        });

        // Enviar mensaje
        const handleSend = () => {
            const message = chatInput?.value.trim();
            if (message) {
                sendMessage(message);
            }
        };

        chatSend?.addEventListener('click', handleSend);

        chatInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });

        // Auto-resize textarea
        chatInput?.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 150) + 'px';
        });

        // Asegurar que el input esté habilitado y funcional desde el inicio
        if (chatInput) {
            chatInput.disabled = false;
            // El input ahora es visible desde el inicio (aunque los mensajes estén ocultos)
        }

        // Asegurar que el input esté habilitado al inicio
        if (chatInput) {
            chatInput.disabled = false;
        }
    }

    // Auto-inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

