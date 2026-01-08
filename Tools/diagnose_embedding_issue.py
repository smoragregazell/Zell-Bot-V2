"""
Script para diagnosticar el problema de embeddings en meetings_weekly.
Verifica si hay doble normalización o inconsistencia entre indexación y búsqueda.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from Tools.search_tickets import generate_openai_embedding

def diagnose_normalization():
    """Diagnostica si hay problemas con la normalización de embeddings"""
    
    test_text = "En mantenimiento del servidor a todos los clientes, GFI reportó que el consecutivo de los ID no estaba correcto, saltando 10,000 números."
    
    print("="*80)
    print("DIAGNOSTICO DE NORMALIZACION DE EMBEDDINGS")
    print("="*80)
    print(f"\nTexto de prueba: {test_text[:60]}...\n")
    
    # 1. Generar embedding (como lo hace indexación y búsqueda)
    print("[1] Generando embedding con generate_openai_embedding...")
    vec_from_api = generate_openai_embedding(test_text, conversation_id="test", interaction_id=None)
    
    if vec_from_api is None:
        print("[ERROR] No se pudo generar embedding")
        return
    
    print(f"   Shape: {vec_from_api.shape}")
    print(f"   Norma original: {np.linalg.norm(vec_from_api):.6f}")
    
    # generate_openai_embedding YA normaliza con faiss.normalize_L2
    # Verificar si está normalizado
    is_normalized = abs(np.linalg.norm(vec_from_api) - 1.0) < 0.001
    print(f"   Ya normalizado?: {is_normalized}")
    
    # 2. Simular normalización adicional (como lo hace indexación)
    print("\n[2] Normalizando OTRA VEZ (como lo hace embed_text_cached)...")
    from Tools.docs_indexer.utils import normalize_vec_1d
    vec_normalized_again = normalize_vec_1d(vec_from_api.reshape(-1))
    
    print(f"   Norma después de normalizar otra vez: {np.linalg.norm(vec_normalized_again):.6f}")
    
    # Comparar si son iguales
    are_equal = np.allclose(vec_from_api.reshape(-1), vec_normalized_again)
    print(f"   Son iguales?: {are_equal}")
    
    if not are_equal:
        diff = np.linalg.norm(vec_from_api.reshape(-1) - vec_normalized_again)
        print(f"   Diferencia: {diff:.10f}")
    
    # 3. Verificar que la normalización sea idempotente
    print("\n[3] Verificando que la normalización sea idempotente...")
    vec_normalized_twice = normalize_vec_1d(normalize_vec_1d(vec_from_api.reshape(-1)))
    are_equal_twice = np.allclose(normalize_vec_1d(vec_from_api.reshape(-1)), vec_normalized_twice)
    print(f"   Normalizar dos veces da lo mismo?: {are_equal_twice}")
    
    # 4. Probar con el texto exacto de dos chunks diferentes
    print("\n[4] Probando con dos chunks diferentes...")
    text1 = "5 | JB | En mantenimiento del servidor a todos los clientes, GFI reportó que el consecutivo de los ID no estaba correcto, saltando 10,000 números. | JB, FC | Se vio que el proveedor del mantenimiento deja 10,000 caracteres para que no se dupliquen."
    text2 = "FECHA: 2025-01-10\nHORA_INICIO: 12:02\nHORA_FIN: 12:38\n\nASISTENTES:\nFrancisco Javier Cameros Orta | Francisco Javier Cameros Orta\n..."
    
    vec1 = generate_openai_embedding(text1, conversation_id="test1", interaction_id=None)
    vec2 = generate_openai_embedding(text2[:200], conversation_id="test2", interaction_id=None)  # Truncar para que no sea muy largo
    
    if vec1 is not None and vec2 is not None:
        vec1_norm = normalize_vec_1d(vec1.reshape(-1))
        vec2_norm = normalize_vec_1d(vec2.reshape(-1))
        
        # Calcular cosine similarity
        cosine_sim = np.dot(vec1_norm, vec2_norm)
        print(f"   Cosine similarity entre chunk específico y chunk completo: {cosine_sim:.6f}")
        
        # Probar con el texto exacto del query
        vec_query = generate_openai_embedding("En mantenimiento del servidor a todos los clientes, GFI reportó que el consecutivo de los ID no estaba correcto, saltando 10,000 números.", conversation_id="test_query", interaction_id=None)
        if vec_query is not None:
            vec_query_norm = normalize_vec_1d(vec_query.reshape(-1))
            
            sim1 = np.dot(vec_query_norm, vec1_norm)
            sim2 = np.dot(vec_query_norm, vec2_norm)
            
            print(f"\n   Cosine similarity query vs chunk específico: {sim1:.6f}")
            print(f"   Cosine similarity query vs chunk completo: {sim2:.6f}")
            print(f"   Diferencia: {abs(sim1 - sim2):.6f}")

if __name__ == "__main__":
    diagnose_normalization()

