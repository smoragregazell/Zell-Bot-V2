# Tools/etiquetas_indexer/indexer.py
# Indexador de etiquetas: construye FAISS index + metadata JSONL desde Excel

import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional

import numpy as np
import faiss

from .config import (
    UNIVERSE_NAME,
    DEFAULT_EXCEL_PATH,
    COL_NUMERO,
    COL_ETIQUETA,
    COL_DESCRIPCION,
    COL_CLIENTE,
    COL_DESC_TABLA,
    COL_TIPO_DATO,
    COL_LONGITUD,
    COL_QUERY,
    EXCEL_HEADER_ROW,
)
from .models import EtiquetaChunk
from .embeddings import (
    load_emb_cache,
    embed_text_cached,
    get_emb_cache_path
)


def _build_text_for_embedding(row: pd.Series) -> Optional[str]:
    """
    Construye el texto combinado para embedding.
    Formato: "[Etiqueta] - Descripcion | Desc Tabla: [Desc Tabla]"
    """
    etiqueta = str(row[COL_ETIQUETA]).strip() if pd.notna(row[COL_ETIQUETA]) else ""
    descripcion = str(row[COL_DESCRIPCION]).strip() if pd.notna(row[COL_DESCRIPCION]) else ""
    desc_tabla = str(row[COL_DESC_TABLA]).strip() if pd.notna(row[COL_DESC_TABLA]) else ""
    
    # Validar que al menos tengamos etiqueta o descripción
    if not etiqueta and not descripcion:
        return None
    
    # Construir texto combinado
    parts = []
    if etiqueta:
        parts.append(etiqueta)
    if descripcion:
        parts.append(descripcion)
    
    text = " - ".join(parts) if len(parts) > 1 else parts[0]
    
    # Agregar Desc Tabla si existe
    if desc_tabla:
        text += f" | Desc Tabla: {desc_tabla}"
    
    return text


