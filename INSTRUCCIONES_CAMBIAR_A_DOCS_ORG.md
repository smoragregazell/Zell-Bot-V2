# Instrucciones: Cambiar de knowledgebase/iso a knowledgebase/docs_org

## ✅ RECOMENDACIÓN: Renombrar el folder (más simple y eficiente)

### Opción 1: Usar el script (RECOMENDADO)
```powershell
.\renombrar_iso_a_docs_org.ps1
```

Este script:
1. Renombra `knowledgebase/iso` → `knowledgebase/docs_org`
2. Te pregunta si quieres limpiar el cache de archivos (recomendado: SÍ)

### Opción 2: Manualmente
```powershell
# 1. Renombrar el folder
Rename-Item -Path "knowledgebase/iso" -NewName "docs_org"

# 2. (Opcional pero recomendado) Limpiar cache de archivos
Remove-Item "Data/docs_org_file_cache.json" -ErrorAction SilentlyContinue
```

## Paso 2: Procesar con el nuevo directorio

```powershell
python -m Tools.docs_indexer --universe docs_org --input_dir knowledgebase/docs_org --out_dir Data
```

## ⚠️ Notas importantes:

### Sobre el cache de archivos:
- El cache usa **rutas relativas** como clave
- Si renombras el folder, las rutas cambiarán
- **Recomendación**: Eliminar el cache para empezar limpio
- Los archivos se reprocesarán, PERO:
  - ✅ **Costo casi $0**: Los embeddings están en cache (usa chunk_id + texto)
  - ✅ Solo se leerán y procesarán archivos (sin llamadas a API)
  - ✅ Rutas correctas desde el inicio

### Sobre el cache de embeddings:
- ✅ **NO se afecta**: Usa chunk_id + fingerprint del texto
- ✅ Los embeddings existentes se reutilizarán
- ✅ Ahorro de costos garantizado

### Rutas en metadatos:
- Cambiarán de: `knowledgebase/iso\archivo.txt` 
- A: `knowledgebase/docs_org\archivo.txt`
- Las búsquedas funcionarán igual

## Verificar después de renombrar:

```powershell
# Verificar que el directorio existe con el nuevo nombre
Test-Path "knowledgebase/docs_org"

# Verificar que los archivos estén ahí
Get-ChildItem knowledgebase/docs_org

# Verificar que el directorio iso ya no existe
Test-Path "knowledgebase/iso"  # Debe retornar False
```

