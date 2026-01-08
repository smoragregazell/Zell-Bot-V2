# Comparación: `docs_tool.py` vs `search_tickets.py`

## 📊 Tabla Comparativa

| Aspecto | `search_tickets.py` | `docs_tool.py` |
|---------|---------------------|----------------|
| **Estrategias de búsqueda** | ✅ Keywords (SQL LIKE)<br>✅ Semántica (FAISS)<br>✅ Híbrida (keywords + semántica) | ❌ Solo Semántica (FAISS) |
| **Fuente de datos** | Base de datos SQL (API Zell) | Archivos FAISS indexados offline |
| **Índice FAISS** | ✅ Un índice global (`faiss_index_ip.bin`)<br>✅ Cargado en memoria al inicio | ❌ Múltiples índices por universo<br>✅ Cargado bajo demanda por universo |
| **Metadata** | Datos dinámicos desde API (Título, Descripción, Cliente) | Metadata estática desde JSONL (title, section, codigo, fecha_emision, etc.) |
| **Estructura** | Tickets = entidades únicas | Documentos = divididos en chunks |
| **Función de búsqueda** | `search_tickets_by_keywords()`<br>`search_tickets_semantic()`<br>`search_tickets_hybrid()` | `search_docs()` (solo semántica) |
| **Función de obtención** | No necesita (API trae todo) | `get_doc_context()` (obtiene texto completo de chunks) |
| **Universe** | ❌ No usa universos | ✅ Usa universos (`docs_org`, `docs_iso`, etc.) |
| **Expansión de contexto** | ❌ No aplica | ✅ Sí (chunks adyacentes en `get_doc_context`) |

## 🔍 Detalles Técnicos

### `search_tickets.py`
- **3 funciones principales:**
  1. `search_tickets_by_keywords()` → SQL LIKE queries
  2. `search_tickets_semantic()` → FAISS search (1 índice global)
  3. `search_tickets_hybrid()` → Combina ambas

- **Ventajas:**
  - ✅ Búsqueda por keywords (útil para nombres exactos)
  - ✅ Búsqueda híbrida (mejor recall)
  - ✅ Datos siempre actualizados (API en tiempo real)
  - ✅ 1 solo índice en memoria (más rápido)

- **Desventajas:**
  - ⚠️ Depende de API externa (más lento)
  - ⚠️ No puede buscar por universos/conjuntos

### `docs_tool.py`
- **2 funciones principales:**
  1. `search_docs()` → FAISS search por universo
  2. `get_doc_context()` → Obtiene texto completo + chunks adyacentes

- **Ventajas:**
  - ✅ Búsqueda por universos (organización flexible)
  - ✅ Indexación offline (más rápido)
  - ✅ Expansión de contexto (chunks adyacentes)
  - ✅ Metadata rica (código, fecha, revisión, etc.)

- **Desventajas:**
  - ⚠️ Solo búsqueda semántica (no keywords)
  - ⚠️ Carga índices bajo demanda (primera búsqueda más lenta)
  - ⚠️ Datos estáticos (requiere re-indexación)

## 🎯 Cuándo Usar Cada Uno

### Usa `search_tickets.py` cuando:
- Buscas tickets específicos por número o palabras clave
- Necesitas datos actualizados en tiempo real
- Quieres combinar keywords + semántica

### Usa `docs_tool.py` cuando:
- Buscas en documentos (ISO, políticas, minutas)
- Necesitas contexto expandido (chunks adyacentes)
- Trabajas con múltiples universos de documentos

## 🔗 Integración en V2

Ambos se usan en `tool_search_knowledge()`:

```python
# tickets
if scope in ("tickets", "all"):
    if policy == "hybrid":
        hybrid_results = search_tickets_hybrid(...)
    elif policy == "keyword":
        keyword_results = search_tickets_by_keywords(...)
    elif policy == "semantic":
        semantic_results = search_tickets_semantic(...)

# docs
if scope in ("docs", "all"):
    doc_res = search_docs(query=query, universe=universe, top_k=top_k)
```

Y en `tool_get_item()`:

```python
# tickets
if item_type == "ticket":
    ticket_data = get_ticket_data(item_id, conversation_id)

# docs
if item_type == "doc":
    result = get_doc_context(universe=universe, chunk_ids=[item_id], max_chunks=6)
```

