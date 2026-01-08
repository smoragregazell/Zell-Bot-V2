# Tools/guides_indexer/__main__.py
# Script para ejecutar el indexador de guías

import argparse
import sys
from pathlib import Path

from .indexer import build_guides_index


def main():
    ap = argparse.ArgumentParser(
        description="Indexa guías de usuario del sistema Zell en FAISS"
    )
    ap.add_argument(
        "--input",
        default="knowledgebase/user_guides",
        help="Directorio con archivos DOCX de guías"
    )
    ap.add_argument(
        "--out",
        default="Data",
        help="Directorio de salida para índices y metadata"
    )
    ap.add_argument(
        "--catalog",
        default="Data/guides_catalog.json",
        help="Ruta al catálogo JSON de guías"
    )
    ap.add_argument(
        "--max-files",
        type=int,
        help="Máximo número de archivos a procesar (útil para pruebas)"
    )
    ap.add_argument(
        "--top-level-only",
        action="store_true",
        help="Solo procesar archivos en el nivel superior (no subdirectorios)"
    )
    
    args = ap.parse_args()

    print(f"[guides_indexer] Iniciando indexación de guías...")
    print(f"  Input: {args.input}")
    print(f"  Output: {args.out}")
    print(f"  Catálogo: {args.catalog}")

    result = build_guides_index(
        universe="user_guides",
        input_dir=args.input,
        out_dir=args.out,
        catalog_path=args.catalog,
        max_files=args.max_files,
        top_level_only=args.top_level_only,
    )

    if not result.get("ok"):
        print(f"[guides_indexer] ERROR: {result.get('error')}")
        sys.exit(1)

    print(f"[guides_indexer] Indexacion completada:")
    print(f"  Archivos encontrados: {result.get('files', 0)}")
    print(f"  Archivos procesados: {result.get('files_processed', 0)}")
    print(f"  Archivos omitidos (ya procesados): {result.get('files_skipped', 0)}")
    print(f"  Documentos únicos: {result.get('docs', 0)}")
    print(f"  Chunks nuevos: {result.get('chunks_new', 0)}")
    print(f"  Chunks totales: {result.get('chunks_total', 0)}")
    print(f"  Dimensión vectores: {result.get('dim', 0)}")
    print(f"  Coincidencias con catálogo: {result.get('catalog_docs_matched_by_filename', 0)}")
    print(f"  Índice FAISS: {result.get('index_path')}")
    print(f"  Metadata JSONL: {result.get('meta_path')}")
    
    if result.get("incremental_update"):
        print(f"  [Actualización incremental - se agregaron chunks a índice existente]")


if __name__ == "__main__":
    main()

