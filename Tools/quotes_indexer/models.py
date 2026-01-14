# Tools/quotes_indexer/models.py
# Modelos de datos para el indexador de cotizaciones

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class QuoteChunk:
    """Representa una cotización indexada (cada fila del Excel = 1 chunk)."""
    chunk_id: str  # "quote_{iIssueId}"
    universe: str  # "quotes"
    i_issue_id: Optional[int]  # Número de ticket (ID principal)
    i_quote_id: Optional[int]  # ID de cotización (metadata)
    v_title: Optional[str]  # Título (metadata + parte del texto vectorizado)
    i_units: Optional[float]  # Unidades (metadata)
    f_payment_date: Optional[str]  # Fecha de pago en formato string (metadata, NULL si no hay)
    descriptions: Optional[str]  # Descripciones (metadata + parte del texto vectorizado)
    text: str  # Texto combinado para embedding: "vTitle + Descriptions" (concatenado)

