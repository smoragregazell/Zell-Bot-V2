# Tools/docs_indexer/__main__.py
# CLI entry point para el indexador de documentos
# Uso: python -m Tools.docs_indexer --universe ...

import json
import argparse

from .indexer import build_docs_index
from .config import DEFAULT_CHUNK_TOKENS, DEFAULT_OVERLAP_TOKENS


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--universe", required=True)
    p.add_argument("--input_dir", required=True)
    p.add_argument("--out_dir", default="Data")
    p.add_argument("--chunk_tokens", type=int, default=DEFAULT_CHUNK_TOKENS)
    p.add_argument("--overlap_tokens", type=int, default=DEFAULT_OVERLAP_TOKENS)
    p.add_argument("--encoding", default="cl100k_base")
    p.add_argument("--top_level_only", action="store_true")
    p.add_argument("--max_files", type=int, default=None)
    p.add_argument("--catalog", default="Data/doc_catalog.json")
    args = p.parse_args()

    res = build_docs_index(
        universe=args.universe,
        input_dir=args.input_dir,
        out_dir=args.out_dir,
        encoding_name=args.encoding,
        chunk_tokens=args.chunk_tokens,
        overlap_tokens=args.overlap_tokens,
        top_level_only=args.top_level_only,
        max_files=args.max_files,
        catalog_path=args.catalog,
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

