# Análisis: Renombrar folder vs Mover archivos

## Situación Actual

El cache de archivos (`docs_org_file_cache.json`) usa **rutas relativas** como clave:
```json
{
  "knowledgebase\\iso\\archivo.txt": {
    "sha256": "...",
    "path": "knowledgebase\\iso\\archivo.txt"
  }
}
```

## Opción 1: Renombrar folder (iso → docs_org)

### ✅ Ventajas:
- Más rápido (solo renombrar 1 folder)
- Los archivos no se modifican (SHA256 igual)
- Cache de embeddings seguirá funcionando (usa chunk_id + texto, no ruta)

### ❌ Desventajas:
- El cache de archivos NO reconocerá los archivos (rutas diferentes)
- Se volverán a leer y procesar todos los archivos
- Se actualizarán las rutas en metadatos
- **PERO**: No se regenerarán embeddings (cache de embeddings funciona)

### Impacto:
- **Costo**: Casi $0 (embeddings vienen del cache)
- **Tiempo**: ~1-2 minutos para leer y procesar archivos
- **Resultado**: Archivos reprocesados con nuevas rutas

## Opción 2: Mover archivos (mismo efecto que renombrar)

### ✅ Ventajas:
- Mismo resultado que renombrar
- Más control sobre el proceso

### ❌ Desventajas:
- Mismo problema con cache de archivos
- Más pasos

## Opción 3: Limpiar cache de archivos + Renombrar

### ✅ Ventajas:
- Cache limpio desde el inicio
- Rutas consistentes desde el principio
- No hay confusión con rutas antiguas

### Pasos:
1. Renombrar folder: `iso` → `docs_org`
2. Eliminar `docs_org_file_cache.json`
3. Procesar normalmente

### Resultado:
- Archivos se procesarán como nuevos
- Pero embeddings vienen del cache (ahorro de costo)
- Rutas correctas desde el inicio

## Recomendación: Opción 3 (Renombrar + Limpiar cache)

**Razón**: Es la opción más limpia y evita problemas futuros con rutas inconsistentes.

### Comando:
```powershell
# 1. Renombrar folder
Rename-Item -Path "knowledgebase/iso" -NewName "docs_org"

# 2. Eliminar cache de archivos (opcional, pero recomendado)
Remove-Item "Data/docs_org_file_cache.json" -ErrorAction SilentlyContinue

# 3. Procesar
python -m Tools.docs_indexer --universe docs_org --input_dir knowledgebase/docs_org --out_dir Data
```

### Costo esperado:
- **Casi $0** porque:
  - Los embeddings están en cache (chunk_id + texto)
  - Solo se regenerarán si el texto cambió
  - Los archivos se leerán y procesarán, pero sin llamadas a API

