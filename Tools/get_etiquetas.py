"""
Obtener etiquetas - Obtiene información completa de etiquetas del sistema ZELL.
Complementa a search_etiquetas.py:
- search_etiquetas.py: Buscar etiquetas (búsqueda semántica con FAISS)
- get_etiquetas.py: Obtener información completa de etiquetas específicas
"""
import os
import json
from typing import List, Dict, Any, Optional

from Tools.search_etiquetas import _load_meta, _load_index_and_meta


def get_etiqueta_context(
    chunk_ids: Optional[List[str]] = None,
    numeros: Optional[List[int]] = None,
    universe: str = "etiquetas"
) -> Dict[str, Any]:
    """
    Obtiene la información completa de etiquetas específicas.
    
    Args:
        chunk_ids: Lista de chunk_ids a obtener (ej: ["etiqueta_101", "etiqueta_102"])
        numeros: Lista de números de etiqueta a obtener (ej: [101, 102])
        universe: Nombre del universo (default: "etiquetas")
    
    Returns:
        Dict con formato:
        {
            "ok": True/False,
            "universe": str,
            "etiquetas": [
                {
                    "chunk_id": str,
                    "numero": int,
                    "etiqueta": str,
                    "descripcion": str,
                    "desc_tabla": str,
                    "cliente_que_la_tiene": str (opcional),
                    "tipo_dato": str (opcional),
                    "longitud": int (opcional),
                    "query": str (opcional),
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
    chunks_by_numero = {}
    for m in meta:
        numero = m.get("numero")
        if numero is not None:
            chunks_by_numero[numero] = m

    # Buscar por chunk_ids
    if chunk_ids:
        for chunk_id in chunk_ids:
            if chunk_id in chunks_by_id and chunk_id not in selected_ids:
                selected.append(chunks_by_id[chunk_id])
                selected_ids.add(chunk_id)

    # Buscar por números
    if numeros:
        for numero in numeros:
            if numero in chunks_by_numero:
                chunk = chunks_by_numero[numero]
                chunk_id = chunk.get("chunk_id")
                if chunk_id and chunk_id not in selected_ids:
                    selected.append(chunk)
                    selected_ids.add(chunk_id)

    if not selected:
        return {"ok": False, "error": "no_etiquetas_found"}

    # Ordenar por número de etiqueta
    selected.sort(key=lambda x: x.get("numero") or 0)

    etiquetas = []
    for m in selected:
        header = []
        
        # Metadata básica
        if m.get("numero") is not None:
            header.append(f"Número: {m.get('numero')}")
        if m.get("etiqueta"):
            header.append(f"Etiqueta: {m.get('etiqueta')}")
        if m.get("desc_tabla"):
            header.append(f"Columna BD: {m.get('desc_tabla')}")
        if m.get("tipo_dato"):
            header.append(f"Tipo: {m.get('tipo_dato')}")
        if m.get("longitud") is not None:
            header.append(f"Longitud: {m.get('longitud')}")
        if m.get("cliente_que_la_tiene"):
            header.append(f"Cliente: {m.get('cliente_que_la_tiene')}")

        etiquetas.append({
            "chunk_id": m.get("chunk_id"),
            "numero": m.get("numero"),
            "etiqueta": m.get("etiqueta"),
            "descripcion": m.get("descripcion"),
            "desc_tabla": m.get("desc_tabla"),
            "cliente_que_la_tiene": m.get("cliente_que_la_tiene"),
            "tipo_dato": m.get("tipo_dato"),
            "longitud": m.get("longitud"),
            "query": m.get("query"),
            "header": " | ".join(header),
            "text": m.get("text", ""),  # Texto usado para embedding (referencia)
        })

    return {"ok": True, "universe": universe, "etiquetas": etiquetas}

