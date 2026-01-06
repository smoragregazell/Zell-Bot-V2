# Checklist: Antes de Procesar 350 Documentos

## ✅ Verificaciones Críticas (OBLIGATORIAS)

### 1. API Key de OpenAI
- [x] **VERIFICADO**: API Key configurada y funcionando
- **Variable de entorno**: `OPENAI_API_KEY_Semantic` o `OPENAI_API_KEY_SEMANTIC`
- **Costo**: $0.0001 por 1,000 tokens (~$0.77 MXN para 350 docs)

### 2. Directorio de Entrada
- [x] **VERIFICADO**: Directorio `knowledgebase/meetings_weekly` existe
- [ ] **ACCIÓN**: Asegurar que los 350 documentos .docx estén en este directorio
- **Formato esperado**: Minutas semanales en formato .docx

### 3. Permisos de Escritura
- [x] **VERIFICADO**: Permisos de escritura en `Data/`
- El sistema necesita escribir:
  - `docs_meetings_weekly_file_cache.json` (cache de archivos)
  - `docs_meetings_weekly_emb_cache.jsonl` (cache de embeddings)
  - `docs_meetings_weekly.index` (índice FAISS)
  - `docs_meetings_weekly_meta.jsonl` (metadatos)

---

## ⚠️ Verificaciones Importantes (RECOMENDADAS)

### 4. Cache de Archivos
- [ ] **ESTADO ACTUAL**: No existe `docs_meetings_weekly_file_cache.json`
- **IMPORTANTE**: Este cache evita reprocesar archivos ya indexados
- **Acción**: Se creará automáticamente al procesar, pero:
  - Si ya procesaste algunos documentos antes, el cache debería existir
  - Si no existe, TODOS los archivos se procesarán (aunque tengan embeddings en cache)

### 5. Cache de Embeddings
- [x] **VERIFICADO**: Existe y contiene 32 embeddings
- **Tamaño actual**: ~1.05 MB
- **Funcionamiento**: 
  - Si un chunk con el mismo texto ya fue procesado, NO se vuelve a llamar a la API
  - Ahorra costos significativamente

### 6. Índice FAISS Existente
- [x] **VERIFICADO**: Existe `docs_meetings_weekly.index`
- **Estado actual**: 6 chunks indexados (1 documento)
- **Comportamiento**: 
  - Si existe, los nuevos chunks se AGREGARÁN al índice existente
  - No se perderán los datos ya indexados

---

## 🔍 Verificaciones Adicionales

### 7. Espacio en Disco
- **Estimación para 350 documentos**:
  - Cache de embeddings: ~70-140 MB (1-2 MB por 1000 chunks)
  - Índice FAISS: ~14 MB (0.04 MB por 1000 chunks)
  - Metadatos JSONL: ~5-10 MB
  - **Total estimado**: ~100-150 MB
- [ ] Verificar que hay al menos 500 MB libres (margen de seguridad)

### 8. Estado de los Archivos .docx
- [ ] Verificar que los 350 archivos:
  - No estén corruptos
  - Tengan el formato correcto (minutas semanales)
  - Tengan nombres únicos (evitar duplicados)

### 9. Procesamiento en Lotes (OPCIONAL pero RECOMENDADO)
- **Ventaja**: Permite monitorear el progreso y detectar errores temprano
- **Comando sugerido**:
  ```bash
  # Procesar 50 documentos a la vez
  python -m Tools.docs_indexer \
    --universe meetings_weekly \
    --input_dir knowledgebase/meetings_weekly \
    --out_dir Data \
    --max_files 50
  ```

---

## 🚨 Puntos Críticos del Sistema de Cache

### Cache de Archivos (file_cache)
**¿Qué hace?**
- Rastrea qué archivos ya fueron procesados usando SHA256
- Si un archivo no cambió, se OMITE completamente del procesamiento

**Estado actual:**
- ❌ **NO EXISTE** `docs_meetings_weekly_file_cache.json` (primera vez)
- Se creará automáticamente al procesar