def build_etiquetas_index(
    excel_path: str = DEFAULT_EXCEL_PATH,
    out_dir: str = "Data",
    universe: str = UNIVERSE_NAME,
) -> Dict[str, Any]:
    """
    Construye índice FAISS (IndexFlatIP) + metadatos JSONL para etiquetas desde Excel.
    
    Args:
        excel_path: Ruta al archivo Excel con las etiquetas
        out_dir: Directorio donde guardar el índice y metadata
        universe: Nombre del universo (default: "etiquetas")
    
    Returns:
        Dict con estadísticas del proceso
    """
    os.makedirs(out_dir, exist_ok=True)
    
    if not os.path.exists(excel_path):
        return {"ok": False, "error": f"No existe el archivo Excel: {excel_path}"}
    
    # Cache de embeddings
    emb_cache = load_emb_cache(out_dir, universe)
    
    # 1) Leer Excel
    try:
        # Leer saltando las primeras filas vacías y usando la fila 7 como header
        df = pd.read_excel(excel_path, header=EXCEL_HEADER_ROW)
        
        # La primera fila después del header tiene los nombres reales de columnas
        if len(df) > 0:
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
    except Exception as e:
        return {"ok": False, "error": f"Error leyendo Excel: {e}"}
    
    # Validar que tenemos las columnas necesarias
    required_cols = [COL_NUMERO, COL_ETIQUETA, COL_DESCRIPCION]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return {"ok": False, "error": f"Faltan columnas en Excel: {missing_cols}"}
    
    # 2) Crear chunks (una etiqueta = un chunk)
    chunks: List[EtiquetaChunk] = []
    
    for idx, row in df.iterrows():
        # Construir texto para embedding
        text = _build_text_for_embedding(row)
        if not text:
            continue  # Saltar filas sin texto válido
        
        # Extraer valores
        numero = None
        if pd.notna(row[COL_NUMERO]):
            try:
                numero = int(float(row[COL_NUMERO]))
            except (ValueError, TypeError):
                pass
        
        chunk_id = f"etiqueta_{numero}" if numero else f"etiqueta_row_{idx}"
        
        chunks.append(EtiquetaChunk(
            chunk_id=chunk_id,
            universe=universe,
            numero=numero,
            etiqueta=str(row[COL_ETIQUETA]).strip() if pd.notna(row[COL_ETIQUETA]) else None,
            descripcion=str(row[COL_DESCRIPCION]).strip() if pd.notna(row[COL_DESCRIPCION]) else None,
            desc_tabla=str(row[COL_DESC_TABLA]).strip() if pd.notna(row[COL_DESC_TABLA]) else None,
            cliente_que_la_tiene=str(row[COL_CLIENTE]).strip() if pd.notna(row[COL_CLIENTE]) else None,
            tipo_dato=str(row[COL_TIPO_DATO]).strip() if pd.notna(row[COL_TIPO_DATO]) else None,
            longitud=int(float(row[COL_LONGITUD])) if pd.notna(row[COL_LONGITUD]) else None,
            query=str(row[COL_QUERY]).strip() if pd.notna(row[COL_QUERY]) else None,
            text=text,
        ))
    
    if not chunks:
        return {"ok": False, "error": "No se generaron chunks válidos del Excel"}
    
    # 3) Embeddings por chunk (con cache)
    vectors: List[np.ndarray] = []
    meta_rows: List[EtiquetaChunk] = []
    
    for c in chunks:
        v = embed_text_cached(
            text=c.text,
            chunk_id=c.chunk_id,
            universe=universe,
            out_dir=out_dir,
            cache=emb_cache
        )
        if v is None:
            continue
        vectors.append(v.astype(np.float32))
        meta_rows.append(c)
    
    if not vectors:
        return {"ok": False, "error": "No se generaron embeddings (revisa OPENAI key/config)"}
    
    mat = np.vstack(vectors).astype(np.float32)
    dim = mat.shape[1]
    
    # 4) Índice FAISS (IP sobre vectores normalizados ~= cosine)
    idx_path = os.path.join(out_dir, f"{universe}.index")
    meta_path = os.path.join(out_dir, f"{universe}_meta.jsonl")
    
    # Cargar índice existente si existe (para actualización incremental)
    existing_index = None
    if os.path.exists(idx_path):
        try:
            existing_index = faiss.read_index(idx_path)
            if existing_index.d != dim:
                # Dimensiones no coinciden, crear nuevo índice
                existing_index = None
        except Exception:
            existing_index = None
    
    if existing_index is not None:
        # Agregar nuevos vectores al índice existente
        index = existing_index
        index.add(mat)
    else:
        # Crear nuevo índice
        index = faiss.IndexFlatIP(dim)
        index.add(mat)
    
    # 5) Persistir
    faiss.write_index(index, idx_path)
    
    # Guardar metadatos: append si hay existentes, write si es nuevo
    mode = "a" if existing_index is not None and os.path.exists(meta_path) else "w"
    with open(meta_path, mode, encoding="utf-8") as f:
        for c in meta_rows:
            f.write(json.dumps({
                "chunk_id": c.chunk_id,
                "universe": c.universe,
                "numero": c.numero,
                "etiqueta": c.etiqueta,
                "descripcion": c.descripcion,
                "desc_tabla": c.desc_tabla,
                "cliente_que_la_tiene": c.cliente_que_la_tiene,
                "tipo_dato": c.tipo_dato,
                "longitud": c.longitud,
                "query": c.query,
                "text": c.text,  # Texto usado para embedding (para referencia)
            }, ensure_ascii=False) + "\n")
    
    # Estadísticas
    unique_numeros = len(set([c.numero for c in meta_rows if c.numero is not None]))
    
    return {
        "ok": True,
        "universe": universe,
        "excel_path": excel_path,
        "chunks_total": len(meta_rows),
        "chunks_indexed": index.ntotal if index else len(meta_rows),
        "dim": dim,
        "index_path": idx_path,
        "meta_path": meta_path,
        "emb_cache_path": get_emb_cache_path(out_dir, universe),
        "unique_etiquetas": unique_numeros,
        "incremental_update": existing_index is not None,
    }

