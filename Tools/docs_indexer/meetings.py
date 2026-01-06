# Tools/docs_indexer/meetings.py
# Lógica específica para procesamiento de minutas de reunión

from typing import Optional

from .config import (
    PAGE_MARK_RE,
    MINUTA_HEADER_RE,
    APPROVALS_RE,
    REVLOG_HEADER_RE
)


def is_meeting_boilerplate(
    text: str,
    block_kind: Optional[str] = None,
    table_name: Optional[str] = None
) -> bool:
    """
    Determina si un bloque de texto es boilerplate de minutas (páginas, headers, footers, etc.).
    NO filtrar chunks importantes como meeting_full.
    """
    t = (text or "").strip()
    if not t:
        return True

    # NO filtrar chunks importantes de meetings
    if block_kind == "meeting_full" or table_name == "meeting_summary":
        return False
    
    if block_kind in ("page_marker", "meeting_footer"):
        return True

    if PAGE_MARK_RE.match(t):
        return True

    if APPROVALS_RE.search(t) and ("ELABOR" in t.upper() or "APROB" in t.upper() or "REVIS" in t.upper()):
        return True

    if MINUTA_HEADER_RE.search(t):
        return True

    if REVLOG_HEADER_RE.match(t):
        return True

    return False

