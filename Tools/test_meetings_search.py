"""
Script para diagnosticar el problema de búsqueda en meetings_weekly.
Verifica si hay inconsistencia en normalización o embeddings.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import faiss
import json
from Tools.search_tickets import generate_openai_embedding

def test_exact_search():
    """Prueba búsqueda exacta del texto que está en los metadatos"""
    
    # Texto exacto del tema 5
    exact_text = "En mantenimiento del servidor a todos los clientes, GFI reportó que el consecutivo de los ID no estaba correcto, saltando 10,000 números."
    
    print("="*80)
    print("DIAGNÓSTICO DE BÚSQUEDA EXACTA EN MEETINGS_WEEKLY")
    print("="*80)
    print(f"\nQuery exacto: {exact_text[:80]}...\n")
    
    # 1. Cargar índice y metadata
    index = faiss.read_index("Data/docs_meetings_weekly.index")
    print(f"Índice: {index.ntotal} vectores, dimensión: {index.d}")
    print(f"Tipo métrica: {index.metric_type} (0=Inner Product, 1=L2)")
    
    # Cargar metadata
    meta = []
    with open("Data/docs_meetings_weekly_meta.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                meta.append(json.loads(line))
    
    print(f"Metadata: {len(meta)} chunks\n")
    
    # 2. Buscar el chunk que contiene este texto exacto (el más específico, no el chunk completo)
    target_chunk = None
    for m in meta:
        text = m.get("text", "")
        # Buscar el chunk que contiene el texto exacto y que sea un tema específico (no la minuta completa)
        if exact_text in text:
            # Preferir chunks que sean temas específicos (row_key con #tema)
            if target_chunk is None or (m.get("row_key") and "#tema" in str(m.get("row_key"))):
                target_chunk = m
    
    if not target_chunk:
        print("[ERROR] No se encontró el chunk con el texto exacto en metadata")
        return
    
    print(f"[OK] Chunk objetivo encontrado:")
    print(f"   chunk_id: {target_chunk['chunk_id']}")
    print(f"   Título: {target_chunk['title']}")
    print(f"   Tema: {target_chunk.get('row_key', 'N/A')}")
    print(f"   Fecha: {target_chunk.get('meeting_date', 'N/A')}")
    
    # 3. Generar embedding del query
    print(f"\n[1] Generando embedding del query...")
    query_vec = generate_openai_embedding(exact_text, conversation_id="test", interaction_id=None)
    if query_vec is None:
        print("[ERROR] No se pudo generar embedding")
        return
    
    print(f"   Embedding shape: {query_vec.shape}")
    print(f"   Norma antes de normalizar: {np.linalg.norm(query_vec):.6f}")
    
    # Normalizar (como lo hace search_docs.py)
    query_norm = query_vec / np.linalg.norm(query_vec)
    print(f"   Norma después de normalizar: {np.linalg.norm(query_norm):.6f}")
    
    # 4. Buscar en el índice
    print(f"\n[2] Buscando en el índice (top 10)...")
    scores, ids = index.search(query_norm.reshape(1, -1), 10)
    
    print(f"\nTop 10 resultados:")
    target_found = False
    for i, (score, idx) in enumerate(zip(scores[0], ids[0])):
        if idx < 0 or idx >= len(meta):
            continue
        
        m = meta[idx]
        is_target = m['chunk_id'] == target_chunk['chunk_id']
        if is_target:
            target_found = True
        
        marker = " <-- OBJETIVO" if is_target else ""
        print(f"  [{i+1}] Score: {score:.6f} | ID: {idx} | chunk_id: {m['chunk_id']}{marker}")
        print(f"      Titulo: {m.get('title', 'N/A')[:60]}")
        if m.get('row_key'):
            print(f"      Tema: {m.get('row_key')}")
    
    if not target_found:
        print(f"\n[PROBLEMA] El chunk objetivo NO esta en los top 10 resultados")
        print(f"   El mejor score fue: {scores[0][0]:.6f}")
    else:
        print(f"\n[OK] El chunk objetivo SI esta en los resultados")
    
    # 5. Verificar normalización de vectores en el índice
    print(f"\n[3] Verificando normalización de vectores en el índice...")
    print(f"   (Esto requiere reconstruir el índice, solo para diagnóstico)")
    
    # Intentar recuperar el vector del chunk objetivo desde el índice
    # Nota: IndexFlatIP no permite recuperar vectores fácilmente, pero podemos verificar
    # que los scores son consistentes con cosine similarity
    
    print(f"\n[4] Análisis de scores:")
    print(f"   Con IndexFlatIP y vectores normalizados L2:")
    print(f"   - Score = Inner Product = Cosine Similarity")
    print(f"   - Rango esperado: -1 a 1 (pero típicamente 0 a 1 para embeddings)")
    print(f"   - 1.0 = idéntico, 0.0 = ortogonal")
    print(f"   - Scores < 0.3 = muy similar")
    print(f"   - Scores > 0.7 = muy diferente")
    
    # Calcular cosine similarity manualmente para verificar
    # Necesitaríamos el vector del chunk objetivo del índice, pero IndexFlatIP no lo permite
    # fácilmente sin reconstruir el índice

if __name__ == "__main__":
    test_exact_search()

