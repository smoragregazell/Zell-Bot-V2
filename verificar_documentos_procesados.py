"""
Script para verificar que documentos de meetings_weekly ya estan procesados
y cuales faltan por procesar.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Set

def cargar_cache_archivos(universe: str, out_dir: str = "Data") -> Dict[str, Dict]:
    """Carga el cache de archivos procesados"""
    cache_path = os.path.join(out_dir, f"docs_{universe}_file_cache.json")
    if not os.path.exists(cache_path):
        return {}
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                # Compatibilidad con formato antiguo
                return {item["path"]: item for item in data if "path" in item}
    except Exception:
        return {}
    return {}

def obtener_archivos_docx(input_dir: str) -> List[str]:
    """Obtiene todos los archivos .docx del directorio"""
    docx_files = []
    for file_path in Path(input_dir).glob("*.docx"):
        docx_files.append(str(file_path))
    return sorted(docx_files)

def calcular_sha256(path: str) -> str:
    """Calcula SHA256 de un archivo"""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def normalizar_path(path: str) -> str:
    """Normaliza path para comparacion"""
    try:
        return os.path.relpath(path)
    except ValueError:
        return os.path.abspath(path)

def main():
    print("="*70)
    print("VERIFICACION: Documentos Procesados vs Pendientes")
    print("="*70)
    print()
    
    universe = "meetings_weekly"
    input_dir = "knowledgebase/meetings_weekly"
    out_dir = "Data"
    
    # Cargar cache de archivos
    cache = cargar_cache_archivos(universe, out_dir)
    print(f"Cache de archivos: {len(cache)} archivos registrados")
    print()
    
    # Obtener todos los archivos .docx
    archivos_docx = obtener_archivos_docx(input_dir)
    print(f"Archivos .docx encontrados: {len(archivos_docx)}")
    print()
    
    # Clasificar archivos
    procesados = []
    pendientes = []
    modificados = []  # Archivos que cambiaron (SHA256 diferente)
    
    for archivo in archivos_docx:
        path_normalizado = normalizar_path(archivo)
        nombre = os.path.basename(archivo)
        
        if path_normalizado in cache:
            # Verificar si el SHA256 coincide
            sha_cache = cache[path_normalizado].get("sha256", "")
            sha_actual = calcular_sha256(archivo)
            
            if sha_actual == sha_cache:
                procesados.append((archivo, nombre, sha_actual[:12]))
            else:
                modificados.append((archivo, nombre, sha_cache[:12], sha_actual[:12]))
        else:
            pendientes.append((archivo, nombre))
    
    # Mostrar resultados
    print("="*70)
    print("RESUMEN")
    print("="*70)
    print(f"  Procesados (no cambiaron): {len(procesados)}")
    print(f"  Pendientes (nuevos):       {len(pendientes)}")
    print(f"  Modificados (cambiaron):    {len(modificados)}")
    print(f"  TOTAL:                      {len(archivos_docx)}")
    print()
    
    # Detalles de procesados
    if procesados:
        print("="*70)
        print(f"ARCHIVOS YA PROCESADOS ({len(procesados)}) - Se OMITIRAN")
        print("="*70)
        for archivo, nombre, sha in procesados[:10]:
            print(f"  [OK] {nombre} (SHA: {sha}...)")
        if len(procesados) > 10:
            print(f"  ... y {len(procesados) - 10} mas")
        print()
    
    # Detalles de pendientes
    if pendientes:
        print("="*70)
        print(f"ARCHIVOS PENDIENTES ({len(pendientes)}) - Se PROCESARAN")
        print("="*70)
        for archivo, nombre in pendientes:
            size_kb = os.path.getsize(archivo) / 1024
            print(f"  [PENDIENTE] {nombre} ({size_kb:.1f} KB)")
        print()
    
    # Detalles de modificados
    if modificados:
        print("="*70)
        print(f"ARCHIVOS MODIFICADOS ({len(modificados)}) - Se REPROCESARAN")
        print("="*70)
        for archivo, nombre, sha_old, sha_new in modificados:
            print(f"  [MODIFICADO] {nombre}")
            print(f"    SHA anterior: {sha_old}...")
            print(f"    SHA actual:   {sha_new}...")
        print()
    
    # Estimacion de costo
    if pendientes or modificados:
        print("="*70)
        print("ESTIMACION DE COSTO")
        print("="*70)
        
        # Asumir ~1,300 tokens por documento (basado en el ejemplo)
        tokens_por_doc = 1300
        costo_por_1k_tokens = 0.0001
        
        docs_a_procesar = len(pendientes) + len(modificados)
        tokens_totales = docs_a_procesar * tokens_por_doc
        costo_usd = (tokens_totales / 1000) * costo_por_1k_tokens
        costo_mxn = costo_usd * 17
        
        print(f"  Documentos a procesar: {docs_a_procesar}")
        print(f"  Tokens estimados: {tokens_totales:,}")
        print(f"  Costo estimado (USD): ${costo_usd:.6f}")
        print(f"  Costo estimado (MXN): ${costo_mxn:.4f}")
        print()
        
        # Nota sobre cache de embeddings
        print("  NOTA: El cache de embeddings puede reducir este costo")
        print("        si hay texto similar entre documentos.")
        print()
    
    # Recomendaciones
    print("="*70)
    print("RECOMENDACIONES")
    print("="*70)
    
    if len(procesados) > 0:
        print(f"  [OK] {len(procesados)} documentos ya procesados se OMITIRAN")
        print("       (no se generaran embeddings nuevos, ahorro de costo)")
        print()
    
    if len(pendientes) > 0:
        print(f"  [ACCION] {len(pendientes)} documentos nuevos se procesaran")
        print("           Estos son documentos que nunca se han indexado")
        print()
    
    if len(modificados) > 0:
        print(f"  [ATENCION] {len(modificados)} documentos modificados se reprocesaran")
        print("             Aunque dijiste que no se modificaran, estos cambiaron")
        print()
    
    if len(pendientes) == 0 and len(modificados) == 0:
        print("  [INFO] Todos los documentos ya estan procesados")
        print("         No hay nada que hacer!")
        print()
    
    # Comando sugerido
    if len(pendientes) > 0 or len(modificados) > 0:
        print("="*70)
        print("COMANDO PARA PROCESAR")
        print("="*70)
        print()
        print("  python -m Tools.docs_indexer \\")
        print("    --universe meetings_weekly \\")
        print("    --input_dir knowledgebase/meetings_weekly \\")
        print("    --out_dir Data")
        print()
        print("  El sistema automaticamente:")
        print("    - Omitira los", len(procesados), "documentos ya procesados")
        print("    - Procesara los", len(pendientes) + len(modificados), "documentos nuevos/modificados")
        print()

if __name__ == "__main__":
    main()

