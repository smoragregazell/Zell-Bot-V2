"""
Buscar documentos - Búsqueda semántica de chunks de documentos en universos.
Complementa a get_docs.py:
- search_docs.py: Buscar documentos (búsqueda semántica con FAISS)
- get_docs.py: Obtener contexto completo de documentos (chunks con texto completo)
"""
import os
import json
from typing import List, Dict, Any, Tuple

import numpy as np
import faiss

from Tools.search_tickets import generate_openai_embedding


def _normalize(v: np.ndarray) -> np.ndarray:
    """Normaliza un vector a norma unitaria."""
    n = np.linalg.norm(v)
    if n == 0:
        return v
    return v / n


def _load_meta(meta_path: str) -> List[Dict[str, Any]]:
    """Carga metadata de documentos desde archivo JSONL."""
    rows = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_index_and_meta(universe: str, data_dir: str = "Data") -> Tuple[Any, List[Dict[str, Any]]]:
    """
    Carga el índice FAISS y la metadata para un universo de documentos.
    
    Args:
        universe: Nombre del universo (ej: "docs_org", "docs_iso", "user_guides")
        data_dir: Directorio donde están los archivos de índice y metadata
    
    Returns:
        Tupla (index, meta) donde index es el índice FAISS y meta es la lista de metadata
    """
    # Si el universo ya tiene prefijo conocido, no agregar el prefijo "docs_"
    # Esto permite usar "docs_org", "user_guides", etc. directamente
    if universe.startswith("docs_") or universe.startswith("user_"):
        index_name = universe
    else:
        index_name = f"docs_{universe}"
    
    idx_path = os.path.join(data_dir, f"{index_name}.index")
    meta_path = os.path.join(data_dir, f"{index_name}_meta.jsonl")

    if not os.path.exists(idx_path):
        raise FileNotFoundError(f"No existe index: {idx_path}")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"No existe meta: {meta_path}")

    index = faiss.read_index(idx_path)
    meta = _load_meta(meta_path)
    return index, meta


def search_docs(query: str, universe: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Busca chunks relevantes en un universo de documentos usando búsqueda semántica (FAISS).
    
    Retorna hits con chunk_id + metadata ligera (sin texto completo pesado).
    
    Para meetings_weekly, aplica filtro de similitud: solo retorna resultados con score <= 0.6
    (muy relevantes: < 0.4, relevantes: 0.4-0.6, irrelevantes: > 0.6 son filtrados).
    
    Args:
        query: Texto de búsqueda
        universe: Nombre del universo (ej: "docs_org", "docs_iso", "user_guides", "meetings_weekly")
        top_k: Número de resultados a retornar (máximo antes del filtro de similitud)
    
    Returns:
        Dict con formato:
        {
            "ok": True/False,
            "universe": str,
            "query": str,
            "hits": [
                {
                    "rank": int,
                    "score": float,  # Para meetings_weekly, solo scores <= 0.6
                    "chunk_id": str,
                    "doc_id": str,
                    "title": str,
                    "section": str,
                    "codigo": str,
                    "fecha_emision": str,
                    "revision": int,
                    "estatus": str,
                    "source_path": str,
                    # Metadata adicional para meetings_weekly
                    "meeting_date": str (opcional),
                    "meeting_start": str (opcional),
                    "meeting_end": str (opcional),
                    "row_key": str (opcional),
                    "block_kind": str (opcional),
                },
                ...
            ]
        }
    """
    index, meta = _load_index_and_meta(universe)

    emb = generate_openai_embedding(query, conversation_id=f"docs_search:{universe}", interaction_id=None)
    if emb is None:
        return {"ok": False, "error": "embedding_failed"}

    q = _normalize(np.array(emb, dtype=np.float32)).reshape(1, -1)
    scores, ids = index.search(q, top_k)

    # Umbral de similitud para meetings_weekly: solo retornar resultados relevantes (score <= 0.6)
    # Score < 0.4: muy relevante, Score 0.4-0.6: relevante, Score > 0.6: irrelevante
    similarity_threshold = 0.6 if universe == "meetings_weekly" else None

    hits = []
    for rank, i in enumerate(ids[0].tolist()):
        if i < 0 or i >= len(meta):
            continue
        
        score = float(scores[0][rank])
        
        # Filtrar por umbral de similitud para meetings_weekly
        if similarity_threshold is not None and score > similarity_threshold:
            continue
        
        m = meta[i]
        # Construir metadata según tipo de documento
        metadata = {
            "doc_id": m.get("doc_id"),
            "title": m.get("catalog_title") or m.get("title"),
            "section": m.get("section"),
            "codigo": m.get("codigo"),
            "fecha_emision": m.get("fecha_emision"),
            "revision": m.get("revision"),
            "estatus": m.get("estatus"),
            "source_path": m.get("source_path"),
        }
        
        # Metadata específica para meetings_weekly
        if m.get("meeting_date"):
            metadata["meeting_date"] = m.get("meeting_date")
            metadata["meeting_start"] = m.get("meeting_start")
            metadata["meeting_end"] = m.get("meeting_end")
        if m.get("row_key"):
            metadata["row_key"] = m.get("row_key")
        if m.get("block_kind"):
            metadata["block_kind"] = m.get("block_kind")
        
        # Metadata específica para user_guides
        if m.get("objetivo"):
            metadata["objetivo"] = m.get("objetivo")
        if m.get("step_label"):
            metadata["step_label"] = m.get("step_label")
        if m.get("step_number"):
            metadata["step_number"] = m.get("step_number")
        if m.get("doc_number"):
            metadata["doc_number"] = m.get("doc_number")
        if m.get("referencia_cliente_ticket"):
            metadata["referencia_cliente_ticket"] = m.get("referencia_cliente_ticket")
        
        hits.append({
            "rank": len(hits) + 1,  # Re-numerar después del filtro
            "score": score,
            "chunk_id": m.get("chunk_id"),
            "doc_id": m.get("doc_id"),
            "title": m.get("catalog_title") or m.get("title"),
            "section": m.get("section"),
            "codigo": m.get("codigo"),
            "fecha_emision": m.get("fecha_emision"),
            "revision": m.get("revision"),
            "estatus": m.get("estatus"),
            "source_path": m.get("source_path"),
            **{k: v for k, v in metadata.items() if k not in ["doc_id", "title", "section", "codigo", "fecha_emision", "revision", "estatus", "source_path"]}
        })

    return {"ok": True, "universe": universe, "query": query, "hits": hits}

