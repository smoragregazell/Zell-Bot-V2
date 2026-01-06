# Tools/docs_indexer/indexer.py
# Docs indexer: builds FAISS index + jsonl metadata for multiple "universes"
# - Supports .txt, .md, .docx
# - Special parsing for meetings_weekly: respects tables, 1 row = 1 chunk for main minuta table
# - Adds boilerplate filtering + dedupe for meetings
# - Optional catalog enrichment (Data/doc_catalog.json) via code in filename (e.g. M-SGCSI-01 ...)
# - Optional embedding cache per universe to avoid re-embedding unchanged chunks

import os
import json
from typing import List, Dict, Any, Optional, Set

import numpy as np
import faiss
import tiktoken

from .config import DEFAULT_CHUNK_TOKENS, DEFAULT_OVERLAP_TOKENS, SUPPORTED_EXTS
from .utils import (
    file_sha256,
    chunk_text_tokens,
    compute_sections,
    section_for_charpos,
    fingerprint_text
)
from .models import DocChunk
from .catalog import load_catalog, infer_code_from_filename
from .meetings import is_meeting_boilerplate
from .docx import read_document
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


def build_docs_index(
    universe: str,
    input_dir: str,
    out_dir: str = "Data",
    encoding_name: str = "cl100k_base",
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    top_level_only: bool = False,
    max_files: Optional[int] = None,
    catalog_path: Optional[str] = "Data/doc_catalog.json",
) -> Dict[str, Any]:
    """
    Construye índice FAISS (IndexFlatIP) + metadatos JSONL para un universo.
    Soporta: .txt, .md, .docx
    Especial: meetings_weekly docx parsing con tablas.
    """
    os.makedirs(out_dir, exist_ok=True)
    catalog = load_catalog(catalog_path)

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
            "index_path": os.path.join(out_dir, f"docs_{universe}.index"),
            "meta_path": os.path.join(out_dir, f"docs_{universe}_meta.jsonl"),
        }

    # Cargar índice FAISS existente si existe (para actualización incremental)
    idx_path = os.path.join(out_dir, f"docs_{universe}.index")
    meta_path = os.path.join(out_dir, f"docs_{universe}_meta.jsonl")
    existing_index = None
    existing_meta: List[DocChunk] = []
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
    chunks: List[DocChunk] = []
    matched_catalog_docs = 0

    for path in files_to_process:
        title = os.path.basename(path)
        sha = file_sha256(path)
        doc_id = sha[:12]  # estable por contenido

        # Coincidencia de catálogo por código en filename
        codigo = infer_code_from_filename(title)
        cat = catalog.get(codigo) if codigo else None
        if cat:
            matched_catalog_docs += 1

        # Leer documento -> blocks
        plain_text, blocks, doc_meta = read_document(path, universe=universe)
        if not blocks:
            continue

        # Para .txt/.md podemos querer mapeo de headings (opcional)
        sections = compute_sections(plain_text) if plain_text else []

        # Deduplicación + filtrado de boilerplate específicamente para meetings
        filtered_blocks: List[Dict[str, Any]] = []
        seen_fp = set()
        for b in blocks:
            t = (b.get("text") or "").strip()
            if not t:
                continue

            if universe == "meetings_weekly":
                if is_meeting_boilerplate(t, b.get("block_kind"), b.get("table_name")):
                    continue

            fp = fingerprint_text(t)
            if fp in seen_fp:
                continue
            seen_fp.add(fp)

            filtered_blocks.append(b)

        if not filtered_blocks:
            continue

        # Ahora tokenizar por bloque; si el bloque es largo, dividir en sub-chunks
        token_cursor = 0
        chunk_idx = 0
        for b in filtered_blocks:
            b_text = (b.get("text") or "").strip()
            if not b_text:
                continue

            # Mapeo de sección:
            sec = b.get("section")
            if not sec and sections:
                # aproximado: coincidencia de ancla en plain_text
                anchor = b_text[:120]
                found_at = plain_text.find(anchor)
                if found_at >= 0:
                    sec = section_for_charpos(sections, found_at)

            # Dividir bloque largo en chunks de tokens
            skip_chunking = False
            enc = tiktoken.get_encoding(encoding_name)
            
            # Para meetings_weekly: NO fragmentar chunks especiales
            if universe == "meetings_weekly":
                block_kind = b.get("block_kind")
                table_name = b.get("table_name")
                
                # NO fragmentar: meeting completo, headers pequeños
                if block_kind == "meeting_full" or table_name == "meeting_summary":
                    skip_chunking = True
                elif table_name == "meeting_data":
                    token_count = len(enc.encode(b_text))
                    if token_count < 800:  # Headers pequeños no fragmentar
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
                # token_start/end son aproximados dentro del documento (block-local + cursor)
                token_start = token_cursor + t0
                token_end = token_cursor + t1

                cid = f"{doc_id}_{chunk_idx}"
                chunk_idx += 1

                chunks.append(DocChunk(
                    chunk_id=cid,
                    universe=universe,
                    doc_id=doc_id,
                    title=title,
                    source_path=path,
                    sha256=sha,
                    chunk_index=(chunk_idx - 1),
                    section=sec,
                    token_start=token_start,
                    token_end=token_end,
                    text=chunk_txt,

                    block_kind=b.get("block_kind"),
                    table_name=b.get("table_name"),
                    row_key=str(b.get("row_key")) if b.get("row_key") is not None else None,
                    meeting_date=b.get("meeting_date") or doc_meta.get("meeting_date"),
                    meeting_date_raw=b.get("meeting_date_raw") or doc_meta.get("meeting_date_raw"),
                    meeting_start=b.get("meeting_start"),
                    meeting_end=b.get("meeting_end"),

                    codigo=codigo,
                    domain=cat.get("domain") if cat else None,
                    family=cat.get("family") if cat else None,
                    revision=cat.get("revision") if cat else None,
                    estatus=cat.get("estatus") if cat else None,
                    tipo_info=cat.get("tipo_info") if cat else None,
                    alcance_iso=cat.get("alcance_iso") if cat else None,
                    disposicion=cat.get("disposicion") if cat else None,
                    fecha_emision=cat.get("fecha_emision") if cat else None,
                    catalog_title=cat.get("titulo") if cat else None,
                ))

            # Avanzar cursor por longitud completa de tokens del bloque (aprox)
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
    meta_rows: List[DocChunk] = []

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
    # Si hay índice existente, agregar a él; si no, crear uno nuevo
    if existing_index is not None:
        if existing_index.d != dim:
            # Dimensiones no coinciden, crear nuevo índice
            index = faiss.IndexFlatIP(dim)
            # Cargar vectores existentes del índice anterior (no podemos recuperarlos fácilmente)
            # Por ahora, si las dimensiones no coinciden, empezamos de cero
            index.add(mat)
        else:
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
                "doc_id": c.doc_id,
                "title": c.title,
                "source_path": c.source_path,
                "sha256": c.sha256,
                "chunk_index": c.chunk_index,
                "section": c.section,
                "token_start": c.token_start,
                "token_end": c.token_end,
                "text": c.text,

                # block metadata
                "block_kind": c.block_kind,
                "table_name": c.table_name,
                "row_key": c.row_key,
                "meeting_date": c.meeting_date,
                "meeting_date_raw": c.meeting_date_raw,
                "meeting_start": c.meeting_start,
                "meeting_end": c.meeting_end,

                # catalog metadata
                "codigo": c.codigo,
                "domain": c.domain,
                "family": c.family,
                "revision": c.revision,
                "estatus": c.estatus,
                "tipo_info": c.tipo_info,
                "alcance_iso": c.alcance_iso,
                "disposicion": c.disposicion,
                "fecha_emision": c.fecha_emision,
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
    # Para docs únicos, contar los nuevos + los existentes
    new_doc_ids = set([c.doc_id for c in meta_rows])
    if existing_index is not None:
        # Leer todos los doc_ids del meta existente para contar total
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
    
    unique_codes = len(set([c.codigo for c in meta_rows if c.codigo]))

    stats_meetings = {}
    if universe == "meetings_weekly":
        kinds = {}
        tables = {}
        for c in meta_rows:
            kinds[c.block_kind or "none"] = kinds.get(c.block_kind or "none", 0) + 1
            tables[c.table_name or "none"] = tables.get(c.table_name or "none", 0) + 1
        stats_meetings = {"block_kind_counts": kinds, "table_name_counts": tables}

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
        "unique_codes_in_meta": unique_codes,
        "emb_cache_path": get_emb_cache_path(out_dir, universe),
        "file_cache_path": get_file_cache_path(out_dir, universe),
        "incremental_update": existing_index is not None,
        "note": "Para que el catálogo se aplique, el filename idealmente debe contener el código tipo P-SGSI-14 / M-SGCSI-01.",
        **({"meetings_stats": stats_meetings} if stats_meetings else {})
    }

