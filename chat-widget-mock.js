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
                padding: 30px 25px;
                text-align: center;
                background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
            }

            .welcome-screen.hidden {
                display: none;
            }

            .welcome-icon {
                width: 65px;
                height: 65px;
                border-radius: 50%;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                margin-bottom: 18px;
                box-shadow: 0 6px 18px rgba(229, 165, 0, 0.3);
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
                font-size: 24px;
                font-weight: 700;
                color: #1a1a1a;
                margin-bottom: 8px;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }

            .welcome-subtitle {
                font-size: 14px;
                color: #666;
                margin-bottom: 24px;
                line-height: 1.4;
            }

            .welcome-features {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                width: 100%;
                max-width: 425px;
            }

            .feature-item {
                display: flex;
                align-items: center;
                gap: 9px;
                padding: 9px 11px;
                background: white;
                border-radius: 9px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                text-align: left;
                transition: transform 0.2s, box-shadow 0.2s;
                cursor: pointer;
            }

            .feature-item:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            }

            .feature-info-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: none;
                align-items: center;
                justify-content: center;
                z-index: 10002;
                padding: 20px;
            }

            .feature-info-modal.open {
                display: flex;
            }

            .feature-info-content {
                background: white;
                border-radius: 16px;
                max-width: 500px;
                width: 100%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            .feature-info-header {
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                padding: 20px;
                border-radius: 16px 16px 0 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .feature-info-header h3 {
                margin: 0;
                font-size: 20px;
                font-weight: 700;
                color: #000;
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .feature-info-close {
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

            .feature-info-close:hover {
                background: rgba(0, 0, 0, 0.1);
            }

            .feature-info-body {
                padding: 24px;
            }

            .feature-info-section {
                margin-bottom: 24px;
            }

            .feature-info-section:last-child {
                margin-bottom: 0;
            }

            .feature-info-section h4 {
                margin: 0 0 12px 0;
                font-size: 16px;
                font-weight: 700;
                color: #1a1a1a;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .feature-info-section p {
                margin: 0 0 12px 0;
                font-size: 14px;
                color: #555;
                line-height: 1.6;
            }

            .feature-examples {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
                margin-top: 8px;
            }

            .feature-example {
                padding: 8px 12px;
                background: white;
                border-radius: 6px;
                margin-bottom: 8px;
                font-size: 13px;
                color: #333;
                border-left: 3px solid #e5a500;
                cursor: pointer;
                transition: background 0.2s;
            }

            .feature-example:hover {
                background: #fff9e6;
            }

            .feature-example:last-child {
                margin-bottom: 0;
            }

            .feature-tips {
                background: #e8f4f8;
                border-left: 4px solid #0c5460;
                padding: 12px;
                border-radius: 6px;
                margin-top: 8px;
            }

            .feature-tips ul {
                margin: 8px 0 0 0;
                padding-left: 20px;
            }

            .feature-tips li {
                font-size: 13px;
                color: #0c5460;
                margin-bottom: 6px;
                line-height: 1.5;
            }

            .feature-tips li:last-child {
                margin-bottom: 0;
            }

            .feature-icon {
                width: 28px;
                height: 28px;
                border-radius: 7px;
                background: linear-gradient(135deg, #e5a500 0%, #ffcd3c 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 15px;
                flex-shrink: 0;
            }

            .feature-text {
                font-size: 12px;
                color: #333;
                font-weight: 500;
                line-height: 1.3;
            }

            @media (max-width: 500px) {
                .welcome-features {
                    grid-template-columns: 1fr;
                    max-width: 100%;
                }
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
                flex-direction: column;
                gap: 8px;
                padding: 12px 16px;
                background: white;
                border-radius: 18px;
                border-bottom-left-radius: 4px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            }
            
            .thinking-dots {
                display: flex;
                flex-direction: row;
                gap: 4px;
                align-items: center;
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

            .live-steps-container {
                margin-top: 8px;
                min-height: 20px;
            }

            .live-step {
                font-size: 12px;
                color: #666;
                line-height: 1.4;
                opacity: 0;
                transform: translateY(-5px);
                transition: opacity 0.4s ease, transform 0.4s ease;
                padding: 2px 0;
            }

            .live-step.active {
                opacity: 1;
                transform: translateY(0);
            }

            .live-step.fading-out {
                opacity: 0;
                transform: translateY(5px);
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
    // FUNCIONES DE INFORMACIÓN DE FEATURES
    // ============================================
    const featureInfo = {
        tickets: {
            title: '🎫 Consulta información de tickets',
            description: 'Busca y consulta información detallada de tickets del sistema. Puedes buscar por número específico, palabras clave, o usar búsqueda semántica para encontrar tickets relacionados.',
            examples: [
                'Muéstrame el ticket 36816',
                '¿En qué ticket se habló de migración ISSTEY?',
                'Busca tickets sobre domiciliación',
                'Tickets abiertos por Javier en diciembre'
            ],
            tips: [
                'Para tickets específicos, menciona el número directamente (ej: "ticket 12345")',
                'Usa búsqueda semántica para encontrar tickets relacionados por concepto',
                'Puedes pedir comentarios y detalles completos de cualquier ticket',
                'Combina búsquedas: "tickets de Exitus sobre errores de configuración"'
            ]
        },
        etiquetas: {
            title: '🏷️ Etiquetas del sistema ZELL',
            description: 'Busca etiquetas del sistema ZELL por nombre de columna, descripción o código. Encuentra qué etiqueta corresponde a cada campo de la base de datos y obtén su información completa.',
            examples: [
                '¿Qué etiqueta corresponde a Person ID?',
                'Buscar etiqueta para número de identificación',
                'Etiqueta Person Full Name',
                '¿Cuál es la etiqueta para nombre de persona?'
            ],
            tips: [
                'Puedes buscar por nombre técnico de columna (ej: "Person ID")',
                'También puedes buscar por descripción en español',
                'Menciona el código de etiqueta si lo conoces (ej: "[i101: PID]")',
                'La búsqueda encuentra coincidencias tanto en español como en inglés'
            ]
        },
        guias: {
            title: '📚 Guías de usuario del sistema',
            description: 'Accede a guías paso a paso para usar el sistema Zell. Encuentra instrucciones detalladas sobre cómo configurar módulos, realizar procesos y usar funcionalidades del sistema.',
            examples: [
                '¿Cómo hacer reintentos de domiciliación?',
                'Pasos para configurar políticas de autorización',
                '¿Cómo cargar una tabla de amortización personalizada?',
                'Guía para ingresar al módulo de cobranza'
            ],
            tips: [
                'Menciona "en Zell" o "en el sistema" para buscar guías específicas',
                'Incluye nombres de módulos (Cobranza, Domiciliación, Tickets, etc.)',
                'Pide "pasos para..." o "cómo hacer..." para obtener instrucciones',
                'Las guías incluyen numeración de pasos para seguir el proceso ordenadamente'
            ]
        },
        documentos: {
            title: '📄 Documentos y políticas ISO',
            description: 'Consulta políticas organizacionales, procedimientos administrativos, manuales ISO y reglamentos internos. Información oficial sobre estándares y lineamientos de la empresa.',
            examples: [
                '¿Cuál es la política de seguridad de la información?',
                'Buscar procedimiento de control de accesos',
                '¿Qué dice el manual ISO sobre gestión de incidentes?',
                'Políticas de continuidad del negocio'
            ],
            tips: [
                'Usa términos como "política", "procedimiento", "manual ISO"',
                'Menciona códigos de documentos si los conoces (ej: "P-SGSI-01")',
                'Puedes buscar por dominio o familia de documentos',
                'Los resultados incluyen fecha de emisión y revisión'
            ]
        },
        soluciones: {
            title: '💡 Soluciones en tickets similares',
            description: 'Encuentra soluciones documentadas a problemas similares. Busca en tickets cerrados o resueltos para ver cómo se solucionaron casos parecidos anteriormente.',
            examples: [
                '¿Cómo se resolvió el problema de migración ISSTEY?',
                'Busca soluciones para errores de domiciliación',
                '¿Hay solución documentada para este problema?',
                'Tickets similares al 36816 que tengan solución'
            ],
            tips: [
                'Menciona el problema específico que estás enfrentando',
                'Puedes proporcionar un ticket de referencia para buscar similares',
                'Los tickets cerrados/resueltos tienen mayor prioridad',
                'Incluye términos técnicos o nombres de módulos para mejores resultados'
            ]
        },
        conteos: {
            title: '📊 Conteos y análisis de tickets',
            description: 'Obtén estadísticas y análisis cuantitativos de tickets. Cuenta tickets por criterios específicos, filtra por fechas, personas, clientes o estatus.',
            examples: [
                '¿Cuántos tickets se abrieron en diciembre?',
                'Tickets activos de Exitus',
                '¿Cuántos tickets tiene Javier abiertos?',
                'Tickets en estatus Desarrollo del último mes'
            ],
            tips: [
                'Usa preguntas cuantitativas: "cuántos", "cuántas", "conteo"',
                'Especifica períodos de tiempo (diciembre, último mes, 2024)',
                'Combina múltiples filtros: cliente + estatus + fecha',
                'Puedes pedir listas de tickets con sus campos principales'
            ]
        },
        reuniones: {
            title: '👥 Reuniones semanales y minutas',
            description: 'Consulta minutas de reuniones semanales donde se discuten problemas, soluciones y experiencias del equipo. Encuentra casos similares y decisiones tomadas.',
            examples: [
                '¿Alguien ha tenido este problema antes?',
                '¿Cómo se resolvió esto en reuniones anteriores?',
                'Buscar temas sobre domiciliación en reuniones',
                '¿Qué se habló en la reunión del 4 de julio?'
            ],
            tips: [
                'Usa frases como "problema similar", "experiencia similar", "caso parecido"',
                'Menciona fechas específicas si las conoces',
                'Puedes buscar por tema o asunto discutido',
                'Los resultados incluyen fecha, participantes y temas tratados'
            ]
        },
        'tiempo-real': {
            title: '🌐 Información en tiempo real',
            description: 'Obtén información actualizada de Internet: tipo de cambio, clima, noticias recientes y eventos socioeconómicos. Datos que cambian frecuentemente y no están en el conocimiento interno.',
            examples: [
                '¿Cuál es el tipo de cambio peso dólar hoy?',
                'Clima en Ciudad de México',
                'Noticias de hoy sobre tecnología',
                '¿Cuál es la inflación actual?'
            ],
            tips: [
                'Usa palabras clave como "hoy", "actual", "en tiempo real"',
                'Para monedas: menciona las monedas específicas (peso/dólar, euro)',
                'Para clima: incluye la ciudad o ubicación',
                'Esta herramienta se usa automáticamente cuando se necesita información actualizada'
            ]
        }
    };

    function showFeatureInfo(featureKey) {
        const info = featureInfo[featureKey];
        if (!info) return;

        const modal = document.getElementById('feature-info-modal');
        const title = document.getElementById('feature-info-title');
        const body = document.getElementById('feature-info-body');

        if (!modal || !title || !body) return;

        title.innerHTML = info.title;
        
        let examplesHTML = '';
        info.examples.forEach((example, idx) => {
            // Usar índice para evitar problemas con comillas
            const safeExample = example.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            examplesHTML += `<div class="feature-example" data-example="${safeExample}">${example}</div>`;
        });

        let tipsHTML = '<ul>';
        info.tips.forEach(tip => {
            tipsHTML += `<li>${tip}</li>`;
        });
        tipsHTML += '</ul>';

        body.innerHTML = `
            <div class="feature-info-section">
                <h4>📖 ¿Qué hace?</h4>
                <p>${info.description}</p>
            </div>
            <div class="feature-info-section">
                <h4>💬 Ejemplos de preguntas</h4>
                <p>Haz clic en cualquier ejemplo para usarlo:</p>
                <div class="feature-examples">
                    ${examplesHTML}
                </div>
            </div>
            <div class="feature-info-section">
                <h4>✨ Cómo aumentar efectividad</h4>
                <div class="feature-tips">
                    ${tipsHTML}
                </div>
            </div>
        `;

        modal.classList.add('open');
    }

    function insertExample(text) {
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.value = text;
            chatInput.focus();
            // Cerrar el modal
            const modal = document.getElementById('feature-info-modal');
            if (modal) {
                modal.classList.remove('open');
            }
            // Ocultar welcome screen y mostrar chat
            const welcomeScreen = document.getElementById('welcome-screen');
            const chatContainer = document.getElementById('chat-container');
            if (welcomeScreen && chatContainer) {
                welcomeScreen.classList.add('hidden');
                chatContainer.classList.add('active');
            }
        }
    }

    // Hacer insertExample disponible globalmente
    window.insertExample = insertExample;

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
                    <div class="feature-item" data-feature="tickets">
                        <div class="feature-icon">🎫</div>
                        <div class="feature-text">Consulta información de tickets</div>
                    </div>
                    <div class="feature-item" data-feature="etiquetas">
                        <div class="feature-icon">🏷️</div>
                        <div class="feature-text">Etiquetas del sistema ZELL</div>
                    </div>
                    <div class="feature-item" data-feature="guias">
                        <div class="feature-icon">📚</div>
                        <div class="feature-text">Guías de usuario del sistema</div>
                    </div>
                    <div class="feature-item" data-feature="documentos">
                        <div class="feature-icon">📄</div>
                        <div class="feature-text">Documentos y políticas ISO</div>
                    </div>
                    <div class="feature-item" data-feature="soluciones">
                        <div class="feature-icon">💡</div>
                        <div class="feature-text">Soluciones en tickets similares</div>
                    </div>
                    <div class="feature-item" data-feature="conteos">
                        <div class="feature-icon">📊</div>
                        <div class="feature-text">Conteos y análisis de tickets</div>
                    </div>
                    <div class="feature-item" data-feature="reuniones">
                        <div class="feature-icon">👥</div>
                        <div class="feature-text">Reuniones semanales y minutas</div>
                    </div>
                    <div class="feature-item" data-feature="tiempo-real">
                        <div class="feature-icon">🌐</div>
                        <div class="feature-text">Información en tiempo real</div>
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

    function createFeatureInfoModal() {
        return `
            <div class="feature-info-modal" id="feature-info-modal">
                <div class="feature-info-content">
                    <div class="feature-info-header">
                        <h3 id="feature-info-title"></h3>
                        <button class="feature-info-close" id="feature-info-close">✕</button>
                    </div>
                    <div class="feature-info-body" id="feature-info-body"></div>
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
            ${createFeatureInfoModal()}
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
            <div class="thinking-dots">
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
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
    // FUNCIONES DE LIVE STEPS
    // ============================================
    
    function showLiveStep(message) {
        // Buscar el thinking indicator
        const thinking = document.getElementById('thinking-indicator');
        if (!thinking) return;
        
        // Buscar el thinking-content (donde están los dots)
        const thinkingContent = thinking.querySelector('.thinking-indicator');
        if (!thinkingContent) return;
        
        // Crear o obtener el contenedor de live steps
        let stepsContainer = thinkingContent.querySelector('.live-steps-container');
        if (!stepsContainer) {
            stepsContainer = document.createElement('div');
            stepsContainer.className = 'live-steps-container';
            thinkingContent.appendChild(stepsContainer);
        }
        
        // Remover step anterior con fade-out
        const previousStep = stepsContainer.querySelector('.live-step.active');
        if (previousStep) {
            previousStep.classList.remove('active');
            previousStep.classList.add('fading-out');
            setTimeout(() => previousStep.remove(), 300);
        }
        
        // Crear nuevo step
        const step = document.createElement('div');
        step.className = 'live-step';
        step.textContent = message;
        
        stepsContainer.appendChild(step);
        
        // Activar animación fade-in
        setTimeout(() => {
            step.classList.add('active');
        }, 10);
    }
    
    function removeLiveSteps() {
        const thinking = document.getElementById('thinking-indicator');
        if (thinking) {
            const thinkingContent = thinking.querySelector('.thinking-indicator');
            if (thinkingContent) {
                const stepsContainer = thinkingContent.querySelector('.live-steps-container');
                if (stepsContainer) {
                    stepsContainer.remove();
                }
            }
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

        // Intentar usar SSE (streaming) primero, fallback a request normal
        const useStreaming = true;
        
        if (useStreaming) {
            try {
                await sendMessageWithStreaming(message, input, sendButton);
                return;
            } catch (streamError) {
                console.warn('Streaming falló, usando request normal:', streamError);
                // Continuar con request normal como fallback
            }
        }

        // Fallback: request normal (sin streaming)
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
            removeLiveSteps();
            
            const botResponse = data.response || 'Error de comunicación';
            addMessage(botResponse, false);

        } catch (error) {
            console.error('Error:', error);
            removeThinking();
            removeLiveSteps();
            
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

    async function sendMessageWithStreaming(message, input, sendButton) {
        const STREAM_ENDPOINT = `${BACKEND_URL}/chat_v2/stream`;
        
        // Enviar request POST para iniciar el stream
        const response = await fetch(STREAM_ENDPOINT, {
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

        // Leer stream de Server-Sent Events
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResponse = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Guardar línea incompleta

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.type === 'status') {
                                // Mostrar live step
                                showLiveStep(data.message);
                            } else if (data.type === 'response') {
                                // Remover live steps y mostrar respuesta final
                                removeLiveSteps();
                                removeThinking();
                                finalResponse = data.content;
                                addMessage(finalResponse, false);
                                
                                // Rehabilitar input
                                if (input) {
                                    input.disabled = false;
                                    input.value = '';
                                    input.focus();
                                }
                                if (sendButton) sendButton.disabled = false;
                                return; // Salir del loop
                            } else if (data.type === 'error') {
                                removeLiveSteps();
                                removeThinking();
                                addMessage(`Error: ${data.message}`, false);
                                
                                // Rehabilitar input
                                if (input) {
                                    input.disabled = false;
                                    input.value = '';
                                    input.focus();
                                }
                                if (sendButton) sendButton.disabled = false;
                                return;
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }

            // Si no se recibió respuesta, mostrar error
            if (!finalResponse) {
                removeLiveSteps();
                removeThinking();
                addMessage('No se recibió respuesta del servidor.', false);
                
                if (input) {
                    input.disabled = false;
                    input.value = '';
                    input.focus();
                }
                if (sendButton) sendButton.disabled = false;
            }
        } catch (streamError) {
            console.error('Error en stream:', streamError);
            removeLiveSteps();
            removeThinking();
            throw streamError; // Re-lanzar para que el catch principal lo maneje
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

        // Event listeners para feature items
        const featureItems = document.querySelectorAll('.feature-item');
        featureItems.forEach(item => {
            item.addEventListener('click', () => {
                const featureKey = item.getAttribute('data-feature');
                if (featureKey) {
                    showFeatureInfo(featureKey);
                }
            });
        });

        // Event listeners para ejemplos (usando delegación de eventos)
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('feature-example')) {
                const exampleText = e.target.getAttribute('data-example');
                if (exampleText) {
                    // Decodificar entidades HTML
                    const textarea = document.createElement('textarea');
                    textarea.innerHTML = exampleText;
                    const decodedText = textarea.value;
                    insertExample(decodedText);
                }
            }
        });

        // Cerrar modal de información
        const featureInfoClose = document.getElementById('feature-info-close');
        const featureInfoModal = document.getElementById('feature-info-modal');
        featureInfoClose?.addEventListener('click', () => {
            featureInfoModal?.classList.remove('open');
        });
        
        // Cerrar modal al hacer clic fuera
        featureInfoModal?.addEventListener('click', (e) => {
            if (e.target === featureInfoModal) {
                featureInfoModal.classList.remove('open');
            }
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

