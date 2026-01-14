# Tools/quotes_indexer/indexer.py
# Indexador de cotizaciones: construye FAISS index + metadata JSONL desde Excel

import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional

import numpy as np
import faiss

from .config import (
    UNIVERSE_NAME,
    DEFAULT_EXCEL_PATH,
    COL_ISSUE_ID,
    COL_QUOTE_ID,
    COL_TITLE,
    COL_UNITS,
    COL_PAYMENT_DATE,
    COL_DESCRIPTIONS,
    EXCEL_HEADER_ROW,
)
from .models import QuoteChunk
from .embeddings import (
    load_emb_cache,
    embed_text_cached,
    get_emb_cache_path
)


def _build_text_for_embedding(row: pd.Series) -> Optional[str]:
    """
    Construye el texto combinado para embedding.
    Formato: "vTitle + Descriptions" (solo concatena Descriptions si no es NULL)
    """
    v_title = str(row[COL_TITLE]).strip() if pd.notna(row[COL_TITLE]) else ""
    descriptions = str(row[COL_DESCRIPTIONS]).strip() if pd.notna(row[COL_DESCRIPTIONS]) else ""
    
    # Validar que al menos tengamos título o descripciones
    if not v_title and not descriptions:
        return None
    
    # Construir texto: solo concatena Descriptions si existe (no es NULL)
    parts = []
    if v_title:
        parts.append(v_title)
    if descriptions:  # Solo se agrega si Descriptions no es NULL/vacío
        parts.append(descriptions)
    
    text = " ".join(parts)
    
    return text if text.strip() else None


def build_quotes_index(
    excel_path: str = DEFAULT_EXCEL_PATH,
    out_dir: str = "Data",
    universe: str = UNIVERSE_NAME,
) -> Dict[str, Any]:
    """
    Construye índice FAISS (IndexFlatIP) + metadatos JSONL para cotizaciones desde Excel.
    
    Args:
        excel_path: Ruta al archivo Excel con las cotizaciones
        out_dir: Directorio donde guardar el índice y metadata
        universe: Nombre del universo (default: "quotes")
    
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
        df = pd.read_excel(excel_path, header=EXCEL_HEADER_ROW)
    except Exception as e:
        return {"ok": False, "error": f"Error leyendo Excel: {e}"}
    
    # Validar que tenemos las columnas necesarias
    required_cols = [COL_ISSUE_ID, COL_TITLE, COL_DESCRIPTIONS]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return {"ok": False, "error": f"Faltan columnas en Excel: {missing_cols}"}
    
    # 2) Crear chunks (una cotización = un chunk)
    chunks: List[QuoteChunk] = []
    
    for idx, row in df.iterrows():
        # Construir texto para embedding
        text = _build_text_for_embedding(row)
        if not text:
            continue  # Saltar filas sin texto válido
        
        # Extraer valores
        i_issue_id = None
        if pd.notna(row[COL_ISSUE_ID]):
            try:
                i_issue_id = int(float(row[COL_ISSUE_ID]))
            except (ValueError, TypeError):
                pass
        
        chunk_id = f"quote_{i_issue_id}" if i_issue_id else f"quote_row_{idx}"
        
        # Extraer iQuoteId
        i_quote_id = None
        if pd.notna(row[COL_QUOTE_ID]):
            try:
                i_quote_id = int(float(row[COL_QUOTE_ID]))
            except (ValueError, TypeError):
                pass
        
        # Extraer iUnits
        i_units = None
        if pd.notna(row[COL_UNITS]):
            try:
                i_units = float(row[COL_UNITS])
            except (ValueError, TypeError):
                pass
        
        # Extraer fPaymentDate (manejar NULL)
        f_payment_date = None
        if pd.notna(row[COL_PAYMENT_DATE]):
            # Convertir fecha a string en formato ISO
            try:
                if isinstance(row[COL_PAYMENT_DATE], pd.Timestamp):
                    f_payment_date = row[COL_PAYMENT_DATE].strftime("%Y-%m-%d")
                elif isinstance(row[COL_PAYMENT_DATE], str):
                    f_payment_date = row[COL_PAYMENT_DATE]
                else:
                    # Intentar parsear como datetime
                    f_payment_date = str(row[COL_PAYMENT_DATE])
            except Exception:
                f_payment_date = str(row[COL_PAYMENT_DATE]) if pd.notna(row[COL_PAYMENT_DATE]) else None
        
        # Extraer vTitle y Descriptions para metadata
        v_title = str(row[COL_TITLE]).strip() if pd.notna(row[COL_TITLE]) else None
        descriptions = str(row[COL_DESCRIPTIONS]).strip() if pd.notna(row[COL_DESCRIPTIONS]) else None
        
        chunks.append(QuoteChunk(
            chunk_id=chunk_id,
            universe=universe,
            i_issue_id=i_issue_id,
            i_quote_id=i_quote_id,
            v_title=v_title,
            i_units=i_units,
            f_payment_date=f_payment_date,
            descriptions=descriptions,
            text=text,
        ))
    
    if not chunks:
        return {"ok": False, "error": "No se generaron chunks válidos del Excel"}
    
    # 3) Embeddings por chunk (con cache)
    vectors: List[np.ndarray] = []
    meta_rows: List[QuoteChunk] = []
    
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
                "i_issue_id": c.i_issue_id,
                "i_quote_id": c.i_quote_id,
                "v_title": c.v_title,
                "i_units": c.i_units,
                "f_payment_date": c.f_payment_date,
                "descriptions": c.descriptions,
                "text": c.text,  # Texto usado para embedding (para referencia)
            }, ensure_ascii=False) + "\n")
    
    # Estadísticas
    unique_quotes = len(set([c.i_issue_id for c in meta_rows if c.i_issue_id is not None]))
    
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
        "unique_quotes": unique_quotes,
        "incremental_update": existing_index is not None,
    }

