# Tools/docs_indexer/utils.py
# Utilidades generales para el indexador de documentos

import os
import re
import hashlib
from typing import List, Tuple, Optional

import numpy as np
import tiktoken

from .config import (
    DEFAULT_CHUNK_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    HEADING_RE
)


def file_sha256(path: str) -> str:
    """Calcula el hash SHA256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text_file(path: str) -> str:
    """Lee un archivo de texto con detección automática de encoding."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            return f.read()


def fingerprint_text(s: str) -> str:
    """Genera un fingerprint (hash) de un texto normalizado."""
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def to_iso_date_from_ddmmyyyy(mx: str) -> Optional[str]:
    """
    Convierte fecha en formato dd/mm/yyyy a ISO (YYYY-MM-DD).
    Asume formato típico de México para minutas de reunión.
    """
    try:
        d, m, y = mx.strip().split("/")
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        return None


def normalize_vec_1d(v: np.ndarray) -> np.ndarray:
    """Normaliza un vector 1D a longitud unitaria."""
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = np.linalg.norm(v)
    if n == 0:
        return v
    return (v / n).astype(np.float32)


def chunk_text_tokens(
    text: str,
    encoding_name: str = "cl100k_base",
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> List[Tuple[str, int, int]]:
    """
    Divide texto en chunks basados en tokens.
    Returns: lista de (chunk_text, start_token_idx, end_token_idx) dentro del texto dado.
    """
    enc = tiktoken.get_encoding(encoding_name)
    toks = enc.encode(text or "")
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
    Detecta secciones (títulos/encabezados) en el texto.
    Returns: lista de (char_pos, heading_text) para mapeo aproximado.
    """
    sections: List[Tuple[int, str]] = []
    pos = 0
    for line in (text or "").splitlines(True):
        if HEADING_RE.match(line):
            sections.append((pos, line.strip()))
        pos += len(line)
    return sections


def section_for_charpos(sections: List[Tuple[int, str]], charpos: int) -> Optional[str]:
    """Encuentra la sección más reciente que contiene la posición de carácter dada."""
    if not sections:
        return None
    best = None
    for p, h in sections:
        if p <= charpos:
            best = h
        else:
            break
    return best

