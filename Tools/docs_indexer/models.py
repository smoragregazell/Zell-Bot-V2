# Tools/docs_indexer/models.py
# Modelos de datos para el indexador de documentos

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class DocChunk:
    """Representa un chunk (fragmento) de un documento indexado."""
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

    # Extra block metadata
    block_kind: Optional[str] = None
    table_name: Optional[str] = None
    row_key: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_date_raw: Optional[str] = None
    meeting_start: Optional[str] = None
    meeting_end: Optional[str] = None

    # Catalog metadata (optional)
    codigo: Optional[str] = None
    domain: Optional[str] = None
    family: Optional[str] = None
    revision: Optional[Any] = None
    estatus: Optional[str] = None
    tipo_info: Optional[str] = None
    alcance_iso: Optional[str] = None
    disposicion: Optional[str] = None
    fecha_emision: Optional[str] = None  # YYYY-MM-DD
    catalog_title: Optional[str] = None  # official title from Excel

