# Tools/docs_indexer/config.py
# Configuración y constantes para el indexador de documentos

import re

# ----------------------------
# Chunking defaults
# ----------------------------
DEFAULT_CHUNK_TOKENS = 650
DEFAULT_OVERLAP_TOKENS = 120

SUPPORTED_EXTS = (".txt", ".md", ".docx")

# ----------------------------
# Regex patterns
# ----------------------------

# Detect headings (markdown or numeric)
HEADING_RE = re.compile(r"^\s*(#{1,6}\s+.+|(\d+(\.\d+)*)\s+.+)\s*$")

# Code in filename: P-SGSI-14, M-SGCSI-01, etc.
CODE_IN_FILENAME_RE = re.compile(r"([A-Z]{1,4}-[A-Z]{2,6}-\d{2})")

# Meetings: boilerplate / structure
PAGE_MARK_RE = re.compile(r"^\s*P[aá]gina\s+\d+\s+de\s+\d+\s*$", re.IGNORECASE)
MINUTA_HEADER_RE = re.compile(r"Nombre del documento:\s*Minuta de Reuni[oó]n Semanal", re.IGNORECASE)
APPROVALS_RE = re.compile(r"\bELABOR[ÓO]\b|\bAPROB[ÓO]\b|\bREVIS[ÓO]\b", re.IGNORECASE)
REVLOG_HEADER_RE = re.compile(r"^\s*Revisi[oó]n\s*\|\s*Cambio\s*\|\s*Fecha\s*$", re.IGNORECASE)

# Meetings: detect date in filename (YYYY-MM-DD)
DATE_IN_FILENAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Meetings: detect "Fecha: dd/mm/yyyy"
DATE_LINE_RE = re.compile(r"\bFecha\s*:\s*(\d{2}/\d{2}/\d{4})\b", re.IGNORECASE)

# Meetings: row number in pipe format (not strictly necessary, but useful)
ROW_NUM_PIPE_RE = re.compile(r"^\s*(\d{1,3})\s*\|")

