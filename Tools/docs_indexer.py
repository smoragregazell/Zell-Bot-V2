# Tools/docs_indexer.py
import os
import re
import json
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import faiss
import tiktoken

# Reusa tu función existente (la que ya usas para tickets)
from Tools.semantic_tool import generate_openai_embedding

# ----------------------------
# Config
# ----------------------------
DEFAULT_CHUNK_TOKENS = 650
DEFAULT_OVERLAP_TOKENS = 120

# Detecta headings tipo Markdown o numeración tipo "3.2 Algo"
HEADING_RE = re.compile(
    r"^\s*(#{1,6}\s+.+|(\d+(\.\d+)*)\s+.+)\s*$"
)

SUPPORTED_EXTS = (".txt", ".md", ".docx")

# Código en filename: P-SGSI-14, PO-RH-01, etc.
CODE_IN_FILENAME_RE = re.compile(r"([A-Z]{1,4}-[A-Z]{2,6}-\d{2})")


# ----------------------------
# Utils
# ----------------------------
def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            return f.read()


def read_docx_file(path: str) -> str:
    """
    Convierte .docx a texto y preserva headings como markdown (#, ##, ###)
    usando styles Heading 1/2/3 del Word.

    Nota: Por ahora NO parsea tablas; lo haremos después.
    """
    try:
        from docx import Document
    except Exception as e:
        raise RuntimeError(
            "Falta dependencia python-docx. Instala con: pip install python-docx"
        ) from e

    doc = Document(path)
    lines: List[str] = []

    for p in doc.paragraphs:
        txt = (p.text or "").strip()
        if not txt:
            continue

        style = (p.style.name or "").lower() if p.style else ""

        # Mapea headings de Word a markdown
        if "heading 1" in style:
            lines.append(f"# {txt}")
        elif "heading 2" in style:
            lines.append(f"## {txt}")
        elif "heading 3" in style:
            lines.append(f"### {txt}")
        else:
            lines.append(txt)

    return "\n".join(lines).strip()


