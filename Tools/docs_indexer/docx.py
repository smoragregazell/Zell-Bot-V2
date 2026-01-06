# Tools/docs_indexer/docx.py
# Parsing de archivos DOCX (genérico y específico para meetings)

import os
import re
from typing import List, Dict, Any, Tuple, Optional, Iterable

from .config import (
    DATE_IN_FILENAME_RE,
    DATE_LINE_RE,
    PAGE_MARK_RE
)
from .utils import (
    fingerprint_text,
    to_iso_date_from_ddmmyyyy,
    read_text_file
)


def _iter_docx_block_items(doc) -> Iterable[Tuple[str, Any]]:
    """
    Itera párrafos y tablas en orden del documento.
    Yields: ("p", paragraph) o ("t", table).
    """
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.lower()
        if tag.endswith("}p"):
            yield ("p", child)
        elif tag.endswith("}tbl"):
            yield ("t", child)


def _paragraph_from_xml(doc, p_xml) -> Any:
    """Mapea un elemento XML de párrafo a un objeto Paragraph de python-docx."""
    from docx.text.paragraph import Paragraph
    return Paragraph(p_xml, doc)


def _table_from_xml(doc, tbl_xml) -> Any:
    """Mapea un elemento XML de tabla a un objeto Table de python-docx."""
    from docx.table import Table
    return Table(tbl_xml, doc)


def _docx_table_to_matrix(table) -> List[List[str]]:
    """Convierte una tabla de docx a una matriz de strings."""
    rows = []
    for r in table.rows:
        cells = []
        for c in r.cells:
            txt = (c.text or "").strip()
            txt = re.sub(r"\s+", " ", txt)
            cells.append(txt)
        if any(cells):
            rows.append(cells)
    return rows


