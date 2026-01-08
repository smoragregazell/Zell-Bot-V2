# Plan de Eliminación de V1

## Análisis del Sistema Actual

### V1 (Sistema Antiguo - Clasificador)
- **Arquitectura**: Clasificador → Tool Registry → Tool específica → Respuesta
- **Endpoint**: `/classify` (en `endpoints/classifier.py` - **NO EXISTE actualmente pero se referencia en main.py**)
- **Flujo**: 
  1. Usuario envía mensaje
  2. Clasificador decide qué tool usar
  3. Se ejecuta la tool registrada
  4. Se retorna respuesta

### V2 (Sistema Nuevo - Responses API)
- **Arquitectura**: Responses API → Tool-calling automático → Loop de tools → Respuesta final
- **Endpoint**: `/chat_v2` y `/chat_v2/stream`
- **Flujo**:
  1. Usuario envía mensaje
  2. Responses API decide qué tools llamar
  3. Loop de tool-calling hasta respuesta final
  4. Se retorna respuesta

---

## Componentes V1 a Eliminar

### 1. Endpoints V1 (NO EXISTEN pero se referencian)
- ❌ `endpoints/classifier.py` - **NO EXISTE** pero se importa en `main.py:13`
- ❌ `Tools/iso_tool.py` - **NO EXISTE** (mencionado en exports pero no existe)
- ❌ `Tools/continuation_tool.py` - **NO EXISTE** (mencionado en exports pero no existe)

### 2. Sistema de Tool Registry (PARCIALMENTE USADO)
- ⚠️ `utils/tool_registry.py` - **USADO por tools que también se usan en V2**
  - `@register_tool` decorator se usa en:
    - `Tools/ticket_tool.py` - `execute_ticket_query` (solo V1)
    - `Tools/query_tool.py` - `execute_query` (solo V1)
    - `Tools/semantic_tool.py` - `execute_semantic_search` (solo V1)
    - `Tools/compararticket_tool.py` - `comparar_ticket` (solo V1)
  - **NOTA**: Las funciones internas de estas tools (como `generate_sql_query`, `fetch_ticket_data`) se usan en V2

### 3. ToolResponse y Clasificaciones V1
- ⚠️ `utils/tool_response.py` - **USADO por tools V1**
  - Clasificaciones V1: "Consulta de Tickets", "Búsqueda de Query", "ISO", "Pregunta Continuada", "Búsqueda Semántica", "Comparar ticket", "No Relacionado", "Clasificación Incierta", "Error"
  - **NOTA**: V2 no usa ToolResponse, usa dicts simples

### 4. Prompts V1
- ❌ `Prompts/Clasificador/` - Prompts de clasificación (solo V1)
- ❌ `Prompts/ISO/` - Prompts ISO (solo V1, si existe)
- ❌ `Prompts/Continuada/` - Prompts de continuación (solo V1, si existe)
- ✅ `Prompts/V2/` - **MANTENER** (solo V2)
- ⚠️ `Prompts/Ticket/`, `Prompts/Query/`, `Prompts/Semantica/` - **MANTENER** (usados por V2 indirectamente)

### 5. Variables de Entorno V1
- ❌ `OPENAI_API_KEY_Clasificador` - Solo para clasificador V1
- ❌ `OPENAI_API_KEY_Continuada` - Solo para continuation tool V1
- ❌ `OPENAI_API_KEY_ISO` - Solo para ISO tool V1
- ✅ `OPENAI_API_KEY_Query` - **MANTENER** (usado por query_tool que V2 usa)
- ✅ `OPENAI_API_KEY_Semantic` - **MANTENER** (usado por semantic_tool que V2 usa)

### 6. Logging V1
- ⚠️ `utils/logs.py` - **USADO por tools que V2 también usa**
  - Funciones: `log_interaction`, `log_ai_call`, `log_ai_call_postgres`, `log_zell_api_call`
  - **NOTA**: V2 usa `utils/logs_v2.py` pero algunas tools internas usan `utils/logs.py`
  - **DECISIÓN**: Mantener `utils/logs.py` porque las tools lo necesitan, pero limpiar funciones no usadas

