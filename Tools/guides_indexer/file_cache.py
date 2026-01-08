# Tools/guides_indexer/file_cache.py
# Cache de archivos procesados - reutiliza lógica de docs_indexer

# Reutilizar directamente desde docs_indexer
from Tools.docs_indexer.file_cache import (
    load_file_cache,
    save_file_cache,
    get_unprocessed_files,
    mark_file_processed,
    get_file_cache_path,
)

__all__ = [
    "load_file_cache",
    "save_file_cache",
    "get_unprocessed_files",
    "mark_file_processed",
    "get_file_cache_path",
]