def _extract_meeting_structured_data(path: str) -> Dict[str, Any]:
    """
    Extrae datos estructurados de una minuta semanal.
    Retorna JSON canónico según especificación.
    """
    try:
        from docx import Document
    except Exception as e:
        raise RuntimeError("Falta python-docx. Instala con: pip install python-docx") from e

    doc = Document(path)
    
    # Inicializar estructura
    result = {
        "doc_type": "meetings_weekly",
        "meeting_meta": {
            "fecha": None,
            "hora_inicio": None,
            "hora_fin": None
        },
        "asistentes": [],
        "temas": [],
        "meeting_text": ""
    }
    
    # Extraer fecha del filename como fallback
    title = os.path.basename(path)
    m = DATE_IN_FILENAME_RE.search(title)
    if m:
        result["meeting_meta"]["fecha"] = m.group(1)
    
    # Variables temporales para construcción
    fecha_raw = None
    hora_inicio = None
    hora_fin = None
    asistentes_data = []
    temas_data = []
    
    # Estados de parsing
    in_asistentes = False
    in_temas = False
    asistentes_header_found = False
    temas_header_found = False
    
    # Procesar elementos del documento
    for kind, xml in _iter_docx_block_items(doc):
        if kind == "p":
            # Ignorar párrafos (solo footers de página)
            p = _paragraph_from_xml(doc, xml)
            txt = (p.text or "").strip()
            
            if PAGE_MARK_RE.match(txt):
                continue
            if "IMAGEN LOGO" in txt.upper():
                continue
            
            # Intentar extraer fecha de párrafos
            if not fecha_raw:
                dm = DATE_LINE_RE.search(txt)
                if dm:
                    fecha_raw = dm.group(1)
                    result["meeting_meta"]["fecha"] = to_iso_date_from_ddmmyyyy(fecha_raw) or fecha_raw
        
        else:
            # Procesar tablas
            t = _table_from_xml(doc, xml)
            rows = _docx_table_to_matrix(t)
            if not rows:
                continue
            
            # Ignorar tablas ISO header
            all_text = " ".join([" ".join(r) for r in rows[:3]]).upper()
            if "CODIGO" in all_text and "F-OPR" in all_text:
                continue
            
            # Ignorar tablas de firmas
            if any(kw in all_text for kw in ["ELABORÓ", "REVISÓ", "APROBÓ"]):
                continue
            
            # Ignorar tabla de revisiones
            if "REVISIÓN" in all_text and "CAMBIO" in all_text:
                continue
            
            # Analizar contenido de la tabla
            for row_idx, row in enumerate(rows):
                if not row:
                    continue
                
                row_text = " ".join(row).upper()
                first_cell = (row[0] or "").strip().upper()
                
                # 1. Buscar datos de reunión (Fecha, Hora Inicio, Hora Fin)
                if "HORA INICIO" in row_text:
                    for i, cell in enumerate(row):
                        cell_upper = (cell or "").upper().strip()
                        if "HORA INICIO" in cell_upper and i + 1 < len(row):
                            hora_inicio = row[i + 1].strip()
                            result["meeting_meta"]["hora_inicio"] = hora_inicio
                        elif "HORA FIN" in cell_upper and i + 1 < len(row):
                            hora_fin = row[i + 1].strip()
                            result["meeting_meta"]["hora_fin"] = hora_fin
                
                # Extraer fecha de filas
                if "FECHA" in row_text and not result["meeting_meta"]["fecha"]:
                    for cell in row:
                        dm = DATE_LINE_RE.search(cell)
                        if dm:
                            fecha_raw = dm.group(1)
                            result["meeting_meta"]["fecha"] = to_iso_date_from_ddmmyyyy(fecha_raw) or fecha_raw
                
                # 2. Detectar tabla de asistentes
                if "NOMBRE COMPLETO" in row_text and "INICIALES" in row_text:
                    in_asistentes = True
                    asistentes_header_found = True
                    continue
                
                # Extraer asistentes
                if in_asistentes and asistentes_header_found:
                    # Verificar si es header de otra sección
                    if "#TEMA" in first_cell or "TEMAS TRATADOS" in row_text:
                        in_asistentes = False
                        # Continuar al procesamiento de temas
                    elif len(row) >= 2:
                        nombre = (row[0] or "").strip()
                        iniciales = (row[1] or "").strip()
                        
                        # Validar que no sea otro header
                        if nombre and iniciales and nombre.upper() not in ["NOMBRE COMPLETO", "NOMBRE"]:
                            asistentes_data.append({
                                "nombre_completo": nombre,
                                "iniciales": iniciales
                            })
                
                # 3. Detectar tabla de Temas Tratados
                if first_cell == "#TEMA" or (first_cell.startswith("#") and "TEMA" in row_text):
                    in_temas = True
                    temas_header_found = True
                    in_asistentes = False
                    continue
                
                # Extraer temas (filas que empiezan con número)
                if in_temas or (temas_header_found and first_cell.isdigit()):
                    # Verificar si es una fila de tema válida
                    if first_cell.isdigit():
                        tema_num = int(first_cell)
                        # Ignorar "00" que suele ser de tabla de revisión
                        if tema_num == 0:
                            continue
                        
                        # Limpiar fila: deduplicar columnas consecutivas idénticas
                        # Word duplica columnas cuando hay celdas combinadas
                        cleaned_row = []
                        
                        for i, cell in enumerate(row):
                            cell_stripped = (cell or "").strip()
                            
                            # Para la primera columna (tema_num), siempre incluir
                            if i == 0:
                                cleaned_row.append(cell_stripped)
                                continue
                            
                            # Para otras columnas, evitar duplicados consecutivos exactos
                            if cell_stripped:
                                # Si es diferente a la anterior, incluir
                                if not cleaned_row or cell_stripped != cleaned_row[-1]:
                                    cleaned_row.append(cell_stripped)
                        
                        # Mapear a las 5 columnas: #Tema | Participante_exp | Situación | Participante_retro | Aprendizajes
                        # Estructura esperada: [tema_num, participante_exp, situacion, participante_retro, aprendizajes]
                        participante_exp = cleaned_row[1] if len(cleaned_row) > 1 else ""
                        situacion = cleaned_row[2] if len(cleaned_row) > 2 else ""
                        participante_retro = ""
                        aprendizajes = ""
                        
                        # Buscar participante_retro y aprendizajes (pueden estar en diferentes posiciones)
                        # Si tenemos suficientes columnas, mapear directamente
                        if len(cleaned_row) >= 5:
                            # Estructura completa
                            participante_retro = cleaned_row[3]
                            aprendizajes = cleaned_row[4]
                        elif len(cleaned_row) == 4:
                            # Puede ser: [tema, participante_exp, situacion, aprendizajes]
                            # o [tema, participante_exp, situacion, participante_retro]
                            # Heurística: si la 4ta columna es corta y tiene iniciales, es participante_retro
                            if len(cleaned_row[3]) < 30 and any(c.isupper() for c in cleaned_row[3][:5]):
                                participante_retro = cleaned_row[3]
                            else:
                                aprendizajes = cleaned_row[3]
                        elif len(cleaned_row) == 3:
                            # Solo tema, participante, situación
                            pass
                        
                        temas_data.append({
                            "tema_num": tema_num,
                            "participante_expuesto": participante_exp,
                            "situacion_problema_tema": situacion,
                            "participante_retro": participante_retro,
                            "aprendizajes_soluciones_retro": aprendizajes
                        })
    
    # Asignar datos extraídos
    result["asistentes"] = asistentes_data
    result["temas"] = temas_data
    
    # Generar meeting_text canónico
    meeting_text_lines = []
    
    # Fecha
    fecha_display = result["meeting_meta"]["fecha"] or fecha_raw or ""
    if fecha_display:
        meeting_text_lines.append(f"FECHA: {fecha_display}")
    
    # Horas
    if hora_inicio:
        meeting_text_lines.append(f"HORA_INICIO: {hora_inicio}")
    if hora_fin:
        meeting_text_lines.append(f"HORA_FIN: {hora_fin}")
    
    # Asistentes
    if asistentes_data:
        meeting_text_lines.append("\nASISTENTES:")
        for asist in asistentes_data:
            meeting_text_lines.append(f"{asist['nombre_completo']} | {asist['iniciales']}")
    
    # Temas
    if temas_data:
        meeting_text_lines.append("\nTEMAS_TRATADOS:")
        meeting_text_lines.append("#Tema | Participante (iniciales) | Situación / Problema / Tema expuesto | Participante (iniciales) | Aprendizajes / Soluciones propuestas / Retroalimentación")
        for tema in temas_data:
            line = f"{tema['tema_num']} | {tema['participante_expuesto']} | {tema['situacion_problema_tema']} | {tema['participante_retro']} | {tema['aprendizajes_soluciones_retro']}"
            meeting_text_lines.append(line)
    
    result["meeting_text"] = "\n".join(meeting_text_lines)
    
    return result