### 7. Funciones de Tools V1 (a eliminar de tools compartidas)
- ❌ `Tools/ticket_tool.py::execute_ticket_query()` - Solo V1 (registrada con `@register_tool`)
- ❌ `Tools/query_tool.py::execute_query()` - Solo V1 (registrada con `@register_tool`)
- ❌ `Tools/semantic_tool.py::execute_semantic_search()` - Solo V1 (registrada con `@register_tool`)
- ❌ `Tools/compararticket_tool.py::comparar_ticket()` - Solo V1 (registrada con `@register_tool`)
- ✅ **MANTENER**: Funciones internas que V2 usa:
  - `generate_sql_query()`, `fetch_query_results()` (de query_tool)
  - `fetch_ticket_data()`, `get_ticket_comments()` (de busquedacombinada_tool)
  - `generate_openai_embedding()`, `perform_faiss_search()` (de semantic_tool)

### 8. Routers V1
- ❌ `Tools/compararticket_tool.py::router` - Router `/comparar_ticket` (solo V1)
- ❌ `Tools/query_tool.py::router` - Router `/query_tool` (solo V1, pero funciones internas se usan)

### 9. Context Manager V1
- ⚠️ `utils/contextManager/short_term_memory.py` - **USADO solo por V1**
  - Funciones: `add_to_short_term_memory()`, `get_short_term_memory()`
  - **NOTA**: V2 no usa short_term_memory, usa Responses API para contexto

---

## Componentes Compartidos (Limpiar pero Mantener)

### Tools que tienen funciones V1 y V2
1. **`Tools/query_tool.py`**:
   - ❌ Eliminar: `execute_query()` (función V1 con `@register_tool`)
   - ❌ Eliminar: Router `/query_tool`
   - ✅ Mantener: `generate_sql_query()`, `fetch_query_results()`, `process_query_results()` (usadas por V2)

2. **`Tools/ticket_tool.py`**:
   - ❌ Eliminar: `execute_ticket_query()` (función V1 con `@register_tool`)
   - ✅ Mantener: Funciones internas si las usa V2

3. **`Tools/semantic_tool.py`**:
   - ❌ Eliminar: `execute_semantic_search()` (función V1 con `@register_tool`)
   - ✅ Mantener: `generate_openai_embedding()`, `perform_faiss_search()`, `init_semantic_tool()` (usadas por V2)

4. **`Tools/compararticket_tool.py`**:
   - ❌ Eliminar: Todo el archivo (solo V1)
   - ✅ Mantener: `ejecutar_busqueda_combinada()` si se usa en V2 (verificar)

---

## Plan de Eliminación Detallado

### Fase 1: Limpiar Referencias Rotas
1. ❌ Eliminar import de `classifier_router` en `main.py:13`
2. ❌ Eliminar `app.include_router(classifier_router)` en `main.py:72`
3. ❌ Eliminar variables de entorno V1 de `REQUIRED_KEYS` en `main.py`
4. ❌ Eliminar imports de tools V1 que no existen

### Fase 2: Eliminar Endpoints y Routers V1
1. ❌ Eliminar router de `Tools/compararticket_tool.py` de `main.py:77-78`
2. ❌ Eliminar router de `Tools/query_tool.py` (si existe endpoint directo)

### Fase 3: Limpiar Tools Compartidas
1. ❌ Eliminar funciones `@register_tool` de tools compartidas:
   - `Tools/ticket_tool.py::execute_ticket_query()`
   - `Tools/query_tool.py::execute_query()`
   - `Tools/semantic_tool.py::execute_semantic_search()`
2. ❌ Eliminar imports de `@register_tool` de estas tools
3. ❌ Eliminar routers de estas tools si existen

