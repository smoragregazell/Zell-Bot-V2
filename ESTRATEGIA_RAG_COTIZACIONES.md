# Estrategia RAG para Cotizaciones

## Análisis del Sistema Actual (Tickets)

### Arquitectura RAG de Tickets

El sistema RAG para tickets funciona con los siguientes componentes:

1. **Indexación Offline:**
   - Índice FAISS: `Data/faiss_index_ip.bin` (IndexFlatIP - Inner Product con normalización L2)
   - IDs: `Data/faiss_ids.npy` (array numpy con IDs de tickets)
   - Cada vector corresponde a un ticket completo (embedding de contenido relevante)
   - Relación 1:1 entre índice FAISS y ID de ticket

2. **Búsqueda en Runtime:**
   - **Semántica (FAISS):** 
     - Genera embedding de la query con `text-embedding-ada-002`
     - Busca en el índice FAISS
     - Devuelve IDs de tickets y scores de similitud
   - **Keywords (SQL LIKE):**
     - Búsqueda directa en API de Zell usando SQL LIKE
     - Busca en campos Titulo y Descripcion
   - **Híbrida:** Combina ambos métodos

3. **Recuperación de Detalles:**
   - Usa `fetch_ticket_data(id)` para obtener datos completos del ticket
   - API: `https://tickets.zell.mx/apilink/info?source=1&sourceid={id}` (action 5001)
   - O alternativamente con SQL query (action 7777)

4. **Integración en chat_v2.py:**
   - `tool_search_knowledge`: Función que busca en múltiples fuentes (tickets, quotes, docs)
   - `tool_get_item`: Función que obtiene detalles de un item por ID

---

## Estrategia para Cotizaciones

### Objetivo

Crear un sistema RAG para cotizaciones que permita:
- Buscar cotizaciones por contenido semántico (ej: "existe alguna cotización para x cosa")
- Tener un universo de vectores con todos los IDs de cotizaciones y su contenido
- Responder preguntas sobre cotizaciones existentes

### Suposiciones Necesarias (a verificar)

1. **Fuente de datos:**
   - ¿Existe una tabla `Cotizaciones` en la base de datos?
   - ¿Hay un API endpoint para cotizaciones similar a tickets?
   - ¿Cuál es el ID único de una cotización? (ej: `IdCotizacion`, `CotizacionId`)
   - ¿Qué campos tiene una cotización? (probablemente: cliente, descripción, productos/servicios, monto, fecha, etc.)

2. **Estructura de datos:**
   - Se asume que cada cotización tiene:
     - ID único
     - Descripción/contenido que puede ser embebido
     - Metadatos (cliente, fecha, monto, etc.)

### Arquitectura Propuesta

#### 1. Indexación Offline (Similar a Tickets)

**Archivos a crear:**
```
Data/faiss_quotes_index_ip.bin  # Índice FAISS para cotizaciones
Data/faiss_quotes_ids.npy        # IDs de cotizaciones (array numpy)
```

**Proceso de indexación:**
1. Obtener todas las cotizaciones desde la API/BD
2. Para cada cotización:
   - Crear texto a embebir (descripción + título + productos/servicios)
   - Generar embedding con `text-embedding-ada-002`
   - Agregar vector al índice FAISS
   - Guardar ID en array paralelo
3. Guardar índice y IDs

**Script de indexación propuesto:**
- `Tools/quotes_indexer.py` (nuevo archivo)
- Similar a cómo se indexan tickets (necesitaríamos ver el script original, pero probablemente usa un proceso batch)

#### 2. Módulo de Búsqueda Semántica

**Archivo:** `Tools/quotes_semantic_tool.py` (nuevo)

**Funciones principales:**
```python
def load_quotes_faiss_data():
    """Carga el índice FAISS y los IDs de cotizaciones"""
    
def perform_quotes_faiss_search(vector, k=10):
    """Busca en el índice FAISS de cotizaciones"""
    
def search_quotes_by_keywords(keywords, max_results=10):
    """Búsqueda por keywords usando SQL LIKE (similar a tickets)"""
```

**Estructura similar a `semantic_tool.py` pero específico para cotizaciones**

#### 3. Funciones de Fetch

**Funciones a crear:**
```python
def fetch_quote_data(quote_id):
    """Obtiene datos completos de una cotización desde la API"""
    # Similar a fetch_ticket_data
    # API endpoint: ¿https://tickets.zell.mx/apilink/info?source=X&sourceid={id}?
    # O SQL query: SELECT * FROM Cotizaciones WHERE IdCotizacion = {id}
```

#### 4. Integración en chat_v2.py

**Modificaciones necesarias:**

1. **En `tool_search_knowledge`:**
   ```python
   # ---- QUOTES ----
   if scope in ("quotes", "all"):
       # Semantic search (quotes FAISS)
       if policy in ("semantic", "hybrid"):
           vec = generate_openai_embedding(query, conversation_id, interaction_id=None)
           if vec is not None:
               faiss_results, _ = perform_quotes_faiss_search(vec, k=top_k)
               for r in faiss_results or []:
                   qid = r.get("quote_id")
                   hits.append({
                       "type": "quote",
                       "id": str(qid),
                       "score": float(r.get("score", 0.0)),
                       "method": "semantic",
                       "snippet": "...",
                   })
       
       # Keyword search (SQL LIKE)
       if policy in ("keyword", "hybrid"):
           words = [w.strip() for w in query.split() if len(w) >= 4][:6]
           like_results = search_quotes_by_keywords(words, max_results=top_k)
           for r in like_results or []:
               hits.append({
                   "type": "quote",
                   "id": str(r.get("IdCotizacion")),
                   "score": 1.0,
                   "method": "keyword",
               })
   ```

