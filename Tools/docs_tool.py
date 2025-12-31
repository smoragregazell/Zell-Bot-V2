# Tools/docs_tool.py
import os
import json
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import faiss

from Tools.semantic_tool import generate_openai_embedding


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n == 0:
        return v
    return v / n


def _load_meta(meta_path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_index_and_meta(universe: str, data_dir: str = "Data") -> Tuple[Any, List[Dict[str, Any]]]:
    idx_path = os.path.join(data_dir, f"docs_{universe}.index")
    meta_path = os.path.join(data_dir, f"docs_{universe}_meta.jsonl")

    if not os.path.exists(idx_path):
        raise FileNotFoundError(f"No existe index: {idx_path}")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"No existe meta: {meta_path}")

    index = faiss.read_index(idx_path)
    meta = _load_meta(meta_path)
    return index, meta


def search_docs(query: str, universe: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Busca chunks relevantes en un universo de docs.
    Devuelve: hits con chunk_id + metadata ligera (sin texto completo pesado).
    """
    index, meta = _load_index_and_meta(universe)

    emb = generate_openai_embedding(query, conversation_id=f"docs_search:{universe}", interaction_id=None)
    if emb is None:
        return {"ok": False, "error": "embedding_failed"}

    q = _normalize(np.array(emb, dtype=np.float32)).reshape(1, -1)
    scores, ids = index.search(q, top_k)

    hits = []
    for rank, i in enumerate(ids[0].tolist()):
        if i < 0 or i >= len(meta):
            continue
        m = meta[i]
        hits.append({
            "rank": rank + 1,
            "score": float(scores[0][rank]),
            "chunk_id": m.get("chunk_id"),
            "doc_id": m.get("doc_id"),
            "title": m.get("catalog_title") or m.get("title"),
            "section": m.get("section"),
            "codigo": m.get("codigo"),
            "fecha_emision": m.get("fecha_emision"),
            "revision": m.get("revision"),
            "estatus": m.get("estatus"),
            "source_path": m.get("source_path"),
        })

    return {"ok": True, "universe": universe, "query": query, "hits": hits}


def get_doc_context(
    universe: str,
    chunk_ids: Optional[List[str]] = None,
    doc_id: Optional[str] = None,
    max_chunks: int = 6
) -> Dict[str, Any]:
    """
    Regresa texto (chunks) para contexto.
    - Si pasas chunk_ids: regresa esos chunks (hasta max_chunks).
    - Si pasas doc_id: regresa los primeros max_chunks de ese doc.
    """
    _, meta = _load_index_and_meta(universe)

    selected = []

    if chunk_ids:
        want = set(chunk_ids)
        for m in meta:
            if m.get("chunk_id") in want:
                selected.append(m)
                if len(selected) >= max_chunks:
                    break

    elif doc_id:
        for m in meta:
            if m.get("doc_id") == doc_id:
                selected.append(m)
                if len(selected) >= max_chunks:
                    break
    else:
        return {"ok": False, "error": "provide chunk_ids or doc_id"}

    if not selected:
        return {"ok": False, "error": "no_chunks_found"}

    blocks = []
    for m in selected:
        header = []
        if m.get("codigo"):
            header.append(f"Código: {m.get('codigo')}")
        if m.get("fecha_emision"):
            header.append(f"Emisión: {m.get('fecha_emision')}")
        if m.get("revision") is not None:
            header.append(f"Rev: {m.get('revision')}")
        if m.get("estatus"):
            header.append(f"Estatus: {m.get('estatus')}")

        title = m.get("catalog_title") or m.get("title")
        section = m.get("section") or ""

        blocks.append({
            "chunk_id": m.get("chunk_id"),
            "doc_id": m.get("doc_id"),
            "title": title,
            "section": section,
            "header": " | ".join(header),
            "text": m.get("text", ""),
        })

    return {"ok": True, "universe": universe, "blocks": blocks}
