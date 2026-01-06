# Sistema de Caché para Indexación de Documentos

## Descripción

El sistema de indexación ahora incluye un **caché de archivos procesados** que evita re-indexar documentos que ya fueron procesados y no han cambiado. Esto acelera significativamente el proceso cuando agregas nuevos documentos.

## Cómo Funciona

1. **Caché de Archivos**: Se guarda un registro de cada archivo procesado con su SHA256 hash
2. **Detección de Cambios**: Al indexar, se compara el SHA256 actual con el guardado
3. **Actualización Incremental**: Solo se procesan archivos nuevos o modificados
4. **Índice FAISS Incremental**: Los nuevos vectores se agregan al índice existente sin rehacer todo

## Archivos de Caché

- **Caché de archivos**: `Data/docs_{universe}_file_cache.json`
  - Guarda qué archivos ya fueron procesados
  - Formato: `{"ruta_relativa": {"sha256": "...", "processed_at": "..."}}`

- **Caché de embeddings**: `Data/docs_{universe}_emb_cache.jsonl`
  - Guarda embeddings ya calculados por chunk
  - Evita re-embeddear chunks de texto idénticos

## Uso

### Indexar por primera vez

```bash
python -m Tools.docs_indexer \
  --universe policies_iso \
  --input_dir knowledgebase/iso
```

### Agregar nuevos documentos

Simplemente ejecuta el mismo comando. El sistema automáticamente:
- Detectará qué archivos son nuevos o modificados
- Solo procesará esos archivos
- Agregará los nuevos chunks al índice existente

```bash
python -m Tools.docs_indexer \
  --universe policies_iso \
  --input_dir knowledgebase/iso
```

### Forzar re-indexación completa

Si necesitas forzar la re-indexación de todos los archivos (por ejemplo, si cambiaste el tamaño de chunks), elimina el caché:

```bash
# Eliminar caché de archivos
rm Data/docs_policies_iso_file_cache.json

# O eliminar todo (índice + cachés)
rm Data/docs_policies_iso.*
```

## Ejemplo de Salida

Cuando ejecutas el indexador, verás información sobre qué archivos se procesaron:

```json
{
  "ok": true,
  "universe": "policies_iso",
  "files": 15,
  "files_processed": 3,
  "files_skipped": 12,
  "chunks_new": 45,
  "chunks_total": 234,
  "incremental_update": true
}
```

- `files`: Total de archivos encontrados
- `files_processed`: Archivos nuevos/modificados procesados
- `files_skipped`: Archivos ya procesados (saltados)
- `chunks_new`: Nuevos chunks agregados
- `chunks_total`: Total de chunks en el índice
- `incremental_update`: `true` si se actualizó un índice existente

## Notas Importantes

1. **SHA256 por Contenido**: El caché usa SHA256 del contenido del archivo, no la fecha de modificación. Esto significa que si cambias el contenido, se detectará como modificado.

2. **Rutas Relativas**: El caché usa rutas relativas cuando es posible. Si mueves archivos, puede que necesites limpiar el caché.

3. **Índice FAISS**: El índice FAISS se actualiza incrementalmente. Los vectores existentes se mantienen y se agregan los nuevos.

4. **Metadatos JSONL**: Los metadatos se agregan al final del archivo JSONL. El orden se mantiene (existentes primero, nuevos después).

## Troubleshooting

### "Todos los archivos ya están procesados"
- Esto es normal si no hay archivos nuevos o modificados
- El índice existente se mantiene intacto

### Archivos no se detectan como nuevos
- Verifica que el archivo realmente cambió (SHA256 diferente)
- Si mueves archivos, puede que necesites limpiar el caché

### Índice corrupto
- Elimina el índice y los cachés: `rm Data/docs_{universe}.*`
- Re-indexa desde cero

