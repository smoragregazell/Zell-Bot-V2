# Tools/etiquetas_indexer/__main__.py
# CLI para indexar etiquetas

import argparse
import sys
from pathlib import Path

from .indexer import build_etiquetas_index
from .config import DEFAULT_EXCEL_PATH, UNIVERSE_NAME


def main():
    parser = argparse.ArgumentParser(
        description="Indexa etiquetas del sistema ZELL en FAISS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Indexar con ruta por defecto
  python -m Tools.etiquetas_indexer
  
  # Indexar con Excel personalizado
  python -m Tools.etiquetas_indexer --excel "ruta/al/excel.xlsx"
  
  # Especificar directorio de salida
  python -m Tools.etiquetas_indexer --out-dir "Data"
        """
    )
    
    parser.add_argument(
        "--excel",
        type=str,
        default=DEFAULT_EXCEL_PATH,
        help=f"Ruta al archivo Excel con etiquetas (default: {DEFAULT_EXCEL_PATH})"
    )
    
    parser.add_argument(
        "--out-dir",
        type=str,
        default="Data",
        help="Directorio donde guardar el índice y metadata (default: Data)"
    )
    
    parser.add_argument(
        "--universe",
        type=str,
        default=UNIVERSE_NAME,
        help=f"Nombre del universo (default: {UNIVERSE_NAME})"
    )
    
    args = parser.parse_args()
    
    # Validar que el Excel existe
    if not Path(args.excel).exists():
        print(f"❌ Error: No existe el archivo Excel: {args.excel}")
        sys.exit(1)
    
    print(f"📊 Indexando etiquetas desde: {args.excel}")
    print(f"📁 Directorio de salida: {args.out_dir}")
    print(f"🌐 Universo: {args.universe}")
    print()
    
    result = build_etiquetas_index(
        excel_path=args.excel,
        out_dir=args.out_dir,
        universe=args.universe,
    )
    
    if not result.get("ok"):
        print(f"❌ Error: {result.get('error', 'Error desconocido')}")
        sys.exit(1)
    
    print("✅ Indexación completada exitosamente")
    print()
    print("📊 Estadísticas:")
    print(f"  - Etiquetas indexadas: {result.get('chunks_total', 0)}")
    print(f"  - Etiquetas únicas: {result.get('unique_etiquetas', 0)}")
    print(f"  - Vectores en índice: {result.get('chunks_indexed', 0)}")
    print(f"  - Dimensión: {result.get('dim', 0)}")
    print()
    print("📁 Archivos generados:")
    print(f"  - Índice FAISS: {result.get('index_path')}")
    print(f"  - Metadata JSONL: {result.get('meta_path')}")
    print(f"  - Cache embeddings: {result.get('emb_cache_path')}")
    print()
    
    if result.get("incremental_update"):
        print("ℹ️  Se actualizó el índice existente (actualización incremental)")
    else:
        print("ℹ️  Se creó un nuevo índice")


if __name__ == "__main__":
    main()

