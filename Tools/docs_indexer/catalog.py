# Tools/docs_indexer/catalog.py
# Funciones relacionadas con el catálogo de documentos

import os
import json
from typing import Dict, Any, Optional

from .config import CODE_IN_FILENAME_RE


def load_catalog(catalog_path: Optional[str]) -> Dict[str, Any]:
    """
    Carga el catálogo de documentos desde JSON.
    Espera JSON producido por doc_catalog_builder:
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
    """Extrae el código del documento (ej: P-SGSI-14, M-SGCSI-01) del nombre del archivo."""
    m = CODE_IN_FILENAME_RE.search((filename or "").upper())
    return m.group(1) if m else None

