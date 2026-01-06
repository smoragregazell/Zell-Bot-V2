"""
Script de verificacion previa antes de procesar 350 documentos.
Verifica que el sistema de cache este funcionando correctamente.
"""
import os
import json
from pathlib import Path

def verificar_cache_archivos(universe: str, out_dir: str = "Data"):
    """Verifica el cache de archivos procesados"""
    print(f"\n{'='*70}")
    print(f"VERIFICACION: Cache de Archivos ({universe})")
    print(f"{'='*70}")
    
    cache_path = os.path.join(out_dir, f"docs_{universe}_file_cache.json")
    
    if not os.path.exists(cache_path):
        print(f"  [ADVERTENCIA] No existe el archivo de cache: {cache_path}")
        print(f"  Esto es normal si es la primera vez que se procesa este universo.")
        print(f"  El cache se creara automaticamente al procesar.")
        return False
    else:
        print(f"  [OK] Archivo de cache existe: {cache_path}")
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            
            if isinstance(cache_data, dict):
                num_archivos = len(cache_data)
                print(f"  [OK] Cache contiene {num_archivos} archivos procesados")
                
                # Mostrar algunos ejemplos
                if num_archivos > 0:
                    print(f"\n  Ejemplos de archivos en cache:")
                    for i, (path, info) in enumerate(list(cache_data.items())[:3]):
                        sha = info.get("sha256", "N/A")[:12] if isinstance(info, dict) else "N/A"
                        print(f"    - {os.path.basename(path)} (SHA: {sha}...)")
                    if num_archivos > 3:
                        print(f"    ... y {num_archivos - 3} mas")
                
                return True
            else:
                print(f"  [ERROR] Formato de cache invalido (debe ser dict)")
                return False
                
        except Exception as e:
            print(f"  [ERROR] No se pudo leer el cache: {e}")
            return False

def verificar_cache_embeddings(universe: str, out_dir: str = "Data"):
    """Verifica el cache de embeddings"""
    print(f"\n{'='*70}")
    print(f"VERIFICACION: Cache de Embeddings ({universe})")
    print(f"{'='*70}")
    
    cache_path = os.path.join(out_dir, f"docs_{universe}_emb_cache.jsonl")
    
    if not os.path.exists(cache_path):
        print(f"  [ADVERTENCIA] No existe el archivo de cache de embeddings: {cache_path}")
        print(f"  Esto es normal si es la primera vez que se procesa este universo.")
        print(f"  El cache se creara automaticamente al procesar.")
        return False
    else:
        print(f"  [OK] Archivo de cache de embeddings existe: {cache_path}")
        
        try:
            count = 0
            with open(cache_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
            
            print(f"  [OK] Cache contiene {count:,} embeddings guardados")
            
            # Calcular tamano del archivo
            size_mb = os.path.getsize(cache_path) / (1024 * 1024)
            print(f"  [INFO] Tamano del cache: {size_mb:.2f} MB")
            
            return True
                
        except Exception as e:
            print(f"  [ERROR] No se pudo leer el cache: {e}")
            return False

def verificar_indice_faiss(universe: str, out_dir: str = "Data"):
    """Verifica que el indice FAISS exista"""
    print(f"\n{'='*70}")
    print(f"VERIFICACION: Indice FAISS ({universe})")
    print(f"{'='*70}")
    
    index_path = os.path.join(out_dir, f"docs_{universe}.index")
    meta_path = os.path.join(out_dir, f"docs_{universe}_meta.jsonl")
    
    index_exists = os.path.exists(index_path)
    meta_exists = os.path.exists(meta_path)
    
    if index_exists:
        print(f"  [OK] Indice FAISS existe: {index_path}")
        size_mb = os.path.getsize(index_path) / (1024 * 1024)
        print(f"  [INFO] Tamano del indice: {size_mb:.2f} MB")
    else:
        print(f"  [INFO] Indice FAISS no existe (se creara al procesar)")
    
    if meta_exists:
        print(f"  [OK] Archivo de metadatos existe: {meta_path}")
        
        # Contar chunks
        try:
            count = 0
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
            print(f"  [INFO] Metadatos contienen {count:,} chunks")
        except Exception as e:
            print(f"  [ADVERTENCIA] No se pudo contar chunks: {e}")
    else:
        print(f"  [INFO] Archivo de metadatos no existe (se creara al procesar)")
    
    return index_exists and meta_exists

def verificar_api_key():
    """Verifica que la API key de OpenAI este configurada"""
    print(f"\n{'='*70}")
    print(f"VERIFICACION: API Key de OpenAI")
    print(f"{'='*70}")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_keys = [
        os.getenv("OPENAI_API_KEY_Semantic"),
        os.getenv("OPENAI_API_KEY_SEMANTIC"),
        os.getenv("OPENAI_API_KEY_V2"),
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_API_KEY_Clasificador"),
    ]
    
    api_key = next((k for k in api_keys if k), None)
    
    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"  [OK] API Key encontrada: {masked}")
        print(f"  [INFO] Se usara para generar embeddings con text-embedding-ada-002")
        return True
    else:
        print(f"  [ERROR] No se encontro API Key de OpenAI")
        print(f"  [INFO] Buscando en variables:")
        print(f"    - OPENAI_API_KEY_Semantic")
        print(f"    - OPENAI_API_KEY_SEMANTIC")
        print(f"    - OPENAI_API_KEY_V2")
        print(f"    - OPENAI_API_KEY")
        print(f"    - OPENAI_API_KEY_Clasificador")
        return False

