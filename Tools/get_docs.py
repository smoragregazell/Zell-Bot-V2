"""
Obtener documentos - Obtiene contexto completo de documentos (chunks con texto completo).
Complementa a search_docs.py:
- search_docs.py: Buscar documentos (búsqueda semántica con FAISS)
- get_docs.py: Obtener contexto completo de documentos (chunks con texto completo)
"""
import os
import json
from typing import List, Dict, Any, Optional

from Tools.search_docs import _load_meta, _load_index_and_meta


def get_doc_context(
    universe: str,
    chunk_ids: Optional[List[str]] = None,
    doc_id: Optional[str] = None,
    max_chunks: int = 6,
    expand_adjacent: bool = True
) -> Dict[str, Any]:
    """
    Obtiene el texto completo de chunks para contexto.
    
    - Si pasas chunk_ids: regresa esos chunks + chunks adyacentes (1 arriba, 1 abajo) del mismo doc.
    - Si pasas doc_id: regresa los primeros max_chunks de ese doc.
    
    Args:
        universe: Nombre del universo (ej: "docs_org", "docs_iso", "user_guides")
        chunk_ids: Lista de chunk_ids a obtener (opcional)
        doc_id: ID del documento del cual obtener los primeros chunks (opcional)
        max_chunks: Número máximo de chunks a retornar cuando se usa doc_id
        expand_adjacent: Si True, incluye chunks adyacentes (anterior y siguiente) del mismo documento cuando se usa chunk_ids
    
    Returns:
        Dict con formato:
        {
            "ok": True/False,
            "universe": str,
            "blocks": [
                {
                    "chunk_id": str,
                    "doc_id": str,
                    "title": str,
                    "section": str,
                    "header": str,  # Header formateado con metadata
                    "text": str,    # Texto completo del chunk
                    "meeting_date": str (opcional),
                    "row_key": str (opcional),
                    "block_kind": str (opcional),
                },
                ...
            ]
        }
    """
    _, meta = _load_index_and_meta(universe)

    selected = []
    selected_ids = set()

    if chunk_ids:
        # Crear índice de chunks por doc_id y chunk_index para búsqueda rápida
        chunks_by_id = {m.get("chunk_id"): m for m in meta}
        chunks_by_doc_and_index = {}  # {doc_id: {chunk_index: chunk}}
        
        for m in meta:
            doc_id_key = m.get("doc_id")
            chunk_idx = m.get("chunk_index")
            if doc_id_key and chunk_idx is not None:
                if doc_id_key not in chunks_by_doc_and_index:
                    chunks_by_doc_and_index[doc_id_key] = {}
                chunks_by_doc_and_index[doc_id_key][chunk_idx] = m
        
        # ESPECIAL: Para user_guides, devolver TODO el documento completo
        if universe == "user_guides":
            # Encontrar el doc_id del primer chunk solicitado
            first_chunk = None
            for chunk_id in chunk_ids:
                if chunk_id in chunks_by_id:
                    first_chunk = chunks_by_id[chunk_id]
                    break
            
            if first_chunk:
                doc_id_key = first_chunk.get("doc_id")
                if doc_id_key and doc_id_key in chunks_by_doc_and_index:
                    # Obtener TODOS los chunks del mismo documento
                    doc_chunks = chunks_by_doc_and_index[doc_id_key]
                    for chunk_idx in sorted(doc_chunks.keys()):
                        chunk = doc_chunks[chunk_idx]
                        selected.append(chunk)
                        selected_ids.add(chunk.get("chunk_id"))
        else:
            # Comportamiento normal: solo chunks solicitados + adyacentes
            # Primero agregar los chunks encontrados
            want = set(chunk_ids)
            for chunk_id in chunk_ids:
                if chunk_id in chunks_by_id:
                    m = chunks_by_id[chunk_id]
                    selected.append(m)
                    selected_ids.add(chunk_id)
            
            # Expandir con chunks adyacentes si está habilitado
            if expand_adjacent:
                for chunk_id in chunk_ids:
                    if chunk_id not in chunks_by_id:
                        continue
                    
                    m = chunks_by_id[chunk_id]
                    doc_id_key = m.get("doc_id")
                    chunk_idx = m.get("chunk_index")
                    
                    if doc_id_key is None or chunk_idx is None:
                        continue
                    
                    if doc_id_key not in chunks_by_doc_and_index:
                        continue
                    
                    doc_chunks = chunks_by_doc_and_index[doc_id_key]
                    
                    # Chunk anterior (chunk_index - 1)
                    prev_idx = chunk_idx - 1
                    if prev_idx >= 0 and prev_idx in doc_chunks:
                        prev_chunk = doc_chunks[prev_idx]
                        prev_id = prev_chunk.get("chunk_id")
                        if prev_id and prev_id not in selected_ids:
                            selected.append(prev_chunk)
                            selected_ids.add(prev_id)
                    
                    # Chunk siguiente (chunk_index + 1)
                    next_idx = chunk_idx + 1
                    if next_idx in doc_chunks:
                        next_chunk = doc_chunks[next_idx]
                        next_id = next_chunk.get("chunk_id")
                        if next_id and next_id not in selected_ids:
                            selected.append(next_chunk)
                            selected_ids.add(next_id)
            
            # Ordenar por doc_id y chunk_index para mantener orden lógico
            selected.sort(key=lambda x: (x.get("doc_id", ""), x.get("chunk_index", 0)))

    elif doc_id:
        for m in meta:
            if m.get("doc_id") == doc_id:
                selected.append(m)
                # Si max_chunks es muy grande (>= 9999), obtener todos los chunks
                if max_chunks < 9999 and len(selected) >= max_chunks:
                    break
    else:
        return {"ok": False, "error": "provide chunk_ids or doc_id"}

    if not selected:
        return {"ok": False, "error": "no_chunks_found"}

    blocks = []
    for m in selected:
        header = []
        
        # Metadata genérica (políticas ISO, etc.)
        if m.get("codigo"):
            header.append(f"Código: {m.get('codigo')}")
        if m.get("fecha_emision"):
            header.append(f"Emisión: {m.get('fecha_emision')}")
        if m.get("revision") is not None:
            header.append(f"Rev: {m.get('revision')}")
        if m.get("estatus"):
            header.append(f"Estatus: {m.get('estatus')}")
        
        # Metadata específica para meetings_weekly
        if m.get("meeting_date"):
            header.append(f"Fecha reunión: {m.get('meeting_date')}")
        if m.get("meeting_start") and m.get("meeting_end"):
            header.append(f"Hora: {m.get('meeting_start')} - {m.get('meeting_end')}")
        if m.get("row_key") and "#tema-" in str(m.get("row_key")):
            tema_num = str(m.get("row_key")).split("#tema-")[-1]
            header.append(f"Tema #{tema_num}")
        elif m.get("row_key"):
            header.append(f"Row: {m.get('row_key')}")
        
        # Metadata específica para user_guides
        if m.get("objetivo"):
            header.append(f"Objetivo: {m.get('objetivo')[:100]}")
        if m.get("step_label"):
            header.append(f"Paso: {m.get('step_label')}")
        if m.get("doc_number"):
            header.append(f"Doc #{m.get('doc_number')}")

        title = m.get("catalog_title") or m.get("title")
        section = m.get("section") or ""

        blocks.append({
            "chunk_id": m.get("chunk_id"),
            "doc_id": m.get("doc_id"),
            "title": title,
            "section": section,
            "header": " | ".join(header),
            "text": m.get("text", ""),
            # Metadata adicional para meetings
            "meeting_date": m.get("meeting_date"),
            "row_key": m.get("row_key"),
            "block_kind": m.get("block_kind"),
            # Metadata adicional para user_guides
            "objetivo": m.get("objetivo"),
            "step_label": m.get("step_label"),
            "step_number": m.get("step_number"),
            "doc_number": m.get("doc_number"),
        })

    return {"ok": True, "universe": universe, "blocks": blocks}

