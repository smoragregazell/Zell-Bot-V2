# Tools/guides_indexer/guide_parser.py
# Parser específico para guías de usuario del sistema Zell
# Estructura real: Título, INDICE, OBJETIVO, TÉRMINOS Y DEFINICIONES, DESARROLLO

import os
import re
from typing import List, Dict, Any, Tuple, Optional

try:
    from docx import Document
    from docx.text.paragraph import Paragraph
except ImportError:
    raise RuntimeError("Falta python-docx. Instala con: pip install python-docx")

from .config import (
    GUIDE_TITLE_RE,
    STEP_NUMBER_RE,
    HEADER_FOOTER_COMMON,
    SECTION_HEADING_RE,
)


def _is_header_footer(text: str) -> bool:
    """Detecta si un texto es parte de encabezado/footer común."""
    text_clean = text.strip()
    if not text_clean:
        return True
    
    for pattern in HEADER_FOOTER_COMMON:
        if pattern.match(text_clean):
            return True
    
    # Encabezados muy cortos repetitivos
    if len(text_clean) < 5 and text_clean.isupper():
        return True
    
    return False


def _is_section_header(text: str) -> bool:
    """Detecta si un texto es un encabezado de sección (mayúsculas, palabras clave)."""
    text_clean = text.strip()
    if not text_clean:
        return False
    
    # Secciones comunes en guías
    section_keywords = [
        "INDICE", "ÍNDICE", "INDICE",
        "OBJETIVO",
        "TÉRMINOS Y DEFINICIONES", "TERMINOS Y DEFINICIONES",
        "DESARROLLO",
        "CONFIGURACIÓN", "CONFIGURACION",
        "PROCESO",
    ]
    
    # Texto completamente en mayúsculas y es una palabra clave conocida
    if text_clean.isupper() and any(keyword in text_clean for keyword in section_keywords):
        return True
    
    # También detectar por patrón de sección (texto corto en mayúsculas)
    if text_clean.isupper() and 3 <= len(text_clean) <= 50:
        return True
    
    return False


def _has_image(paragraph: Paragraph) -> bool:
    """Detecta si un párrafo contiene una imagen."""
    if not paragraph.runs:
        return False
    for run in paragraph.runs:
        if run._element.xml and 'pic:pic' in run._element.xml:
            return True
    return False


