# Tools/docs_indexer/embeddings.py
# Cache y generación de embeddings

import os
import json
from typing import Dict, Any, Optional, List

import numpy as np

from Tools.search_tickets import generate_openai_embedding
from .utils import fingerprint_text, normalize_vec_1d


def _normalize_universe_name(universe: str) -> str:
    """
    Normaliza el nombre del universo para evitar duplicar el prefijo 'docs_'.
    Si el universo ya empieza con 'docs_', lo deja igual.
    Si no, agrega el prefijo 'docs_'.
    """
    if universe.startswith("docs_"):
        return universe
    return f"docs_{universe}"


def _emb_cache_path(out_dir: str, universe: str) -> str:
    """Retorna la ruta del archivo de cache de embeddings para un universo."""
    index_name = _normalize_universe_name(universe)
    return os.path.join(out_dir, f"{index_name}_emb_cache.jsonl")


def load_emb_cache(out_dir: str, universe: str) -> Dict[str, Dict[str, Any]]:
    """
    Carga el cache de embeddings desde un archivo JSONL.
    Returns: dict con clave cache_key = chunk_id + "|" + text_fp
    Valor: {"embedding": [...], "dim": int}
    """
    p = _emb_cache_path(out_dir, universe)
    if not os.path.exists(p):
        return {}
    cache: Dict[str, Dict[str, Any]] = {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                ck = row.get("cache_key")
                if ck:
                    cache[ck] = row
    except Exception:
        return {}
    return cache


def append_emb_cache(out_dir: str, universe: str, cache_key: str, embedding: List[float]) -> None:
    """Añade una entrada al cache de embeddings."""
    p = _emb_cache_path(out_dir, universe)
    row = {"cache_key": cache_key, "embedding": embedding, "dim": len(embedding)}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def embedding_to_1d_list(x: Any) -> Optional[List[float]]:
    """
    Convierte un embedding a lista 1D.
    generate_openai_embedding en tu proyecto retorna np.ndarray (1, d) normalizado,
    pero algunos paths pueden retornar lista; maneja ambos.
    """
    if x is None:
        return None
    try:
        arr = np.asarray(x, dtype=np.float32)
        arr = arr.reshape(-1)
        return arr.tolist()
    except Exception:
        return None


def embed_text_cached(
    text: str,
    chunk_id: str,
    universe: str,
    out_dir: str,
    cache: Dict[str, Dict[str, Any]]
) -> Optional[np.ndarray]:
    """
    Genera embedding para un texto con cache.
    Returns: vector normalizado 1D float32.
    """
    text_fp = fingerprint_text(text)
    cache_key = f"{chunk_id}|{text_fp}"

    if cache_key in cache:
        emb_list = cache[cache_key].get("embedding")
        if isinstance(emb_list, list) and emb_list:
            return normalize_vec_1d(np.array(emb_list, dtype=np.float32))

    vec = generate_openai_embedding(
        text,
        conversation_id=f"index_docs:{universe}",
        interaction_id=None
    )
    emb_list = embedding_to_1d_list(vec)
    if emb_list is None:
        return None

    append_emb_cache(out_dir, universe, cache_key, emb_list)
    cache[cache_key] = {"cache_key": cache_key, "embedding": emb_list, "dim": len(emb_list)}
    return normalize_vec_1d(np.array(emb_list, dtype=np.float32))


def get_emb_cache_path(out_dir: str, universe: str) -> str:
    """Obtiene la ruta del archivo de cache de embeddings (función pública)."""
    return _emb_cache_path(out_dir, universe)

