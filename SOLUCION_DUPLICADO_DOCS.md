# Solución: Duplicado de prefijo "docs_" en nombres de archivos

## Problema detectado

Cuando se ejecutaba:
```powershell
python -m Tools.docs_indexer --universe docs_org --input_dir knowledgebase/docs_org --out_dir Data
```

Se generaban archivos con nombre duplicado:
- ❌ `docs_docs_org.index` (incorrecto)
- ❌ `docs_docs_org_meta.jsonl` (incorrecto)
- ❌ `docs_docs_org_file_cache.json` (incorrecto)
- ❌ `docs_docs_org_emb_cache.jsonl` (incorrecto)

## Solución implementada

Se agregó una función `_normalize_universe_name()` en:
1. `Tools/docs_indexer/indexer.py`
2. `Tools/docs_indexer/file_cache.py`
3. `Tools/docs_indexer/embeddings.py`

Esta función verifica si el universo ya empieza con `docs_` y evita duplicar el prefijo.

## Archivos corregidos

### Antes:
```python
idx_path = os.path.join(out_dir, f"docs_{universe}.index")
# Si universe = "docs_org" → "docs_docs_org.index" ❌
```

### Después:
```python
index_name = _normalize_universe_name(universe)
idx_path = os.path.join(out_dir, f"{index_name}.index")
# Si universe = "docs_org" → "docs_org.index" ✅
```

## Archivos generados correctamente

Ahora se generarán:
- ✅ `docs_org.index`
- ✅ `docs_org_meta.jsonl`
- ✅ `docs_org_file_cache.json`
- ✅ `docs_org_emb_cache.jsonl`

## Limpiar archivos duplicados

Si ya ejecutaste el comando y tienes archivos con `docs_docs_org`, puedes:

1. **Eliminar los archivos duplicados:**
```powershell
Remove-Item "Data/docs_docs_org.*" -Force
```

2. **Re-ejecutar el indexador:**
```powershell
python -m Tools.docs_indexer --universe docs_org --input_dir knowledgebase/docs_org --out_dir Data
```

## Nota importante

El campo `universe` en los metadatos JSONL seguirá usando el valor original (ej: `docs_org`) para mantener compatibilidad con las búsquedas. Solo los nombres de archivos usan el nombre normalizado.

