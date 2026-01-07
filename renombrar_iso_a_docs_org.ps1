# Script para renombrar knowledgebase/iso a knowledgebase/docs_org
# Ejecuta: .\renombrar_iso_a_docs_org.ps1

Write-Host "Renombrando knowledgebase/iso a knowledgebase/docs_org..."

# Verificar que existe el directorio
if (-not (Test-Path "knowledgebase/iso")) {
    Write-Host "ERROR: El directorio knowledgebase/iso no existe"
    exit 1
}

# Renombrar el directorio
Rename-Item -Path "knowledgebase/iso" -NewName "docs_org"

Write-Host "✓ Directorio renombrado exitosamente"

# Opcional: Limpiar cache de archivos para empezar limpio
$cacheFile = "Data/docs_org_file_cache.json"
if (Test-Path $cacheFile) {
    Write-Host ""
    Write-Host "¿Deseas eliminar el cache de archivos para empezar limpio? (S/N)"
    $response = Read-Host
    if ($response -eq "S" -or $response -eq "s") {
        Remove-Item $cacheFile -Force
        Write-Host "✓ Cache de archivos eliminado"
    } else {
        Write-Host "⚠ Cache de archivos mantenido (los archivos se reprocesarán con nuevas rutas)"
    }
}

Write-Host ""
Write-Host "Ahora puedes ejecutar:"
Write-Host "python -m Tools.docs_indexer --universe docs_org --input_dir knowledgebase/docs_org --out_dir Data"

