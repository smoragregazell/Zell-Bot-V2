"""
Script para analizar los scores de búsqueda en meetings_weekly.
Ayuda a determinar qué threshold usar para filtrar resultados irrelevantes.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Tools.search_docs import search_docs
import json

def analyze_meetings_search(query: str, top_k: int = 10):
    """
    Analiza una búsqueda en meetings_weekly y muestra los scores detallados.
    
    Args:
        query: Query a buscar
        top_k: Número de resultados a analizar (default 10 para ver más)
    """
    print(f"\n{'='*80}")
    print(f"BÚSQUEDA: '{query}'")
    print(f"Universo: meetings_weekly")
    print(f"Top K: {top_k}")
    print(f"{'='*80}\n")
    
    result = search_docs(query=query, universe="meetings_weekly", top_k=top_k)
    
    if not result.get("ok"):
        print(f"[ERROR] Error: {result.get('error')}")
        return
    
    hits = result.get("hits", [])
    
    if not hits:
        print("[X] No se encontraron resultados")
        return
    
    print(f"[OK] Se encontraron {len(hits)} resultados:\n")
    
    # Analizar scores
    scores = [h.get("score", 0.0) for h in hits]
    min_score = min(scores)
    max_score = max(scores)
    avg_score = sum(scores) / len(scores) if scores else 0
    
    print(f"ESTADISTICAS DE SCORES:")
    print(f"   Mínimo: {min_score:.4f}")
    print(f"   Máximo: {max_score:.4f}")
    print(f"   Promedio: {avg_score:.4f}")
    print(f"   Rango: {max_score - min_score:.4f}\n")
    
    print(f"{'='*80}")
    print(f"RESULTADOS DETALLADOS:")
    print(f"{'='*80}\n")
    
    for i, h in enumerate(hits, 1):
        score = h.get("score", 0.0)
        title = h.get("title", "N/A")
        section = h.get("section", "")
        meeting_date = h.get("meeting_date", "")
        row_key = h.get("row_key", "")
        
        # Clasificar relevancia por score
        # FAISS usa IndexFlatIP (Inner Product) con vectores normalizados = Cosine Similarity
        # Cosine similarity: 1.0 = idéntico, 0.9+ = muy similar, 0.7-0.9 = similar, 0.5-0.7 = poco similar, <0.5 = irrelevante
        if score >= 0.9:
            relevance = "[VERDE] MUY RELEVANTE"
        elif score >= 0.7:
            relevance = "[AMARILLO] RELEVANTE"
        elif score >= 0.5:
            relevance = "[NARANJA] POCO RELEVANTE"
        else:
            relevance = "[ROJO] IRRELEVANTE"
        
        print(f"[{i}] Score: {score:.4f} {relevance}")
        print(f"    Título: {title}")
        if section:
            print(f"    Sección: {section}")
        if meeting_date:
            print(f"    Fecha reunión: {meeting_date}")
        if row_key and "#tema-" in str(row_key):
            tema_num = str(row_key).split("#tema-")[-1]
            print(f"    Tema: #{tema_num}")
        
        # Mostrar snippet del texto (primeros 200 chars)
        snippet = h.get("snippet", "") if hasattr(h, "get") else ""
        if snippet:
            print(f"    Preview: {snippet[:200]}...")
        
        print()
    
    print(f"{'='*80}")
    print(f"RECOMENDACIONES:")
    print(f"{'='*80}")
    print(f"1. Scores >= 0.9: Muy relevantes (Cosine Similarity) - Incluir siempre")
    print(f"2. Scores 0.7-0.9: Relevantes - Incluir si hay pocos resultados")
    print(f"3. Scores 0.5-0.7: Poco relevantes - Considerar filtrar")
    print(f"4. Scores < 0.5: Irrelevantes - Filtrar")
    print(f"\n[Sugerencia] Filtrar resultados con score < 0.7 para mejorar relevancia\n")


def main():
    """Ejecuta análisis con queries de prueba"""
    
    test_queries = [
        "reintentos de domiciliación",
        "domiciliación",
        "problemas con Banxico",
        "errores 500",
        "configuración de producto",
        "llave duplicada en base de datos",
        "responsabilidades por errores",
        "tickets de seguimiento",
    ]
    
    if len(sys.argv) > 1:
        # Si se pasa un query como argumento, usarlo
        query = " ".join(sys.argv[1:])
        analyze_meetings_search(query, top_k=10)
    else:
        # Ejecutar todos los queries de prueba
        for query in test_queries:
            analyze_meetings_search(query, top_k=10)
            print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()

