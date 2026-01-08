# Tools/guides_indexer/models.py
# Modelos de datos para el indexador de guías

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class GuideChunk:
    """Representa un chunk (fragmento) de una guía de usuario indexada."""
    chunk_id: str
    universe: str  # Siempre "user_guides"
    doc_id: str
    title: str
    source_path: str
    sha256: str
    chunk_index: int
    section: Optional[str]  # Sección del documento (ej: "Paso 1", "Configuración")
    step_number: Optional[int]  # Número de paso si aplica (para ordenamiento)
    token_start: int
    token_end: int
    text: str
    
    # Campos opcionales con valores por defecto (deben ir al final)
    step_label: Optional[str] = None  # Etiqueta completa del paso (ej: "3.1", "3.2", "Paso 1")
    doc_number: Optional[int] = None  # Número del documento desde catálogo
    objetivo: Optional[str] = None  # OBJETIVO (muy importante)
    referencia_cliente_ticket: Optional[str] = None
    fecha_ultimo_cambio: Optional[str] = None  # YYYY-MM-DD
    version: Optional[str] = None
    cambio_realizado: Optional[str] = None
    autores: Optional[str] = None
    verifico: Optional[str] = None
    asignada_a: Optional[str] = None
    fecha_asignacion: Optional[str] = None
    fecha_entregado: Optional[str] = None
    catalog_title: Optional[str] = None  # Nombre completo del catálogo

