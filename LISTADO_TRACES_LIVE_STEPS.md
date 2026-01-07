# Listado de Traces que DEBEN Mostrarse en Live Steps

## Mensajes que EXISTEN en el código y DEBEN aparecer:

### ✅ 1. Búsqueda de Documentación
**Código:** `tr(f"Buscando en documentación interna Zell...")` (línea 489)
**Patrón actual:** `r"Buscando en documentación interna Zell"`
**Estado:** ✅ Debería funcionar

### ✅ 2. Explorando Scope y Estrategia
**Código:** `tr(f"Explorando scope={scope} ejecutando estrategia={policy}")` (línea 490)
**Patrón actual:** `r"Explorando scope=.+ ejecutando estrategia=.+"`
**Estado:** ✅ Debería funcionar

### ✅ 3. Obteniendo Top Resultados
**Código:** `tr(f"Obteniendo top {top_k} resultados para query: '{query[:120]}'")` (línea 491)
**Patrón actual:** `r"Obteniendo top \d+ resultados para query:"`
**Estado:** ✅ Debería funcionar

### ✅ 4. Búsqueda por Palabras Clave
**Código:** `tr(f"Buscando en tickets con palabras clave: {words}")` (línea 502)
**Patrón actual:** `r"Buscando en tickets con palabras clave:"`
**Estado:** ✅ Debería funcionar

### ✅ 5. Búsqueda Semántica
**Código:** `tr(f"Buscando en tickets con búsqueda semántica...")` (línea 531)
**Patrón actual:** `r"Buscando en tickets con búsqueda semántica"`
**Estado:** ✅ Debería funcionar

### ✅ 6. Búsqueda en Universe
**Código:** `tr(f"Buscando en: {universe}")` (línea 565)
**Patrón actual:** `r"Buscando en: .+"`
**Estado:** ✅ Debería funcionar

### ✅ 7. Obteniendo Item
**Código:** `tr(f"Obteniendo item {item_type} id={item_id}")` (línea 646)
**Patrón actual:** `r"Obteniendo item .+ id=.+"`
**Estado:** ✅ Debería funcionar

### ✅ 8. Info Clave del Documento
**Código:** `tr(f"Obteniendo info clave del documento")` (línea 651)
**Patrón actual:** `r"Obteniendo info clave del documento"`
**Estado:** ✅ Debería funcionar

### ✅ 9. Datos del Ticket
**Código:** `tr(f"Obteniendo datos del ticket #{item_id}")` (línea 670)
**Patrón actual:** `r"Obteniendo datos del ticket #\d+"`
**Estado:** ✅ Debería funcionar

### ✅ 10. Query SQL Generado
**Código:** `tr(f"Query SQL generado: {sql_query}")` (línea 732)
**Patrón actual:** `r"Query SQL generado:"`
**Estado:** ✅ Debería funcionar

### ✅ 11. Web Search
**Código:** `tr(f"Ejecutando web_search para: {web_query[:100]}")` (línea 985)
**Patrón actual:** `r"Ejecutando web_search para:"`
**Estado:** ✅ Debería funcionar

### ✅ 12. Generando Respuesta Final
**Código:** `tr(f"Generando respuesta final para el usuario...")` (líneas 883, 1207)
**Patrón actual:** `r"Generando respuesta final para el usuario"`
**Estado:** ✅ Debería funcionar

---

## Posibles Problemas Detectados:

1. **Patrón 1:** El mensaje tiene "..." al final pero el patrón no lo incluye
   - **Solución:** El patrón debería ser: `r"Buscando en documentación interna Zell\.\.\."` o mejor: `r"Buscando en documentación interna Zell"` (sin los puntos)

2. **Patrón 5:** Similar, tiene "..." al final
   - **Solución:** El patrón ya está bien (sin los puntos)

3. **Patrón 12:** Similar, tiene "..." al final
   - **Solución:** El patrón ya está bien (sin los puntos)

4. **Throttle:** Los mensajes pueden estar siendo filtrados por el throttle de 300ms
   - **Solución:** Reducir throttle o ajustar lógica

5. **ContextVar:** Puede que el emitter no esté activo cuando se llaman algunos tr()
   - **Solución:** Verificar que el endpoint /stream esté configurando el emitter correctamente

---

## Mensajes Adicionales que PODRÍAN ser útiles (pero no están en tu lista):

- `tr(f"Encontrados {count} tickets con búsqueda por palabras clave")` (línea 510)
- `tr(f"Encontrados {count} tickets con búsqueda semántica")` (línea 538)
- `tr(f"Encontrados {count} documentos en {universe}")` (línea 572)
- `tr(f"Obteniendo comentarios del ticket...")` (línea 682)

¿Quieres agregar alguno de estos también?

