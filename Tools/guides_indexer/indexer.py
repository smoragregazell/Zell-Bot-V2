# Tools/guides_indexer/indexer.py
# Indexador de guías de usuario: construye FAISS index + metadata JSONL para user_guides

import os
import json
from typing import List, Dict, Any, Optional, Set

import numpy as np
import faiss
import tiktoken

from .config import DEFAULT_CHUNK_TOKENS, DEFAULT_OVERLAP_TOKENS, SUPPORTED_EXTS
from .utils import file_sha256, chunk_text_tokens
from .models import GuideChunk
from .catalog import load_guides_catalog, match_guide_to_catalog
from .guide_parser import read_guide_document
from .embeddings import (
    load_emb_cache,
    embed_text_cached,
    get_emb_cache_path
)
from .file_cache import (
    load_file_cache,
    save_file_cache,
    get_unprocessed_files,
    mark_file_processed,
    get_file_cache_path
)


def build_guides_index(
    universe: str = "user_guides",
    input_dir: str = "knowledgebase/user_guides",
    out_dir: str = "Data",
    encoding_name: str = "cl100k_base",
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    top_level_only: bool = False,
    max_files: Optional[int] = None,
    catalog_path: Optional[str] = "Data/guides_catalog.json",
) -> Dict[str, Any]:
    """
    Construye índice FAISS (IndexFlatIP) + metadatos JSONL para guías de usuario.
    Soporta: .docx
    """
    os.makedirs(out_dir, exist_ok=True)
    catalog = load_guides_catalog(catalog_path)

    # Cache de embeddings
    emb_cache = load_emb_cache(out_dir, universe)
    
    # Cache de archivos procesados
    file_cache = load_file_cache(out_dir, universe)

    # 1) Descubrir archivos
    files: List[str] = []
    if top_level_only:
        for fn in os.listdir(input_dir):
            p = os.path.join(input_dir, fn)
            if os.path.isfile(p) and fn.lower().endswith(SUPPORTED_EXTS):
                files.append(p)
    else:
        for root, _, filenames in os.walk(input_dir):
            for fn in filenames:
                if fn.lower().endswith(SUPPORTED_EXTS):
                    files.append(os.path.join(root, fn))

    files.sort()
    if max_files is not None:
        files = files[:max_files]

    if not files:
        return {"ok": False, "error": f"No encontré archivos {SUPPORTED_EXTS} en {input_dir}"}
    
    # Filtrar archivos ya procesados (solo procesar nuevos/modificados)
    files_to_process = get_unprocessed_files(files, file_cache, use_relative_path=True)
    skipped_files = len(files) - len(files_to_process)
    
    if not files_to_process:
        return {
            "ok": True,
            "universe": universe,
            "input_dir": input_dir,
            "files": len(files),
            "skipped": skipped_files,
            "message": "Todos los archivos ya están procesados. No hay cambios.",
            "index_path": os.path.join(out_dir, f"{universe}.index"),
            "meta_path": os.path.join(out_dir, f"{universe}_meta.jsonl"),
        }

    # Cargar índice FAISS existente si existe (para actualización incremental)
    idx_path = os.path.join(out_dir, f"{universe}.index")
    meta_path = os.path.join(out_dir, f"{universe}_meta.jsonl")
    existing_index = None
    existing_meta: List[GuideChunk] = []
    existing_chunk_ids: Set[str] = set()
    
    if os.path.exists(idx_path) and os.path.exists(meta_path):
        try:
            existing_index = faiss.read_index(idx_path)
            # Cargar metadatos existentes para evitar duplicados
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        existing_chunk_ids.add(data.get("chunk_id", ""))
                    except Exception:
                        continue
        except Exception as e:
            # Si hay error cargando el índice existente, empezamos de cero
            existing_index = None
            existing_chunk_ids = set()

    # 2) Crear chunks solo para archivos nuevos/modificados
    chunks: List[GuideChunk] = []
    matched_catalog_docs = 0

    for path in files_to_process:
        title = os.path.basename(path)
        sha = file_sha256(path)
        doc_id = sha[:12]  # estable por contenido

        # Coincidencia de catálogo por título/filename
        cat_item = match_guide_to_catalog(title, catalog)
        if cat_item:
            matched_catalog_docs += 1

        # Leer documento -> blocks
        plain_text, blocks, doc_meta = read_guide_document(path, universe=universe)
        if not blocks:
            continue

        # Tokenizar y crear chunks
        enc = tiktoken.get_encoding(encoding_name)
        token_cursor = 0
        chunk_idx = 0
        
        for b in blocks:
            b_text = (b.get("text") or "").strip()
            if not b_text:
                continue

            section = b.get("section")
            step_number = b.get("step_number")
            block_kind = b.get("block_kind", "content")

            # Dividir bloque largo en chunks de tokens
            # Para pasos numerados, intentar mantener juntos si son pequeños
            skip_chunking = False
            if block_kind == "step" and step_number:
                token_count = len(enc.encode(b_text))
                if token_count < 800:  # Pasos pequeños no fragmentar
                    skip_chunking = True
            
            if skip_chunking:
                # Mantener el bloque como un solo chunk
                token_count = len(enc.encode(b_text))
                sub_chunks = [(b_text, 0, token_count)]
            else:
                sub_chunks = chunk_text_tokens(
                    b_text,
                    encoding_name=encoding_name,
                    chunk_tokens=chunk_tokens,
                    overlap_tokens=overlap_tokens,
                )

            if not sub_chunks:
                continue

            for (chunk_txt, t0, t1) in sub_chunks:
                token_start = token_cursor + t0
                token_end = token_cursor + t1

                cid = f"{doc_id}_{chunk_idx}"
                chunk_idx += 1

                # Extraer metadata del catálogo si existe
                step_label = b.get("step_label")  # Nueva: etiqueta del paso (ej: "3.1")
                chunks.append(GuideChunk(
                    chunk_id=cid,
                    universe=universe,
                    doc_id=doc_id,
                    title=doc_meta.get("title") or title,
                    source_path=path,
                    sha256=sha,
                    chunk_index=(chunk_idx - 1),
                    section=section,
                    step_number=step_number,
                    step_label=step_label,
                    token_start=token_start,
                    token_end=token_end,
                    text=chunk_txt,

                    # Catalog metadata (enriquecido desde Excel)
                    doc_number=cat_item.get("doc_number") if cat_item else doc_meta.get("doc_number"),
                    objetivo=cat_item.get("objetivo") if cat_item else None,
                    referencia_cliente_ticket=cat_item.get("referencia_cliente_ticket") if cat_item else None,
                    fecha_ultimo_cambio=cat_item.get("fecha_ultimo_cambio") if cat_item else None,
                    version=cat_item.get("version") if cat_item else None,
                    cambio_realizado=cat_item.get("cambio_realizado") if cat_item else None,
                    autores=cat_item.get("autores") if cat_item else None,
                    verifico=cat_item.get("verifico") if cat_item else None,
                    asignada_a=cat_item.get("asignada_a") if cat_item else None,
                    fecha_asignacion=cat_item.get("fecha_asignacion") if cat_item else None,
                    fecha_entregado=cat_item.get("fecha_entregado") if cat_item else None,
                    catalog_title=cat_item.get("nombre_completo") if cat_item else None,
                ))

            # Avanzar cursor por longitud completa de tokens del bloque
            token_cursor += sub_chunks[-1][2]

    if not chunks:
        # Si no hay chunks nuevos pero hay archivos procesados, retornar info del índice existente
        if existing_index is not None:
            return {
                "ok": True,
                "universe": universe,
                "input_dir": input_dir,
                "files": len(files),
                "skipped": skipped_files,
                "new_files": 0,
                "message": "No se generaron chunks nuevos de los archivos modificados (pueden estar vacíos o fallar extracción). Índice existente se mantiene.",
                "index_path": idx_path,
                "meta_path": meta_path,
            }
        return {"ok": False, "error": "No se generaron chunks (docs vacíos o extracción falló)"}

    # 3) Embeddings por chunk (con cache)
    vectors: List[np.ndarray] = []
    meta_rows: List[GuideChunk] = []

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
    if existing_index is not None:
        if existing_index.d != dim:
            index = faiss.IndexFlatIP(dim)
            index.add(mat)
        else:
            index = existing_index
            index.add(mat)
    else:
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
                "doc_id": c.doc_id,
                "title": c.title,
                "source_path": c.source_path,
                "sha256": c.sha256,
                "chunk_index": c.chunk_index,
                "section": c.section,
                "step_number": c.step_number,
                "step_label": c.step_label,
                "token_start": c.token_start,
                "token_end": c.token_end,
                "text": c.text,

                # Catalog metadata
                "doc_number": c.doc_number,
                "objetivo": c.objetivo,
                "referencia_cliente_ticket": c.referencia_cliente_ticket,
                "fecha_ultimo_cambio": c.fecha_ultimo_cambio,
                "version": c.version,
                "cambio_realizado": c.cambio_realizado,
                "autores": c.autores,
                "verifico": c.verifico,
                "asignada_a": c.asignada_a,
                "fecha_asignacion": c.fecha_asignacion,
                "fecha_entregado": c.fecha_entregado,
                "catalog_title": c.catalog_title,
            }, ensure_ascii=False) + "\n")

    # Marcar archivos como procesados en el caché
    for path in files_to_process:
        try:
            sha = file_sha256(path)
            mark_file_processed(path, sha, file_cache, use_relative_path=True)
        except Exception:
            pass
    
    # Guardar caché de archivos actualizado
    save_file_cache(out_dir, universe, file_cache)
    
    # Calcular estadísticas
    new_doc_ids = set([c.doc_id for c in meta_rows])
    if existing_index is not None:
        all_doc_ids = new_doc_ids.copy()
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        doc_id = data.get("doc_id")
                        if doc_id:
                            all_doc_ids.add(doc_id)
                    except Exception:
                        continue
        except Exception:
            pass
        unique_docs = len(all_doc_ids)
    else:
        unique_docs = len(new_doc_ids)

    return {
        "ok": True,
        "universe": universe,
        "input_dir": input_dir,
        "files": len(files),
        "files_processed": len(files_to_process),
        "files_skipped": skipped_files,
        "docs": unique_docs,
        "chunks_new": len(meta_rows),
        "chunks_total": index.ntotal if index else len(meta_rows),
        "dim": dim,
        "index_path": idx_path,
        "meta_path": meta_path,
        "catalog_path": catalog_path,
        "catalog_docs_matched_by_filename": matched_catalog_docs,
        "emb_cache_path": get_emb_cache_path(out_dir, universe),
        "file_cache_path": get_file_cache_path(out_dir, universe),
        "incremental_update": existing_index is not None,
        "note": "Para que el catálogo se aplique, el filename debe seguir el formato: (N) Zell - Nombre.docx"
    }

