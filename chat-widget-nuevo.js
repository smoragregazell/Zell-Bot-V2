// Chat Widget - Modern Design with Backend Communication
(function() {
    
    // Configura tu endpoint de Supabase (AJUSTA ESTOS VALORES)
      const SUPABASE_URL = 'https://lnelwrjmhggndokkjdes.supabase.co';
      const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxuZWx3cmptaGdnbmRva2tqZGVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkwODA2NTksImV4cCI6MjA2NDY1NjY1OX0.laY_1H7SeopDU-6fmTucO6ALZMyadYwP_S4EIQqkJ9E';
  
    // Capturamos el email expuesto por el host
      let conversationId = '';
      let interactionId = '';
  
      const userName = '<%=Session("vUserName")%>'
  
      const createChatWidget = (config = {}) => {
          const rootId = config.rootId || 'chat-widget';
          const root = document.createElement('div');
          root.id = rootId;
  
          // Popup Styles
          Object.assign(root.style, {
              position: 'fixed',
              bottom: config.position?.bottom || '20px',
              left: config.position?.left || '20px',
              width: config.width || '400px',
              height: config.height || '500px',
              background: '#f4f5f7',
              border: 'none',
              borderRadius: '15px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
              overflow: 'hidden',
              display: 'none'
          });
  
          // Toggle Button
          const toggleButton = document.createElement('button');
          toggleButton.textContent = 'IA';
  
          Object.assign(toggleButton.style, {
              position: 'fixed',
              bottom: '20px',
              left: '20px',
              width: '60px',
              height: '60px',
              background: '#e5a500',
              color: '#000',
              border: 'none',
              borderRadius: '50%',
              cursor: 'pointer',
              fontSize: '24px',
              boxShadow: '0 4px 10px rgba(0,0,0,0.2)',
              fontFamily: '"Arial", Arial, sans-serif',
              fontWeight: '900'
          });
  
          toggleButton.addEventListener('click', () => {
              root.style.display = root.style.display === 'none' ? 'block' : 'none';
          });
          document.body.appendChild(toggleButton);
  
          // Widget HTML
          // … dentro de createChatWidget, en lugar del root.innerHTML anterior:
  root.innerHTML = `
    <div id="chat-header" style="
        background: linear-gradient(135deg, #e5a500, #ffcd3c);
        color: #000; padding: 15px;
        text-align: center; font-weight: bold;
        font-size: 18px; position: relative;
    ">
        Agente IA de Zell
        <!-- Botón de ayuda -->
        <button id="help-widget" style="
            position: absolute; left: 15px; top: 10px;
            background: transparent; border: none;
            font-size: 18px; font-weight: bold; cursor: pointer;
        ">?</button>
        <!-- Botón de cerrar -->
        <button id="close-widget" style="
            position: absolute; right: 15px; top: 10px;
            background: transparent; border: none;
            font-size: 18px; font-weight: bold; cursor: pointer;
        ">X</button>
    </div>
    <!-- Contenedor oculto para la ayuda -->
    <div id="help-popup" style="
        display: none;
        position: absolute;
        top: 60px; left: 2px;
        width: calc(100% - 30px);
        max-height: 300px;
        overflow-y: auto;
        padding: 12px;
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        font-size: 13px;
        color: black;
        line-height: 1.4;
        text-align: left;
        z-index: 10;
    ">
        <strong>¡Soy más eficiente cuando las preguntas están estructuradas así!</strong><br><br>
        <u>Consultar info completa de UN ticket:</u><br>
        &nbsp;&nbsp;Tráeme el ticket 12345.<br><br>
  
        <u>Consultar info específica de UN ticket:</u><br>
        &nbsp;&nbsp;Tráeme el id, descripción, resumen y último comentario del ticket 12345.<br><br>
  
        <u>Conteos o búsquedas de múltiples tickets:</u><br>
        &nbsp;&nbsp;Dame los tickets activos que ha registrado Juan en mayo.<br><br>
  
        <u>Buscar palabras clave en campos específicos de tickets:</u><br>
        &nbsp;&nbsp;*Se puede en título, descripción, último comentario y resumen.<br>
        &nbsp;&nbsp;¿Cuáles tickets que hayan sido registrados el mes de mayo del 2025 tienen error en su título o descripción?<br><br>
  
        <u>Para buscar tickets con solamente un concepto,error,palabra,frase,característica,etc.</u><br>
        &nbsp;&nbsp;¿Cuáles tickets hablan de listas negras?<br>
        &nbsp;&nbsp;Usar comillas -> “error base de datos”<br><br>
      
        <u>Búsqueda general pero filtrando por fecha, cliente, o alguna otra característica:</u><br>
        &nbsp;&nbsp;¿Cuáles tickets de CRQ registrados en el 2025 hacen referencia al reporte general IMSS?<br><br>
  
        <u>Si quieres saber cuales tickets se parecen a uno específico:</u><br>
        &nbsp;&nbsp;¿Cuáles tickets se parecen al 12345?<br><br>
  
        <u>Documentación interna e ISO:</u><br>
        &nbsp;&nbsp;¿Cuál es la política de calidad?<br>
        &nbsp;&nbsp;¿Qué dice ISO sobre la gestión de activos y seguridad de la información?<br><br>
    </div>
    <div id='chat-content' style='padding: 15px; overflow-y: auto; height: 70%; background: #ffffff; color: #000; font-family: "Inter", sans-serif; font-size: 14px;'></div>
              <div style='display: flex; padding: 10px; background: #f4f5f7;'>
                  <input id='chat-input' style='flex: 1; padding: 12px; font-size: 14px; background: #ffffff; color: #000; border: 1px solid #ddd; border-radius: 10px; outline: none; margin-right: 8px;' placeholder='Escribe tu mensaje...'>
                  <button id='chat-send' style='background-color: #e5a500; color: #fff; border: none; padding: 12px; cursor: pointer; border-radius: 10px;'>
                      <img src='https://cdn-icons-png.flaticon.com/512/254/254434.png' alt='Enviar' style='width: 24px; height: 24px;'>
                  </button>
              </div>`;
  
          document.body.appendChild(root);
          // Después de añadir `root` al body:
  const helpBtn = root.querySelector('#help-widget');
  const helpPopup = root.querySelector('#help-popup');
  helpBtn.addEventListener('click', () => {
    // Oculta/ muestra el pop-up
    helpPopup.style.display = helpPopup.style.display === 'none' ? 'block' : 'none';
  });
  // Si cierras el widget, también ocultamos el pop-up
  root.querySelector('#close-widget').addEventListener('click', () => {
    helpPopup.style.display = 'none';
  });
  
          // ** saludo inicial antes del primer mensaje del usuario **
          const chatContent = root.querySelector('#chat-content');
          appendBotMessage(
              chatContent,
              `¡Hola ${userName}! ¿En qué puedo ayudarte?`
          );
  
          setTimeout(() => initializeChat(rootId), 100);
      };
  
      const initializeChat = (rootId) => {
          const root = document.getElementById(rootId);
          const chatContent = root.querySelector('#chat-content');
          const chatInput = root.querySelector('#chat-input');
          const chatSend = root.querySelector('#chat-send');
          const closeWidget = root.querySelector('#close-widget');
  
          closeWidget.onclick = () => { root.style.display = 'none'; };
          chatSend.onclick = () => sendMessage(chatInput, chatContent);
          chatInput.onkeydown = (e) => { if (e.key === 'Enter') sendMessage(chatInput, chatContent); };
      };
  
      const sendMessage = (input, content) => {
          const message = input.value.trim();
          if (!message) return;
  
          appendUserMessage(content, message);
          input.value = '';
  
          // 1) Insertar la burbuja de "pensando"
          const thinkingBubble = appendThinkingBubble(content);
  
  
          sendToBackend(message, content, thinkingBubble);
      };
  
      const sendToBackend = async (message, content, thinkingBubble) => {
          // Enviamos conversationId ('' la primera vez)
          const payload = {
              conversation_id: conversationId,
              user_message: message,
              zToken: 'YOUR_ZTOKEN_HERE',
              userName
          };
          try {
              const resp = await fetch('https://iaticketsv4.replit.app/classify', 
                  {
                  method: 'POST',
                  headers: {
                      'Authorization': 'Bearer ' + payload.zToken,
                      'Content-Type': 'application/json'
                  },
                  body: JSON.stringify(payload)
              });
              const data = await resp.json();
              console.log(data);
              // Guardar conversationId tras primera respuesta
              if (data.conversation_id) conversationId = data.conversation_id;
              if (data.interaction_id) interactionId = data.interaction_id;
              thinkingBubble.remove();
              appendBotMessage(content, data.response || 'Error de comunicación', interactionId);
          } catch (err) {
              console.error("🔥 Error al comunicar con backend:", err);
              thinkingBubble.remove();
              appendBotMessage(content, 'Error de comunicación');
          }
      };
  
      // Función de feedback
      const sendFeedback = async (conversation_id, interaction_id, rating) => {
          try {
              await fetch(`${SUPABASE_URL}/rest/v1/rpc/grade_response`, {
                  method: 'POST',
                  headers: {
                      'apikey': SUPABASE_KEY,
                      'Content-Type': 'application/json'
                  },
                  body: JSON.stringify({
                      p_conversation_id: conversation_id,
                      p_interaction_id: interaction_id,
                      p_grade: rating
                  })
              });
          } catch (e) {
              console.error('Error enviando feedback:', e);
          }
      };
  
      // función para crear la burbuja de “Pensando…”
  function appendThinkingBubble(content) {
    const wrapper = document.createElement('div');
    Object.assign(wrapper.style, { textAlign: 'left', margin: '12px 0', opacity: '0.6' });
  
    const bubble = document.createElement('div');
    Object.assign(bubble.style, {
      display: 'inline-block',
      background: '#e0e0e0',
      padding: '10px 14px',
      borderRadius: '12px',
      fontStyle: 'italic',
      position: 'relative'
    });
  
    bubble.textContent = '…';
  
    wrapper.appendChild(bubble);
    content.appendChild(wrapper);
    content.scrollTop = content.scrollHeight;
    return wrapper;
  }
  
  // Expose init
  window.initChatWidget = createChatWidget;
  
      // User bubble with bottom-tail
    const appendUserMessage = (content, message) => {
      const wrapper = document.createElement('div');
      Object.assign(wrapper.style, {
        textAlign: 'right',
        margin: '12px 0'
      });
  
      const bubble = document.createElement('div');
      bubble.innerHTML = message.replace(/\n/g, '<br>');
      Object.assign(bubble.style, {
        display: 'inline-block',
        background: '#ffeb8a',
        padding: '10px 14px',
        borderRadius: '12px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.15)',
        border: '1px solid rgba(0,0,0,0.1)',
        position: 'relative',
        whiteSpace: 'pre-line'
      });
      bubble.textContent = message.replace(/\n/g, "<br>");
  
      // Tail pointing down
      const tail = document.createElement('div');
      Object.assign(tail.style, {
        width: '0',
        height: '0',
        borderLeft: '8px solid transparent',
        borderRight: '8px solid transparent',
        borderTop: '8px solid #ffeb8a',
        position: 'absolute',
        bottom: '-8px',
        right: '12px'
      });
  
      bubble.appendChild(tail);
      wrapper.appendChild(bubble);
      content.appendChild(wrapper);
      content.scrollTop = content.scrollHeight;
    };
  
    // Bot bubble with bottom-tail
    const appendBotMessage = (content, message, interaction_id) => {
      const wrapper = document.createElement('div');
      Object.assign(wrapper.style, {
        textAlign: 'left',
        margin: '12px 0'
      });
  
      const bubble = document.createElement('div');
      Object.assign(bubble.style, {
        display: 'inline-block',
        background: '#e0e0e0',
        padding: '10px 14px',
        borderRadius: '12px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.15)',
        border: '1px solid rgba(0,0,0,0.1)',
        position: 'relative',
        whiteSpace: 'pre-line', // Mantener saltos de línea
        maxWidth: '360px',      // Limitar ancho para mejor lectura
        lineHeight: '1.4',
        fontFamily: 'Inter, sans-serif',
        fontSize: '14px'
      });
  
      // Convertir saltos de línea \n en etiquetas <br>
      const formattedMessage = message
          .replace(/\n/g, '<br>')    // Convertir saltos de línea a <br>
          .replace(/TICKET A COMPARAR:/g, "<strong>TICKET A COMPARAR:</strong>")
          .replace(/TICKETS SIMILARES:/g, "<strong>TICKETS SIMILARES:</strong>")
          .replace(/ANÁLISIS:/g, "<br><strong>ANÁLISIS:</strong>")
          .replace(/RECOMENDACIÓN:/g, "<br><strong>RECOMENDACIÓN:</strong>")
          .replace(/\* ?IdTicket:/g, "<strong>* IdTicket:</strong>")
          .replace(/\| Cliente:/g, "<strong> | Cliente:</strong>")
          .replace(/\| Titulo:/g, "<strong> | Título:</strong>")
          .replace(/\| Descripcion:/g, "<strong> | Descripción:</strong>")
          .replace(/\| FechaCreado:/g, "<strong> | FechaCreado:</strong>")
          .replace(/\| HoraCreado:/g, "<strong> | HoraCreado:</strong>")
          .replace(/\| DetectadoPor:/g, "<strong> | DetectadoPor:</strong>")
          .replace(/\| AsignadoA:/g, "<strong> | AsignadoA:</strong>")
          .replace(/\| Contacto:/g, "<strong> | Contacto:</strong>")
          .replace(/\| Categoria:/g, "<strong> | Categoría:</strong>")
          .replace(/\| Prioridad:/g, "<strong> | Prioridad:</strong>")
          .replace(/\| Modulo:/g, "<strong> | Módulo:</strong>")
          .replace(/\| Estatus:/g, "<strong> | Estatus:</strong>")
          .replace(/\| FechaEstatus:/g, "<strong> | FechaEstatus:</strong>")
          .replace(/\| HoraEstatus:/g, "<strong> | HoraEstatus:</strong>")
          .replace(/\| Unidades:/g, "<strong> | Unidades:</strong>")
          .replace(/\| Objetivo:/g, "<strong> | Objetivo:</strong>")
          .replace(/\| Costo:/g, "<strong> | Costo:</strong>")
          .replace(/\| Calificac[oó]n:/g, "<strong> | Calificación:</strong>") // cubre posibles typos
          .replace(/\| FechaEntrega:/g, "<strong> | FechaEntrega:</strong>")
          .replace(/\| Resumen:/g, "<strong> | Resumen:</strong>")
          .replace(/\| Etiquetas:/g, "<strong> | Etiquetas:</strong>")
          .replace(/\| UltimoComentario:/g, "<strong> | ÚltimoComentario:</strong>")
          .replace(/\| FechaUltimoComentario:/g, "<strong> | FechaUltimoComentario:</strong>")
          .replace(/\| HoraUltimoComentario:/g, "<strong> | HoraUltimoComentario:</strong>")
          .replace(/\| DiasDelTicket:/g, "<strong> | DíasDelTicket:</strong>")
          .replace(/\| DiasEnEstatus:/g, "<strong> | DíasEnEstatus:</strong>")
          .replace(/\| DiasParaCambiar:/g, "<strong> | DíasParaCambiar:</strong>")
          .replace(/\\n/g, '<br>'); // Asegura que cualquier otro \n se convierta también
  
  
      bubble.innerHTML = formattedMessage;
  
      // Tail pointing down
      const tail = document.createElement('div');
      Object.assign(tail.style, {  
        width: '0',
        height: '0',
        borderLeft: '8px solid transparent',
        borderRight: '8px solid transparent',
        borderTop: '8px solid #e0e0e0',
        position: 'absolute',
        bottom: '-8px',
        left: '12px'
      });
  
  
      const fbContainer = document.createElement('div');
          Object.assign(fbContainer.style, { marginTop: '6px', fontSize: '16px' });
  
      const upBtn = document.createElement('button');
      upBtn.textContent = '👍';
      Object.assign(upBtn.style, { background: 'transparent', border: 'none', cursor: 'pointer', marginRight: '8px' });
      upBtn.onclick = () => {
          sendFeedback(conversationId, interaction_id, 'positive');
          upBtn.disabled = downBtn.disabled = true;
      };
  
      const downBtn = document.createElement('button');
      downBtn.textContent = '👎';
      Object.assign(downBtn.style, { background: 'transparent', border: 'none', cursor: 'pointer' });
      downBtn.onclick = () => {
          sendFeedback(conversationId, interaction_id, 'negative');
          upBtn.disabled = downBtn.disabled = true;
      };
  
      fbContainer.appendChild(upBtn);
      fbContainer.appendChild(downBtn);
  
      
  
      bubble.appendChild(tail);
      wrapper.appendChild(bubble);
      wrapper.appendChild(fbContainer);
  
      content.appendChild(wrapper);
      content.scrollTop = content.scrollHeight;
    };
  
    // Expose init
    window.initChatWidget = createChatWidget;
  
    // Auto‐start on load
    if (document.readyState === 'complete') {
      createChatWidget();
    } else {
      window.addEventListener('load', () => createChatWidget());
    }
  })();