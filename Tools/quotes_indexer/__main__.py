# Tools/quotes_indexer/__main__.py
# CLI para indexar cotizaciones

import argparse
import sys
from pathlib import Path

from .indexer import build_quotes_index
from .config import DEFAULT_EXCEL_PATH, UNIVERSE_NAME


def main():
    parser = argparse.ArgumentParser(
        description="Indexa cotizaciones del sistema ZELL en FAISS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Indexar con ruta por defecto
  python -m Tools.quotes_indexer
  
  # Indexar con Excel personalizado
  python -m Tools.quotes_indexer --excel "ruta/al/excel.xlsx"
  
  # Especificar directorio de salida
  python -m Tools.quotes_indexer --out-dir "Data"
        """
    )
    
    parser.add_argument(
        "--excel",
        type=str,
        default=DEFAULT_EXCEL_PATH,
        help=f"Ruta al archivo Excel con cotizaciones (default: {DEFAULT_EXCEL_PATH})"
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
        print(f"Error: No existe el archivo Excel: {args.excel}")
        sys.exit(1)
    
    print(f"Indexando cotizaciones desde: {args.excel}")
    print(f"Directorio de salida: {args.out_dir}")
    print(f"Universo: {args.universe}")
    print()
    
    result = build_quotes_index(
        excel_path=args.excel,
        out_dir=args.out_dir,
        universe=args.universe,
    )
    
    if not result.get("ok"):
        print(f"Error: {result.get('error', 'Error desconocido')}")
        sys.exit(1)
    
    print("Indexacion completada exitosamente")
    print()
    print("Estadisticas:")
    print(f"  - Cotizaciones indexadas: {result.get('chunks_total', 0)}")
    print(f"  - Cotizaciones unicas: {result.get('unique_quotes', 0)}")
    print(f"  - Vectores en indice: {result.get('chunks_indexed', 0)}")
    print(f"  - Dimension: {result.get('dim', 0)}")
    print()
    print("Archivos generados:")
    print(f"  - Indice FAISS: {result.get('index_path')}")
    print(f"  - Metadata JSONL: {result.get('meta_path')}")
    print(f"  - Cache embeddings: {result.get('emb_cache_path')}")
    print()
    
    if result.get("incremental_update"):
        print("Se actualizo el indice existente (actualizacion incremental)")
    else:
        print("Se creo un nuevo indice")


if __name__ == "__main__":
    main()

