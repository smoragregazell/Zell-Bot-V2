import json
import tiktoken

# Cargar algunos chunks
chunks = []
with open('Data/docs_policies_iso_meta.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 5:  # Solo primeros 5
            break
        chunks.append(json.loads(line.strip()))

# Tokenizer para contar tokens
enc = tiktoken.get_encoding("cl100k_base")

print("=" * 80)
print("EJEMPLOS DE CHUNKS - TAMAÑO REAL")
print("=" * 80)
print(f"\nConfiguración actual:")
print(f"  - Chunk size: 650 tokens")
print(f"  - Overlap: 120 tokens")
print(f"  - Encoding: cl100k_base (GPT-4)")
print("\n" + "=" * 80)

for i, chunk in enumerate(chunks, 1):
    text = chunk.get("text", "")
    token_start = chunk.get("token_start", 0)
    token_end = chunk.get("token_end", 0)
    token_count = token_end - token_start
    
    # Contar tokens reales
    actual_tokens = len(enc.encode(text))
    char_count = len(text)
    word_count = len(text.split())
    
    print(f"\n📄 CHUNK #{i}")
    print(f"   Título: {chunk.get('title', 'N/A')}")
    print(f"   Código: {chunk.get('codigo', 'N/A')}")
    print(f"   Tokens (rango): {token_start} - {token_end} = {token_count} tokens")
    print(f"   Tokens (reales): {actual_tokens} tokens")
    print(f"   Caracteres: {char_count:,}")
    print(f"   Palabras: ~{word_count:,}")
    print(f"   Tamaño aproximado: ~{char_count/4:.0f} palabras")
    print(f"\n   📝 TEXTO (primeros 500 caracteres):")
    print(f"   {'-' * 76}")
    preview = text[:500].replace('\n', ' ')
    print(f"   {preview}...")
    print(f"   {'-' * 76}")

print("\n" + "=" * 80)
print("RESUMEN:")
print("=" * 80)
print(f"  • Cada chunk tiene aproximadamente 650 tokens")
print(f"  • En español, 1 token ≈ 0.75 palabras (o ~4 caracteres)")
print(f"  • Entonces cada chunk ≈ 490 palabras ≈ 2,600 caracteres")
print(f"  • Equivale a aproximadamente 2-3 párrafos medianos")
print(f"  • Overlap de 120 tokens asegura contexto entre chunks adyacentes")
print("=" * 80)

