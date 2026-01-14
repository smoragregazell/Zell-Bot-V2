"""
Obtener cotizaciones - Obtiene información completa de cotizaciones del sistema ZELL.
Complementa a search_quotes.py:
- search_quotes.py: Buscar cotizaciones (búsqueda semántica con FAISS)
- get_quotes.py: Obtener información completa de cotizaciones específicas
"""
import os
import json
from typing import List, Dict, Any, Optional

from Tools.search_quotes import _load_meta, _load_index_and_meta


def get_quotes_context(
    chunk_ids: Optional[List[str]] = None,
    i_issue_ids: Optional[List[int]] = None,
    i_quote_ids: Optional[List[int]] = None,
    universe: str = "quotes"
) -> Dict[str, Any]:
    """
    Obtiene la información completa de cotizaciones específicas.
    
    Args:
        chunk_ids: Lista de chunk_ids a obtener (ej: ["quote_1054", "quote_1069"])
        i_issue_ids: Lista de números de ticket (iIssueId) a obtener (ej: [1054, 1069])
        i_quote_ids: Lista de IDs de cotización (iQuoteId) a obtener (ej: [69, 71])
        universe: Nombre del universo (default: "quotes")
    
    Returns:
        Dict con formato:
        {
            "ok": True/False,
            "universe": str,
            "quotes": [
                {
                    "chunk_id": str,
                    "i_issue_id": int,
                    "i_quote_id": int,
                    "v_title": str,
                    "i_units": float,
                    "f_payment_date": str,  # Puede ser null
                    "descriptions": str,    # Puede ser null
                    "header": str,  # Header formateado con metadata
                    "text": str,    # Texto usado para embedding (referencia)
                },
                ...
            ]
        }
    """
    try:
        _, meta = _load_index_and_meta(universe)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}

    selected = []
    selected_ids = set()

    # Crear índices para búsqueda rápida
    chunks_by_id = {m.get("chunk_id"): m for m in meta}
    chunks_by_issue_id = {}
    chunks_by_quote_id = {}
    for m in meta:
        issue_id = m.get("i_issue_id")
        quote_id = m.get("i_quote_id")
        if issue_id is not None:
            chunks_by_issue_id[issue_id] = m
        if quote_id is not None:
            if quote_id not in chunks_by_quote_id:
                chunks_by_quote_id[quote_id] = []
            chunks_by_quote_id[quote_id].append(m)

    # Buscar por chunk_ids
    if chunk_ids:
        for chunk_id in chunk_ids:
            if chunk_id in chunks_by_id and chunk_id not in selected_ids:
                selected.append(chunks_by_id[chunk_id])
                selected_ids.add(chunk_id)

    # Buscar por i_issue_ids
    if i_issue_ids:
        for issue_id in i_issue_ids:
            if issue_id in chunks_by_issue_id:
                chunk = chunks_by_issue_id[issue_id]
                chunk_id = chunk.get("chunk_id")
                if chunk_id and chunk_id not in selected_ids:
                    selected.append(chunk)
                    selected_ids.add(chunk_id)

    # Buscar por i_quote_ids
    if i_quote_ids:
        for quote_id in i_quote_ids:
            if quote_id in chunks_by_quote_id:
                for chunk in chunks_by_quote_id[quote_id]:
                    chunk_id = chunk.get("chunk_id")
                    if chunk_id and chunk_id not in selected_ids:
                        selected.append(chunk)
                        selected_ids.add(chunk_id)

    if not selected:
        return {"ok": False, "error": "no_quotes_found"}

    # Ordenar por i_issue_id
    selected.sort(key=lambda x: x.get("i_issue_id") or 0)

    quotes = []
    for m in selected:
        header = []
        
        # Metadata básica
        if m.get("i_issue_id") is not None:
            header.append(f"Ticket: {m.get('i_issue_id')}")
        if m.get("i_quote_id") is not None:
            header.append(f"Cotizacion: {m.get('i_quote_id')}")
        if m.get("v_title"):
            header.append(f"Titulo: {m.get('v_title')}")
        if m.get("i_units") is not None:
            header.append(f"Unidades: {m.get('i_units')}")
        if m.get("f_payment_date"):
            header.append(f"Fecha Pago: {m.get('f_payment_date')}")

        quotes.append({
            "chunk_id": m.get("chunk_id"),
            "i_issue_id": m.get("i_issue_id"),
            "i_quote_id": m.get("i_quote_id"),
            "v_title": m.get("v_title"),
            "i_units": m.get("i_units"),
            "f_payment_date": m.get("f_payment_date"),
            "descriptions": m.get("descriptions"),
            "header": " | ".join(header),
            "text": m.get("text", ""),  # Texto usado para embedding (referencia)
        })

    return {"ok": True, "universe": universe, "quotes": quotes}