def read_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        return read_text_file(path)
    if ext == ".docx":
        return read_docx_file(path)
    raise ValueError(f"Formato no soportado aún: {ext} ({path})")


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def chunk_text_tokens(
    text: str,
    encoding_name: str = "cl100k_base",
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> List[Tuple[str, int, int]]:
    """
    Devuelve lista de (chunk_text, start_token_idx, end_token_idx)
    """
    enc = tiktoken.get_encoding(encoding_name)
    toks = enc.encode(text)
    chunks: List[Tuple[str, int, int]] = []

    i = 0
    n = len(toks)

    while i < n:
        j = min(i + chunk_tokens, n)
        chunk = enc.decode(toks[i:j]).strip()
        if chunk:
            chunks.append((chunk, i, j))
        if j == n:
            break
        i = max(0, j - overlap_tokens)

    return chunks


def compute_sections(text: str) -> List[Tuple[int, str]]:
    """
    Devuelve lista de (char_pos, heading_text) detectados para mapear chunks a sección.
    """
    sections: List[Tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(True):
        if HEADING_RE.match(line):
            sections.append((pos, line.strip()))
        pos += len(line)
    return sections


def section_for_charpos(sections: List[Tuple[int, str]], charpos: int) -> Optional[str]:
    if not sections:
        return None
    best = None
    for p, h in sections:
        if p <= charpos:
            best = h
        else:
            break
    return best


def load_catalog(catalog_path: Optional[str]) -> Dict[str, Any]:
    """
    Espera un JSON generado por doc_catalog_builder:
    {
      "generated_at": "...",
      "count": 105,
      "items": { "P-SGSI-14": {...}, ... }
    }
    """
    if not catalog_path:
        return {}
    if not os.path.exists(catalog_path):
        return {}
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("items", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def infer_code_from_filename(filename: str) -> Optional[str]:
    m = CODE_IN_FILENAME_RE.search((filename or "").upper())
    return m.group(1) if m else None


# ----------------------------
# Data model
# ----------------------------
@dataclass
class DocChunk:
    chunk_id: str
    universe: str
    doc_id: str
    title: str
    source_path: str
    sha256: str
    chunk_index: int
    section: Optional[str]
    token_start: int
    token_end: int
    text: str

    # Catalog metadata (opcional)
    codigo: Optional[str] = None
    domain: Optional[str] = None
    family: Optional[str] = None
    revision: Optional[Any] = None
    estatus: Optional[str] = None
    tipo_info: Optional[str] = None
    alcance_iso: Optional[str] = None
    disposicion: Optional[str] = None
    fecha_emision: Optional[str] = None  # YYYY-MM-DD
    catalog_title: Optional[str] = None  # Título oficial desde el Excel


# ----------------------------
# Main build
# ----------------------------
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
    Construye índice FAISS (IndexFlatIP) + metadata (jsonl) para un universo.
    Soporta: .txt, .md, .docx
    """
    os.makedirs(out_dir, exist_ok=True)
    catalog = load_catalog(catalog_path)

    # 1) Descubre archivos
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

    # 2) Chunking + metadata por chunk
    chunks: List[DocChunk] = []
    matched_catalog_docs = 0

    for path in files:
        raw_text = read_document(path)
        text = (raw_text or "").strip()
        if not text:
            continue

        sha = file_sha256(path)
        title = os.path.basename(path)

        # doc_id por hash (si el contenido cambia, doc_id cambia; simple y robusto)
        doc_id = sha[:12]

        # Catalog match (por código en filename)
        codigo = infer_code_from_filename(title)
        cat = catalog.get(codigo) if codigo else None
        if cat:
            matched_catalog_docs += 1

        sections = compute_sections(text)
        token_chunks = chunk_text_tokens(
            text,
            encoding_name=encoding_name,
            chunk_tokens=chunk_tokens,
            overlap_tokens=overlap_tokens,
        )

        # Map aproximado a sección: buscamos un “ancla” del chunk en el texto
        cursor = 0
        for idx, (chunk_txt, t0, t1) in enumerate(token_chunks):
            anchor = chunk_txt[:140]
            found_at = text.find(anchor, cursor)
            if found_at == -1:
                # fallback: intenta buscar desde inicio
                found_at = text.find(anchor)
                if found_at == -1:
                    found_at = cursor
            cursor = max(cursor, found_at)

            sec = section_for_charpos(sections, found_at)

            chunk_id = f"{doc_id}_{idx}"
            chunks.append(
                DocChunk(
                    chunk_id=chunk_id,
                    universe=universe,
                    doc_id=doc_id,
                    title=title,
                    source_path=path,
                    sha256=sha,
                    chunk_index=idx,
                    section=sec,
                    token_start=t0,
                    token_end=t1,
                    text=chunk_txt,

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
                )
            )

    if not chunks:
        return {"ok": False, "error": "No se generaron chunks (docs vacíos o extracción falló)"}

    # 3) Embeddings (por chunk)
    vectors: List[np.ndarray] = []
    meta_rows: List[DocChunk] = []

    for c in chunks:
        vec = generate_openai_embedding(
            c.text,
            conversation_id=f"index_docs:{universe}",
            interaction_id=None
        )
        if vec is None:
            continue
        v = normalize(np.array(vec, dtype=np.float32))
        vectors.append(v)
        meta_rows.append(c)

    if not vectors:
        return {"ok": False, "error": "No se generaron embeddings (revisa OPENAI key/config)"}

    mat = np.vstack(vectors).astype(np.float32)
    dim = mat.shape[1]

    # 4) FAISS index (cosine-like con IP + vectores normalizados)
    index = faiss.IndexFlatIP(dim)
    index.add(mat)

    # 5) Persistencia
    idx_path = os.path.join(out_dir, f"docs_{universe}.index")
    meta_path = os.path.join(out_dir, f"docs_{universe}_meta.jsonl")

    faiss.write_index(index, idx_path)

    with open(meta_path, "w", encoding="utf-8") as f:
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

    # stats
    unique_docs = len(set([c.doc_id for c in meta_rows]))
    unique_codes = len(set([c.codigo for c in meta_rows if c.codigo]))

    return {
        "ok": True,
        "universe": universe,
        "input_dir": input_dir,
        "files": len(files),
        "docs": unique_docs,
        "chunks": len(meta_rows),
        "dim": dim,
        "index_path": idx_path,
        "meta_path": meta_path,
        "catalog_path": catalog_path,
        "catalog_docs_matched_by_filename": matched_catalog_docs,
        "unique_codes_in_meta": unique_codes,
        "note": "Para que el catálogo se aplique, el filename idealmente debe contener el código tipo P-SGSI-14.",
    }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--universe", required=True)
    p.add_argument("--input_dir", required=True)
    p.add_argument("--out_dir", default="Data")
    p.add_argument("--chunk_tokens", type=int, default=DEFAULT_CHUNK_TOKENS)
    p.add_argument("--overlap_tokens", type=int, default=DEFAULT_OVERLAP_TOKENS)
    p.add_argument("--encoding", default="cl100k_base")
    p.add_argument("--top_level_only", action="store_true")
    p.add_argument("--max_files", type=int, default=None)
    p.add_argument("--catalog", default="Data/doc_catalog.json")
    args = p.parse_args()

    res = build_docs_index(
        universe=args.universe,
        input_dir=args.input_dir,
        out_dir=args.out_dir,
        encoding_name=args.encoding,
        chunk_tokens=args.chunk_tokens,
        overlap_tokens=args.overlap_tokens,
        top_level_only=args.top_level_only,
        max_files=args.max_files,
        catalog_path=args.catalog,
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))
