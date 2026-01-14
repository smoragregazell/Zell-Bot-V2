# Tools/etiquetas_indexer/models.py
# Modelos de datos para el indexador de etiquetas

from dataclasses import dataclass
from typing import Optional


@dataclass
class EtiquetaChunk:
    """Representa una etiqueta indexada (cada fila del Excel = 1 chunk)."""
    chunk_id: str  # "etiqueta_{numero}"
    universe: str  # "etiquetas"
    numero: Optional[int]  # Número de etiqueta (NO se vectoriza, solo metadata)
    etiqueta: Optional[str]  # Código de etiqueta [i101: PID]
    descripcion: Optional[str]  # Descripción en español
    desc_tabla: Optional[str]  # Nombre de columna en BD (en inglés)
    cliente_que_la_tiene: Optional[str]  # Cliente que tiene la etiqueta
    tipo_dato: Optional[str]  # Tipo de dato (1 o 2)
    longitud: Optional[int]  # Longitud del campo
    query: Optional[str]  # Query SQL para insertar
    text: str  # Texto combinado para embedding: "[Etiqueta] - Descripcion | Desc Tabla: [Desc Tabla]"