**Escenario Confirmado:**
- ✅ **Los documentos viejos NO se modificarán**
- ✅ **Solo se añadirán documentos de nuevas semanas**
- ✅ **Perfecto para el sistema de cache incremental**

**Impacto:**
- **Primera ejecución**: Procesa todos los documentos y crea el cache
- **Ejecuciones futuras**: Solo procesa documentos nuevos (nuevas semanas)
- **Documentos viejos**: Se omiten completamente (no se leen, no se procesan)
- **Ahorro**: Máximo eficiencia y mínimo costo en ejecuciones futuras

### Cache de Embeddings (emb_cache)
**¿Qué hace?**
- Guarda los embeddings ya generados por chunk_id + fingerprint del texto
- Si el mismo texto aparece en otro documento, reutiliza el embedding

**Estado actual:**
- ✅ **EXISTE** y tiene 32 embeddings guardados
- Esto ahorrará costos significativamente

**Impacto:**
- Si procesas 350 documentos similares, muchos chunks tendrán texto similar
- Los embeddings se reutilizarán, ahorrando llamadas a la API

---

## 📋 Comando para Procesar

### Procesamiento Completo (350 documentos)
```bash
python -m Tools.docs_indexer \
  --universe meetings_weekly \
  --input_dir knowledgebase/meetings_weekly \
  --out_dir Data
```

### Procesamiento en Lotes (recomendado)
```bash
# Lote 1: primeros 50
python -m Tools.docs_indexer \
  --universe meetings_weekly \
  --input_dir knowledgebase/meetings_weekly \
  --out_dir Data \
  --max_files 50

# Lote 2: siguientes 50 (el sistema omitirá los ya procesados)
# ... y así sucesivamente
```

---

## ✅ Checklist Final

Antes de ejecutar el procesamiento, asegúrate de:

- [x] API Key configurada y funcionando
- [ ] Los 350 documentos .docx están en `knowledgebase/meetings_weekly`
- [ ] Hay suficiente espacio en disco (~500 MB mínimo)
- [ ] Los archivos no están corruptos
- [ ] Has ejecutado `python verificar_cache_antes_procesar.py` y todo está OK
- [x] **Confirmado**: Los documentos viejos NO se modificarán, solo se añadirán nuevos
- [ ] Entiendes que:
  - El cache de archivos se creará automáticamente en la primera ejecución
  - **Documentos viejos**: Se omitirán completamente en ejecuciones futuras
  - **Documentos nuevos**: Solo se procesarán las nuevas semanas que añadas
  - Los embeddings se cachean y reutilizan
  - El costo total será ~$0.77 MXN para 350 documentos (solo primera vez)
  - **Ejecuciones futuras**: Casi $0 (solo procesa documentos nuevos)

## 🔍 Verificar Estado Actual

**Ejecuta antes de procesar:**
```bash
python verificar_documentos_procesados.py
```

Este script te mostrará:
- Cuántos documentos ya están procesados (se omitirán)
- Cuántos documentos son nuevos (se procesarán)
- Costo estimado solo para los documentos nuevos

---

## 🔄 Después del Procesamiento

1. **Verificar resultados**:
   ```bash
   python verificar_cache_antes_procesar.py
   ```

2. **Revisar estadísticas**:
   - Chunks totales en `docs_meetings_weekly_meta.jsonl`
   - Tamaño del cache de embeddings
   - Tamaño del índice FAISS

3. **Probar búsqueda**:
   - Verificar que los documentos nuevos aparezcan en búsquedas semánticas

---

## 💡 Tips Finales

1. **Primera ejecución**: Puede tardar varias horas para 350 documentos
   - Cada documento: ~1-2 segundos de procesamiento
   - 350 documentos: ~6-12 minutos (sin contar llamadas API)
   - Con API calls: ~10-20 minutos total

2. **Si se interrumpe**: El sistema es incremental
   - Los archivos ya procesados se guardan en el cache
   - Puedes reanudar sin problemas

3. **Monitoreo**: Revisa la salida del comando
   - Verás cuántos archivos se procesaron
   - Cuántos se omitieron (ya procesados)
   - Cuántos chunks se generaron