def _docx_blocks_meeting(path: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parsing específico para meetings_weekly según especificación canónica.
    Extrae JSON estructurado y genera chunks: 1 macro + N por temas.
    """
    # Extraer datos estructurados
    structured_data = _extract_meeting_structured_data(path)
    
    meeting_text = structured_data.get("meeting_text", "")
    meeting_meta = structured_data.get("meeting_meta", {})
    temas = structured_data.get("temas", [])
    
    # Metadata del documento
    title = os.path.basename(path)
    meeting_date = meeting_meta.get("fecha")
    meeting_start = meeting_meta.get("hora_inicio")
    meeting_end = meeting_meta.get("hora_fin")
    
    # Construir blocks
    blocks: List[Dict[str, Any]] = []
    plain_lines: List[str] = []
    
    base_meta = {
        "section": "Minuta",
        "meeting_date": meeting_date,
        "meeting_date_raw": meeting_date,
        "meeting_start": meeting_start,
        "meeting_end": meeting_end,
    }
    
    # CHUNK 1: Meeting completo (visión macro) - NO debe fragmentarse
    if meeting_text:
        blocks.append({
            "text": meeting_text,
            "block_kind": "meeting_full",
            "table_name": "meeting_summary",
            "row_key": None,
            "meeting_date": meeting_date,
            "meeting_date_raw": meeting_date,
            "meeting_start": meeting_start,
            "meeting_end": meeting_end,
            **base_meta
        })
        plain_lines.append(meeting_text)
    
    # CHUNKS 2+: Un chunk por cada tema
    for tema in temas:
        tema_text = f"{tema['tema_num']} | {tema['participante_expuesto']} | {tema['situacion_problema_tema']} | {tema['participante_retro']} | {tema['aprendizajes_soluciones_retro']}"
        row_key = f"{meeting_date}#tema-{tema['tema_num']}" if meeting_date else f"tema-{tema['tema_num']}"
        
        blocks.append({
            "text": tema_text,
            "block_kind": "table_row",
            "table_name": "minuta_items",
            "row_key": row_key,
            **base_meta
        })
        plain_lines.append(tema_text)
    
    # Doc metadata
    doc_meta = {
        "meeting_date": meeting_date,
        "meeting_date_raw": meeting_date,
        "meeting_start": meeting_start,
        "meeting_end": meeting_end,
        "structured_data": structured_data  # Guardar JSON completo en metadata
    }
    
    plain_text = "\n".join(plain_lines).strip()
    return plain_text, blocks, doc_meta


def _docx_blocks_generic(path: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parsing genérico de .docx -> blocks (párrafos + tablas).
    Mantiene headings como markdown (#, ##, ###) usando estilos de Word Heading.
    """
    try:
        from docx import Document
    except Exception as e:
        raise RuntimeError("Falta python-docx. Instala con: pip install python-docx") from e

    doc = Document(path)
    blocks: List[Dict[str, Any]] = []
    plain_lines: List[str] = []
    current_section: Optional[str] = None

    seen_fp = set()

    for kind, xml in _iter_docx_block_items(doc):
        if kind == "p":
            p = _paragraph_from_xml(doc, xml)
            txt = (p.text or "").strip()
            if not txt:
                continue

            style = (p.style.name or "").lower() if p.style else ""
            if "heading 1" in style:
                txt_md = f"# {txt}"
                current_section = txt_md
            elif "heading 2" in style:
                txt_md = f"## {txt}"
                current_section = txt_md
            elif "heading 3" in style:
                txt_md = f"### {txt}"
                current_section = txt_md
            else:
                txt_md = txt

            fp = fingerprint_text(txt_md)
            if fp in seen_fp:
                continue
            seen_fp.add(fp)

            blocks.append({
                "text": txt_md,
                "block_kind": "paragraph",
                "table_name": None,
                "row_key": None,
                "section": current_section,
            })
            plain_lines.append(txt_md)

        else:
            t = _table_from_xml(doc, xml)
            rows = _docx_table_to_matrix(t)
            if not rows:
                continue

            text_lines = []
            for r in rows:
                line = " | ".join([c for c in r if c])
                if line:
                    text_lines.append(line)
            text = "\n".join(text_lines).strip()
            if not text:
                continue

            fp = fingerprint_text(text)
            if fp in seen_fp:
                continue
            seen_fp.add(fp)

            blocks.append({
                "text": text,
                "block_kind": "table",
                "table_name": "generic",
                "row_key": None,
                "section": current_section,
            })
            plain_lines.append(text)

    plain_text = "\n".join(plain_lines).strip()
    meta: Dict[str, Any] = {}
    return plain_text, blocks, meta


def read_docx_file(path: str, universe: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Lee un archivo .docx y retorna (plain_text, blocks, doc_meta).
    """
    if universe == "meetings_weekly":
        return _docx_blocks_meeting(path)
    return _docx_blocks_generic(path)


def read_document(path: str, universe: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Lee un documento y retorna (plain_text, blocks, doc_meta).
    Soporta: .txt, .md, .docx
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        txt = read_text_file(path)
        # Tratar como bloque de texto único; headings detectados después
        return (
            (txt or "").strip(),
            [{
                "text": (txt or "").strip(),
                "block_kind": "text",
                "table_name": None,
                "row_key": None,
                "section": None
            }],
            {}
        )
    if ext == ".docx":
        return read_docx_file(path, universe=universe)
    raise ValueError(f"Formato no soportado aún: {ext} ({path})")