def verificar_directorio_entrada(input_dir: str):
    """Verifica que el directorio de entrada exista y tenga archivos"""
    print(f"\n{'='*70}")
    print(f"VERIFICACION: Directorio de Entrada")
    print(f"{'='*70}")
    
    if not os.path.exists(input_dir):
        print(f"  [ERROR] El directorio no existe: {input_dir}")
        return False
    
    print(f"  [OK] Directorio existe: {input_dir}")
    
    # Contar archivos .docx
    docx_files = list(Path(input_dir).glob("*.docx"))
    num_docx = len(docx_files)
    
    print(f"  [INFO] Archivos .docx encontrados: {num_docx}")
    
    if num_docx > 0:
        print(f"\n  Primeros 5 archivos:")
        for f in docx_files[:5]:
            size_kb = f.stat().st_size / 1024
            print(f"    - {f.name} ({size_kb:.1f} KB)")
        if num_docx > 5:
            print(f"    ... y {num_docx - 5} mas")
    
    return True

def verificar_permisos_escritura(out_dir: str = "Data"):
    """Verifica permisos de escritura en el directorio de salida"""
    print(f"\n{'='*70}")
    print(f"VERIFICACION: Permisos de Escritura")
    print(f"{'='*70}")
    
    if not os.path.exists(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
            print(f"  [OK] Directorio creado: {out_dir}")
        except Exception as e:
            print(f"  [ERROR] No se pudo crear directorio: {e}")
            return False
    else:
        print(f"  [OK] Directorio existe: {out_dir}")
    
    # Intentar escribir un archivo de prueba
    test_file = os.path.join(out_dir, ".test_write")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print(f"  [OK] Permisos de escritura verificados")
        return True
    except Exception as e:
        print(f"  [ERROR] No se puede escribir en el directorio: {e}")
        return False

def main():
    print("="*70)
    print("VERIFICACION PREVIA ANTES DE PROCESAR 350 DOCUMENTOS")
    print("="*70)
    
    universe = "meetings_weekly"
    input_dir = "knowledgebase/meetings_weekly"
    out_dir = "Data"
    
    resultados = {}
    
    # 1. Verificar API Key
    resultados["api_key"] = verificar_api_key()
    
    # 2. Verificar directorio de entrada
    resultados["directorio_entrada"] = verificar_directorio_entrada(input_dir)
    
    # 3. Verificar permisos de escritura
    resultados["permisos"] = verificar_permisos_escritura(out_dir)
    
    # 4. Verificar cache de archivos
    resultados["cache_archivos"] = verificar_cache_archivos(universe, out_dir)
    
    # 5. Verificar cache de embeddings
    resultados["cache_embeddings"] = verificar_cache_embeddings(universe, out_dir)
    
    # 6. Verificar indice FAISS
    resultados["indice_faiss"] = verificar_indice_faiss(universe, out_dir)
    
    # Resumen
    print(f"\n{'='*70}")
    print("RESUMEN DE VERIFICACION")
    print(f"{'='*70}")
    
    criticos = ["api_key", "directorio_entrada", "permisos"]
    advertencias = ["cache_archivos", "cache_embeddings", "indice_faiss"]
    
    todo_ok = True
    for check in criticos:
        status = "OK" if resultados[check] else "ERROR"
        print(f"  {check:20s}: {status}")
        if not resultados[check]:
            todo_ok = False
    
    print()
    for check in advertencias:
        status = "OK" if resultados[check] else "ADVERTENCIA (normal si es primera vez)"
        print(f"  {check:20s}: {status}")
    
    print()
    if todo_ok:
        print("  [RESULTADO] Sistema listo para procesar documentos")
        print("  [INFO] El sistema de cache evitara reprocesar archivos ya indexados")
        print("  [INFO] Solo se procesaran archivos nuevos o modificados")
    else:
        print("  [RESULTADO] Hay problemas criticos que deben resolverse primero")
        print("  [ACCION] Revisa los errores arriba antes de continuar")
    
    print(f"\n{'='*70}")
    print("RECOMENDACIONES ANTES DE PROCESAR:")
    print(f"{'='*70}")
    print("1. Asegurate de tener suficiente espacio en disco")
    print("   - Cada documento genera ~6 chunks")
    print("   - 350 documentos = ~2,100 chunks")
    print("   - Cache de embeddings: ~1-2 MB por 1000 chunks")
    print()
    print("2. Verifica que los archivos .docx esten en buen estado")
    print("   - No corruptos")
    print("   - Formato correcto (minutas semanales)")
    print()
    print("3. Considera procesar en lotes si son muchos archivos")
    print("   - Usa --max_files para limitar")
    print("   - Ejemplo: --max_files 50 para procesar 50 a la vez")
    print()
    print("4. El sistema es incremental:")
    print("   - Si un archivo ya esta procesado, se omite")
    print("   - Si un archivo cambio (SHA256 diferente), se reprocesa")
    print("   - Los embeddings se cachean por chunk_id + texto")
    print()
    print("5. Monitorea el progreso:")
    print("   - Revisa los logs de salida")
    print("   - Verifica que el cache se actualice correctamente")
    print()

if __name__ == "__main__":
    main()