2. **En `tool_get_item`:**
   ```python
   # ---- QUOTE ----
   if item_type == "quote":
       try:
           quote_data = fetch_quote_data(item_id)
           return {"quote_data": quote_data}
       except Exception as e:
           return {"error": f"fetch_quote_data falló: {e}"}
   ```

---

## Plan de Implementación

### Fase 1: Investigación y Preparación

1. **Verificar estructura de datos:**
   - Identificar tabla/API de cotizaciones
   - Obtener schema completo (campos disponibles)
   - Identificar ID único y campos clave para búsqueda
   - Verificar endpoints API disponibles

2. **Crear script de exploración:**
   - Script temporal para listar cotizaciones
   - Ver estructura real de datos
   - Identificar campos útiles para embeddings

### Fase 2: Indexación Offline

1. **Crear `Tools/quotes_indexer.py`:**
   - Función para obtener todas las cotizaciones
   - Función para crear texto embebible de cada cotización
   - Función para generar embeddings y construir índice FAISS
   - Guardar índice y IDs

2. **Ejecutar indexación inicial:**
   - Generar `Data/faiss_quotes_index_ip.bin`
   - Generar `Data/faiss_quotes_ids.npy`

### Fase 3: Herramientas de Búsqueda

1. **Crear `Tools/quotes_semantic_tool.py`:**
   - `load_quotes_faiss_data()`: Carga índice e IDs
   - `perform_quotes_faiss_search()`: Búsqueda semántica
   - `search_quotes_by_keywords()`: Búsqueda por keywords
   - `fetch_quote_data()`: Obtener datos completos

2. **Importar en `endpoints/chat_v2.py`**

### Fase 4: Integración

1. **Modificar `tool_search_knowledge`:**
   - Implementar búsqueda semántica para quotes
   - Implementar búsqueda por keywords para quotes
   - Integrar con política híbrida

2. **Modificar `tool_get_item`:**
   - Implementar recuperación de datos de cotización

### Fase 5: Testing

1. **Pruebas unitarias:**
   - Búsqueda semántica
   - Búsqueda por keywords
   - Fetch de datos

2. **Pruebas de integración:**
   - Flujo completo de búsqueda
   - Respuestas a preguntas tipo "existe alguna cotización para x"

---

## Consideraciones Técnicas

### Similitudes con Tickets

- Misma arquitectura: índice FAISS + IDs paralelos
- Mismo modelo de embedding: `text-embedding-ada-002`
- Mismo tipo de índice: `IndexFlatIP` con normalización L2
- Búsqueda híbrida: semántica + keywords

### Diferencias Potenciales

1. **Estructura de datos:**
   - Cotizaciones pueden tener estructura diferente (productos, líneas de detalle, etc.)
   - Puede requerir agregación de múltiples campos para el texto embebible

2. **Frecuencia de actualización:**
   - ¿Con qué frecuencia se agregan nuevas cotizaciones?
   - ¿Necesitamos re-indexación incremental o batch completo?

3. **Campos para búsqueda:**
   - Identificar qué campos son más relevantes para búsqueda
   - Posiblemente: Descripción, Productos/Servicios, Cliente, Observaciones

---

## Preguntas Pendientes

1. **¿Cuál es la estructura real de la tabla/API de cotizaciones?**
2. **¿Qué campos tiene una cotización?**
3. **¿Cuál es el ID único? (IdCotizacion, CotizacionId, etc.)**
4. **¿Existe endpoint API para cotizaciones? ¿Cuál es la estructura?**
5. **¿Las cotizaciones están relacionadas con tickets o son entidades independientes?**
6. **¿Qué campos deben incluirse en el texto embebible?**
7. **¿Necesitamos indexar todas las cotizaciones o solo las activas/recientes?**

---

## Archivos a Crear/Modificar

### Nuevos Archivos:
- `Tools/quotes_indexer.py` - Script de indexación offline
- `Tools/quotes_semantic_tool.py` - Herramientas de búsqueda semántica
- `Data/faiss_quotes_index_ip.bin` - Índice FAISS (generado)
- `Data/faiss_quotes_ids.npy` - IDs (generado)

### Archivos a Modificar:
- `endpoints/chat_v2.py` - Integrar búsqueda y get_item para quotes

---

## Ejemplo de Uso Esperado

**Usuario:** "¿Existe alguna cotización para implementación de módulo de inventarios?"

**Sistema:**
1. Genera embedding de la query
2. Busca en `faiss_quotes_index_ip.bin`
3. Obtiene IDs de cotizaciones similares con scores
4. Para los top K resultados:
   - Llama `fetch_quote_data(id)` para obtener detalles
   - Construye respuesta con información relevante
5. Responde: "Sí, encontré X cotizaciones relacionadas: [lista con IDs y resumen]"

---

## Próximos Pasos Inmediatos

1. **Investigar estructura de datos de cotizaciones**
2. **Crear script de exploración para entender datos reales**
3. **Definir campos clave para embeddings**
4. **Implementar indexador básico**
5. **Implementar herramientas de búsqueda**
6. **Integrar en chat_v2.py**