### Fase 4: Eliminar Archivos Completos V1
1. ❌ Eliminar `Tools/compararticket_tool.py` (solo V1)
2. ❌ Eliminar `utils/tool_registry.py` (solo V1)
3. ❌ Eliminar `utils/tool_response.py` (solo V1)
4. ❌ Eliminar `utils/contextManager/short_term_memory.py` (solo V1)

### Fase 5: Limpiar Prompts V1
1. ❌ Eliminar `Prompts/Clasificador/` (solo V1)
2. ❌ Verificar y eliminar `Prompts/ISO/` si existe
3. ❌ Verificar y eliminar `Prompts/Continuada/` si existe

### Fase 6: Limpiar Variables de Entorno
1. ❌ Eliminar de `env.example`: `OPENAI_API_KEY_Clasificador`, `OPENAI_API_KEY_Continuada`, `OPENAI_API_KEY_ISO`
2. ❌ Eliminar de `main.py` las referencias a estas keys

### Fase 7: Limpiar Logging V1 (si es posible)
1. ⚠️ Revisar si `utils/logs.py` se puede simplificar eliminando funciones no usadas
2. ⚠️ Verificar si todas las tools pueden migrar a `utils/logs_v2.py`

### Fase 8: Limpiar Imports y Dependencias
1. ❌ Eliminar imports de `tool_registry` en todos los archivos
2. ❌ Eliminar imports de `tool_response` en todos los archivos
3. ❌ Eliminar imports de `short_term_memory` en todos los archivos
4. ❌ Limpiar imports no usados en `main.py`

---

## Archivos a Eliminar Completamente

1. ❌ `Tools/compararticket_tool.py` (solo V1)
2. ❌ `utils/tool_registry.py` (solo V1)
3. ❌ `utils/tool_response.py` (solo V1)
4. ❌ `utils/contextManager/short_term_memory.py` (solo V1)
5. ❌ `Prompts/Clasificador/` (directorio completo)
6. ❌ `Prompts/ISO/` (si existe)
7. ❌ `Prompts/Continuada/` (si existe)

## Archivos a Modificar (Limpiar funciones V1)

1. ⚠️ `main.py` - Eliminar referencias a V1
2. ⚠️ `Tools/query_tool.py` - Eliminar `execute_query()` y router
3. ⚠️ `Tools/ticket_tool.py` - Eliminar `execute_ticket_query()`
4. ⚠️ `Tools/semantic_tool.py` - Eliminar `execute_semantic_search()`
5. ⚠️ `env.example` - Eliminar variables V1

---

## Verificaciones Necesarias

Antes de eliminar, verificar:
1. ✅ ¿V2 usa `ejecutar_busqueda_combinada()` de `busquedacombinada_tool.py`?
2. ✅ ¿Alguna tool V2 necesita `ToolResponse`?
3. ✅ ¿Alguna tool V2 necesita `short_term_memory`?
4. ✅ ¿Hay algún frontend/widget que use endpoints V1?

---

## Orden de Ejecución Recomendado

1. **Primero**: Eliminar referencias rotas en `main.py`
2. **Segundo**: Verificar que V2 funciona correctamente
3. **Tercero**: Eliminar funciones V1 de tools compartidas
4. **Cuarto**: Eliminar archivos completos V1
5. **Quinto**: Limpiar prompts y variables de entorno
6. **Sexto**: Verificar que todo funciona

---

## Notas Importantes

- ⚠️ **NO eliminar** funciones internas de tools que V2 usa (ej: `generate_sql_query`)
- ⚠️ **NO eliminar** `utils/logs.py` completamente (algunas tools lo necesitan)
- ⚠️ **NO eliminar** `utils/llm_provider.py` y `utils/llm_config.py` (usados por ambos)
- ⚠️ **NO eliminar** `utils/contextManager/context_handler.py` (usado por ambos)