def parse_guide_docx(path: str) -> Dict[str, Any]:
    """
    Parsea una guía de usuario DOCX.
    
    Estructura real observada:
    - Título: primera línea significativa (ej: "Reintentos de domiciliación")
    - INDICE: sección que se filtra
    - OBJETIVO: sección importante
    - TÉRMINOS Y DEFINICIONES: sección opcional
    - DESARROLLO: contenido principal con pasos descriptivos
    
    Returns:
    {
        "title": str,  # Título extraído
        "doc_number": int | None,  # Número del documento (del filename o catálogo)
        "blocks": [
            {
                "text": str,
                "section": str | None,  # "OBJETIVO", "DESARROLLO", etc.
                "step_number": int | None,
                "block_kind": str,  # "title", "section_header", "content"
            },
            ...
        ]
    }
    """
    doc = Document(path)
    
    result = {
        "title": None,
        "doc_number": None,
        "blocks": []
    }
    
    paragraphs = list(doc.paragraphs)
    
    # Estado de parsing
    found_title = False
    current_section = None
    in_index = False
    step_counter = 0
    
    for i, para in enumerate(paragraphs):
        text = (para.text or "").strip()
        
        if not text:
            continue
        
        # Filtrar encabezados/footers comunes
        if _is_header_footer(text):
            continue
        
        # Detectar sección por encabezado en mayúsculas
        if _is_section_header(text):
            section_name = text.upper()
            
            # INDICE se filtra completamente
            if "INDICE" in section_name or "ÍNDICE" in section_name:
                in_index = True
                current_section = None
                continue
            
            # Otras secciones importantes
            if "OBJETIVO" in section_name:
                in_index = False
                current_section = "OBJETIVO"
                continue
            elif "TÉRMINOS" in section_name or "TERMINOS" in section_name:
                in_index = False
                current_section = "TÉRMINOS Y DEFINICIONES"
                continue
            elif "DESARROLLO" in section_name:
                in_index = False
                current_section = "DESARROLLO"
                step_counter = 0  # Resetear contador de pasos
                continue
            else:
                # Otra sección genérica
                in_index = False
                current_section = section_name
                continue
        
        # Si estamos en índice, saltar
        if in_index:
            continue
        
        # Buscar título (primera línea significativa no-header, no-sección)
        if not found_title and not _is_section_header(text):
            # Primero intentar extraer número del filename
            filename = os.path.basename(path)
            filename_no_ext = re.sub(r'\.(docx|doc)$', '', filename, flags=re.IGNORECASE)
            m = GUIDE_TITLE_RE.match(filename_no_ext)
            if m:
                result["doc_number"] = int(m.group(1))
                result["title"] = m.group(2).strip()
            else:
                # Usar el texto del párrafo como título
                result["title"] = text
                # Intentar extraer número del título si tiene formato "(N)"
                m_num = re.match(r"^\((\d+)\)", text)
                if m_num:
                    result["doc_number"] = int(m_num.group(1))
                    # Limpiar título
                    result["title"] = re.sub(r"^\(\d+\)\s*Zell\s*-\s*", "", text, flags=re.IGNORECASE).strip()
            
            found_title = True
            result["blocks"].append({
                "text": result["title"],
                "section": "Título",
                "step_number": None,
                "block_kind": "title"
            })
            continue
        
        # Procesar contenido normal
        # Detectar pasos numerados explícitos (formato: "3.1", "3.2", "1.", "Paso 1", etc.)
        step_num = None
        step_label = None  # Etiqueta completa como "3.1"
        
        # Patrón 1: Numeración con punto y subnumeración (ej: "3.1", "3.2")
        match_substep = re.match(r"^(\d+)\.(\d+)\s+(.+)$", text)
        if match_substep:
            main_num = int(match_substep.group(1))
            sub_num = int(match_substep.group(2))
            step_label = f"{main_num}.{sub_num}"
            step_num = main_num * 100 + sub_num  # 3.1 -> 301, 3.2 -> 302 para ordenar
            text = match_substep.group(3).strip()
        
        # Patrón 2: Numeración simple con punto (ej: "3.", "1.")
        elif re.match(r"^(\d+)\.\s+(.+)$", text):
            match_step = re.match(r"^(\d+)\.\s+(.+)$", text)
            step_num = int(match_step.group(1))
            step_label = str(step_num)
            step_counter = step_num
            text = match_step.group(2).strip()
        
        # Patrón 3: "Paso N" explícito
        elif step_match := STEP_NUMBER_RE.match(text):
            step_num = int(step_match.group(1))
            step_label = f"Paso {step_num}"
            step_counter = step_num
            text = step_match.group(2).strip()
        
        # Patrón 4: En DESARROLLO, detectar pasos implícitos (empezar con verbo imperativo o texto descriptivo)
        elif current_section == "DESARROLLO" and text:
            # Verificar si empieza con verbo imperativo o es texto descriptivo de continuación
            is_step = re.match(r"^(Para|Seleccionar|Marcar|Dar|Ingresar|Crear|Configurar|Una vez|Se mostrará|Se ejecutará|La nueva|El|Se)", text, re.IGNORECASE)
            
            if is_step:
                step_counter += 1
                # Generar numeración tipo "3.1", "3.2" para DESARROLLO (asumiendo que DESARROLLO es sección 3)
                section_num = 3  # DESARROLLO típicamente es la sección 3 después de OBJETIVO y TÉRMINOS
                step_label = f"{section_num}.{step_counter}"
                step_num = section_num * 100 + step_counter
        
        # Construir texto completo con numeración si existe
        full_text = text
        if step_label and step_label not in text:
            # Prepend número de paso si no está ya en el texto
            full_text = f"{step_label}\t{text}"
        
        # Agregar bloque con información de paso
        section_name = current_section
        if step_num:
            if step_label and "." in step_label:
                # Numeración tipo "3.1"
                section_name = f"{current_section} - {step_label}" if current_section else step_label
            else:
                section_name = f"{current_section} - Paso {step_num}" if current_section else f"Paso {step_num}"
        
        result["blocks"].append({
            "text": full_text,  # Texto completo incluyendo numeración
            "section": section_name,
            "step_number": step_num,
            "step_label": step_label,  # Nueva: etiqueta completa del paso (ej: "3.1")
            "block_kind": "content"
        })
    
    # Si no se encontró título, usar nombre del archivo
    if not result["title"]:
        filename = os.path.basename(path)
        filename_no_ext = re.sub(r'\.(docx|doc)$', '', filename, flags=re.IGNORECASE)
        m = GUIDE_TITLE_RE.match(filename_no_ext)
        if m:
            result["doc_number"] = int(m.group(1))
            result["title"] = m.group(2).strip()
        else:
            result["title"] = filename_no_ext
    
    return result


def read_guide_document(path: str, universe: str = "user_guides") -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Lee un documento de guía y retorna texto plano, bloques estructurados y metadata.
    
    Returns:
        (plain_text, blocks, doc_meta)
    """
    parsed = parse_guide_docx(path)
    
    # Construir texto plano concatenando todos los bloques
    plain_text = "\n\n".join([b["text"] for b in parsed["blocks"]])
    
    # Bloques estructurados (igual que el parse)
    blocks = parsed["blocks"]
    
    # Metadata del documento
    doc_meta = {
        "title": parsed["title"],
        "doc_number": parsed["doc_number"],
    }
    
    return plain_text, blocks, doc_meta

