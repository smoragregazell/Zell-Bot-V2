from typing import Optional, Literal, List
from pydantic import BaseModel

class ToolResponse(BaseModel):
    classification: Literal[
        "Consulta de Tickets",
        "Búsqueda de Query",
        "ISO",
        "Pregunta Respondida",
        "Búsqueda Semántica",
        "Pregunta Continuada",
        "Comparar ticket",    
        "No Relacionado",
        "Clasificación Incierta",
        "Error"
    ]

    response: str
    error: Optional[str] = None

    # Campos opcionales útiles para herramientas específicas
    ticket_ids: Optional[List[str]] = None
    etiquetas: Optional[List[str]] = None
    results: Optional[List[dict]] = None
    metadata: Optional[dict] = None

def make_error_response(message: str) -> ToolResponse:
    return ToolResponse(
        classification="Error",
        response=message,
        error=message,
        ticket_ids=[],
        etiquetas=[],
        results=[]
    )

