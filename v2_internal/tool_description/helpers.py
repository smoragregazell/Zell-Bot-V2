"""
Funciones helper para herramientas
"""
from typing import Any, Dict, List


def _dedupe_hits(hits: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """
    Deduplica hits por type::id y mantiene el mejor score.
    
    Si un item aparece en múltiples búsquedas (keyword + semantic), 
    mantiene el que tenga el mayor score. Todos los scores están normalizados
    a [0.0, 1.0] donde mayor = mejor.
    
    Args:
        hits: Lista de hits que pueden tener duplicados (mismo type::id)
        top_k: Número máximo de resultados a retornar
    
    Returns:
        Lista deduplicada y ordenada por score descendente (mejores primero)
    """
    best: Dict[str, Dict[str, Any]] = {}
    for h in hits:
        k = f"{h.get('type')}::{h.get('id')}"
        # Mantener el hit con mayor score si hay duplicados
        if k not in best or float(h.get("score", 0)) > float(best[k].get("score", 0)):
            best[k] = h
    # Ordenar por score descendente (mayor = mejor) y retornar top_k
    return sorted(best.values(), key=lambda x: float(x.get("score", 0)), reverse=True)[:top_k]

