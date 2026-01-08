# Tools/guides_indexer/catalog.py
# Funciones relacionadas con el catálogo de guías de usuario

import os
import json
import re
from typing import Dict, Any, Optional

from Tools.guides_catalog_builder import extract_number_from_title


def load_guides_catalog(catalog_path: Optional[str]) -> Dict[str, Any]:
    """
    Carga el catálogo de guías desde JSON.
    Espera JSON producido por guides_catalog_builder:
    {
      "generated_at": "...",
      "count": 200,
      "items": { "1": {...}, "2": {...}, ... }
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


def match_guide_to_catalog(filename: str, catalog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Encuentra entrada del catálogo que coincida con el nombre del archivo.
    Busca por número de documento (prioridad) o por nombre parcial.
    
    Args:
        filename: Nombre del archivo (ej: "(1) Zell - Reintentos.docx" o ruta completa)
        catalog: Diccionario del catálogo (items)
    
    Returns:
        Item del catálogo o None si no se encuentra
    """
    # Extraer nombre base del archivo (sin extensión y sin ruta)
    base_name = os.path.basename(filename)
    base_name = re.sub(r'\.(docx|doc)$', '', base_name, flags=re.IGNORECASE)
    
    # Método 1: Buscar por número extraído del filename (más preciso)
    doc_number, clean_name = extract_number_from_title(base_name)
    
    if doc_number is not None:
        # Buscar en catálogo por número (la clave puede ser string o número)
        for key, item in catalog.items():
            item_doc_number = item.get("doc_number")
            # Comparar con número del catálogo o con la clave
            if item_doc_number == doc_number:
                return item
            try:
                if int(key) == doc_number:
                    return item
            except (ValueError, TypeError):
                pass
    
    # Método 2: Buscar por coincidencia parcial del nombre
    # Normalizar nombres para comparación
    base_name_clean = clean_name.lower() if clean_name else base_name.lower()
    # Remover caracteres especiales y normalizar espacios
    base_name_normalized = re.sub(r'[^\w\s]', '', base_name_clean)
    base_name_normalized = re.sub(r'\s+', ' ', base_name_normalized).strip()
    
    best_match = None
    best_score = 0
    
    for item in catalog.values():
        nombre_completo = (item.get("nombre_completo") or "").lower()
        nombre = (item.get("nombre") or "").lower()
        
        # Normalizar nombres del catálogo
        nombre_completo_norm = re.sub(r'[^\w\s]', '', nombre_completo)
        nombre_completo_norm = re.sub(r'\s+', ' ', nombre_completo_norm).strip()
        nombre_norm = re.sub(r'[^\w\s]', '', nombre)
        nombre_norm = re.sub(r'\s+', ' ', nombre_norm).strip()
        
        # Calcular score de coincidencia
        score = 0
        
        # Coincidencia exacta o parcial
        if nombre_norm and nombre_norm in base_name_normalized:
            score = len(nombre_norm) / max(len(base_name_normalized), 1)
        elif base_name_normalized and base_name_normalized in nombre_norm:
            score = len(base_name_normalized) / max(len(nombre_norm), 1)
        elif nombre_completo_norm and nombre_completo_norm in base_name_normalized:
            score = len(nombre_completo_norm) / max(len(base_name_normalized), 1)
        elif base_name_normalized and base_name_normalized in nombre_completo_norm:
            score = len(base_name_normalized) / max(len(nombre_completo_norm), 1)
        
        # Palabras comunes
        base_words = set(base_name_normalized.split())
        cat_words = set((nombre_norm + " " + nombre_completo_norm).split())
        common_words = base_words & cat_words
        if common_words and len(base_words) > 0:
            word_score = len(common_words) / len(base_words)
            score = max(score, word_score)
        
        if score > best_score:
            best_score = score
            best_match = item
    
    # Retornar si el score es razonable (al menos 50% de coincidencia)
    if best_match and best_score >= 0.5:
        return best_match
    
    return None

