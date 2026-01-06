"""
Script para calcular el costo de vectorización de documentos
"""
import json
import tiktoken

# Precio de OpenAI text-embedding-ada-002 (por 1K tokens)
# Fuente: https://openai.com/pricing (actualizado 2024)
COSTO_EMBEDDING_POR_1K_TOKENS = 0.0001  # $0.0001 por 1K tokens = $0.10 por 1M tokens

# Configuración de chunking
DEFAULT_CHUNK_TOKENS = 650
DEFAULT_OVERLAP_TOKENS = 120

def analizar_documento_ejemplo():
    """Analiza el documento de ejemplo para calcular costos"""
    enc = tiktoken.get_encoding("cl100k_base")
    
    # Leer chunks del documento de ejemplo
    chunks = []
    with open("Data/docs_meetings_weekly_meta.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if "3dd14b53b939" in data.get("doc_id", ""):
                    chunks.append(data)
    
    if not chunks:
        print("No se encontró el documento de ejemplo")
        return None
    
    # Calcular tokens reales
    total_tokens = 0
    for chunk in chunks:
        tokens = len(enc.encode(chunk["text"]))
        total_tokens += tokens
    
    costo_documento = (total_tokens / 1000) * COSTO_EMBEDDING_POR_1K_TOKENS
    
    return {
        "chunks": len(chunks),
        "tokens_totales": total_tokens,
        "costo_usd": costo_documento,
        "titulo": chunks[0].get("title", "N/A")
    }

def calcular_costo_350_documentos():
    """Calcula el costo para 350 documentos similares"""
    ejemplo = analizar_documento_ejemplo()
    if not ejemplo:
        return None
    
    # Proyección para 350 documentos
    tokens_por_doc = ejemplo["tokens_totales"]
    costo_por_doc = ejemplo["costo_usd"]
    
    total_tokens_350 = tokens_por_doc * 350
    total_costo_350 = costo_por_doc * 350
    
    return {
        "documentos": 350,
        "tokens_por_documento": tokens_por_doc,
        "chunks_por_documento": ejemplo["chunks"],
        "costo_por_documento_usd": costo_por_doc,
        "total_tokens_350_docs": total_tokens_350,
        "total_costo_350_docs_usd": total_costo_350,
        "total_costo_350_docs_mxn": total_costo_350 * 17  # Aprox 17 MXN por USD
    }

def main():
    print("=" * 70)
    print("ANÁLISIS DE COSTOS DE VECTORIZACIÓN")
    print("=" * 70)
    print()
    
    # Análisis del documento de ejemplo
    ejemplo = analizar_documento_ejemplo()
    if ejemplo:
        print("DOCUMENTO DE EJEMPLO:")
        print(f"   Titulo: {ejemplo['titulo']}")
        print(f"   Chunks generados: {ejemplo['chunks']}")
        print(f"   Tokens totales: {ejemplo['tokens_totales']:,}")
        print(f"   Costo (USD): ${ejemplo['costo_usd']:.6f}")
        print(f"   Costo (MXN): ${ejemplo['costo_usd'] * 17:.4f}")
        print()
    
    # Proyección para 350 documentos
    proyeccion = calcular_costo_350_documentos()
    if proyeccion:
        print("PROYECCION PARA 350 DOCUMENTOS:")
        print(f"   Documentos: {proyeccion['documentos']}")
        print(f"   Chunks por documento: ~{proyeccion['chunks_por_documento']}")
        print(f"   Tokens por documento: ~{proyeccion['tokens_por_documento']:,}")
        print(f"   Costo por documento (USD): ${proyeccion['costo_por_documento_usd']:.6f}")
        print()
        print(f"   TOTAL TOKENS (350 docs): {proyeccion['total_tokens_350_docs']:,}")
        print(f"   TOTAL COSTO (350 docs, USD): ${proyeccion['total_costo_350_docs_usd']:.4f}")
        print(f"   TOTAL COSTO (350 docs, MXN): ${proyeccion['total_costo_350_docs_mxn']:.2f}")
        print()
    
    print("=" * 70)
    print("DETALLES DEL PROCESO:")
    print("=" * 70)
    print("1. Extraccion de texto del .docx")
    print("2. Division en chunks (650 tokens, overlap 120)")
    print("3. Generacion de embeddings (text-embedding-ada-002)")
    print("4. Almacenamiento en indice FAISS")
    print("5. Cache de embeddings para evitar reprocesamiento")
    print()
    print("VENTAJAS DEL SISTEMA ACTUAL:")
    print("   + Cache de embeddings: documentos no modificados no se reprocesan")
    print("   + Actualizacion incremental: solo procesa archivos nuevos/modificados")
    print("   + Chunking inteligente: respeta estructura de minutas (1 chunk por tema)")
    print()
    print("COSTO DE text-embedding-ada-002:")
    print("   $0.0001 por 1,000 tokens")
    print("   $0.10 por 1,000,000 tokens")
    print()

if __name__ == "__main__":
    main()

