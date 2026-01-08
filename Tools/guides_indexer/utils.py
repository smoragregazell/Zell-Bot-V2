# Tools/guides_indexer/utils.py
# Utilidades - reutiliza funciones de docs_indexer cuando es posible

from Tools.docs_indexer.utils import (
    file_sha256,
    fingerprint_text,
    chunk_text_tokens,
    normalize_vec_1d,
)

__all__ = [
    "file_sha256",
    "fingerprint_text",
    "chunk_text_tokens",
    "normalize_vec_1d",
]

