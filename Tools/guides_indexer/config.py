# Tools/guides_indexer/config.py
# Configuración y constantes para el indexador de guías de usuario

import re

# ----------------------------
# Chunking defaults para guías
# ----------------------------
DEFAULT_CHUNK_TOKENS = 650
DEFAULT_OVERLAP_TOKENS = 120

SUPPORTED_EXTS = (".docx",)

# ----------------------------
# Regex patterns específicos para guías
# ----------------------------

# Título de guía: "(1) Zell - Nombre de la guía"
GUIDE_TITLE_RE = re.compile(r"^\((\d+)\)\s+Zell\s+-\s+(.+)$", re.IGNORECASE)

# Número de paso: "1.", "1)", "Paso 1:", etc.
STEP_NUMBER_RE = re.compile(r"^(?:Paso\s+)?(\d+)[.)]\s*(.+)$", re.IGNORECASE)

# Encabezado/Footer común (filtrar)
HEADER_FOOTER_COMMON = [
    re.compile(r"^Guía\s+de\s+Usuario\s+.*$", re.IGNORECASE),
    re.compile(r"^Página\s+\d+\s+de\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^Zell\s+.*$", re.IGNORECASE),
    re.compile(r"^Sistema\s+Zell\s*$", re.IGNORECASE),
]

# Índice: líneas que empiezan con número o viñeta (ya no se usa directamente)
INDEX_LINE_RE = re.compile(r"^[\d\s.\-•]+\s+.+$")

# Secciones comunes en guías
SECTION_HEADING_RE = re.compile(r"^[A-Z][A-Z\s]{3,}:?\s*$")

