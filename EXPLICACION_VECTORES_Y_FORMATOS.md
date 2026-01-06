# Explicación Detallada: Vectores, Formatos de Archivos y Diferencia entre Tickets y Docs

## 📚 Conceptos Fundamentales

### 1. ¿Qué son los Vectores en Espacios Multidimensionales?

Imagina que cada palabra, frase o documento puede representarse como un punto en un espacio de muchas dimensiones (típicamente 1536 dimensiones para `text-embedding-ada-002`).

**Ejemplo simple (3D para visualizar):**
- "Implementación de inventarios" → vector `[0.2, 0.8, 0.3]`
- "Sistema de control de stock" → vector `[0.25, 0.75, 0.35]`
- "Consulta de tickets" → vector `[0.9, 0.1, 0.2]`

Los primeros dos están "cerca" porque hablan de lo mismo (inventarios), el tercero está "lejos" porque es diferente.

**En realidad usamos 1536 dimensiones**, pero la idea es la misma:
- Textos similares → vectores cercanos en el espacio
- Textos diferentes → vectores alejados

### 2. ¿Cómo Funciona la Búsqueda Semántica?

```
1. Usuario pregunta: "¿existe alguna cotización para inventarios?"
2. Sistema convierte pregunta a vector: [0.21, 0.79, 0.31, ... (1536 números)]
3. Sistema busca en el "universo" de vectores guardados
4. Encuentra los vectores más cercanos (por distancia/cosine similarity)
5. Devuelve los IDs/códigos de esos documentos/chunks más cercanos
```

**La "distancia" se mide con:**
- **Cosine Similarity** (similitud del coseno): mide el ángulo entre vectores
- Valores cercanos a 1.0 = muy similares
- Valores cercanos a 0.0 = diferentes

---

## 📁 Formatos de Archivos: ¿Por qué diferentes extensiones?

### `.bin` - Índice FAISS (Binary)

**¿Qué es?**
- Archivo binario optimizado que contiene los **vectores** organizados para búsqueda rápida
- Es como un "mapa del universo" donde están todos los vectores

**¿Qué contiene?**
- Los vectores numéricos (arrays de 1536 números float32 cada uno)
- Estructura interna de FAISS para búsqueda eficiente (árboles, índices invertidos, etc.)

**Ejemplo:**
```
faiss_index_ip.bin contiene:
  Vector 0: [0.123, 0.456, ..., 0.789] (1536 números)
  Vector 1: [0.234, 0.567, ..., 0.890] (1536 números)
  Vector 2: [0.345, 0.678, ..., 0.901] (1536 números)
  ... (millones de vectores)
```

**Por qué `.bin`:**
- Binario = muy rápido de leer
- Optimizado por FAISS para búsquedas en milisegundos
- No es legible por humanos (es código de máquina)

---

### `.npy` - NumPy Array (Numeric Python)

**¿Qué es?**
- Formato binario de NumPy para arrays numéricos
- Más simple que `.bin`, solo arrays de números

**¿Qué contiene en tickets?**
- Array de IDs: `[123, 456, 789, 1011, ...]`
- Relación 1:1 con las posiciones del índice FAISS

**Ejemplo:**
```
faiss_ids.npy contiene:
  [123, 456, 789, 1011, 2022, ...]
  
Significado:
  Posición 0 en FAISS → Ticket ID 123
  Posición 1 en FAISS → Ticket ID 456
  Posición 2 en FAISS → Ticket ID 789
```

**Por qué `.npy`:**
- Formato estándar de Python/NumPy
- Eficiente para arrays numéricos simples
- Fácil de cargar: `np.load("faiss_ids.npy")`

**⚠️ PROBLEMA OBSERVADO:**
En `semantic_tool.py` línea 95, el código usa `int(idx)` directamente como ticket_id, **NO usa `issue_ids[idx]`**. Esto sugiere que:
- O el índice FAISS está estructurado de manera que el índice posicional ES el ticket_id
- O hay un bug/implementación especial

---

### `.index` - Índice FAISS (Alternative naming)

**¿Qué es?**
- **Mismo tipo que `.bin`**: Es un índice FAISS binario
- Solo cambia el nombre por convención

**¿Qué contiene?**
- Exactamente lo mismo: vectores organizados para búsqueda rápida

**Por qué `.index` en docs pero `.bin` en tickets?**
- Solo es una convención de nombres diferente
- Ambos son archivos FAISS binarios
- Funcionalmente idénticos

---

### `.jsonl` - JSON Lines (JSON por línea)

**¿Qué es?**
- **JSON Lines**: cada línea del archivo es un objeto JSON completo
- No es un array JSON grande, es una línea = un objeto

**Formato:**
```
{"chunk_id": "abc123", "doc_id": "doc1", "title": "Manual de Calidad", "text": "..."}
{"chunk_id": "def456", "doc_id": "doc1", "title": "Manual de Calidad", "text": "..."}
{"chunk_id": "ghi789", "doc_id": "doc2", "title": "Política de Seguridad", "text": "..."}
```

**¿Qué contiene?**
- **Metadata rica**: información sobre cada chunk/documento
- `chunk_id`, `doc_id`, `title`, `text`, `section`, `codigo`, etc.
- Información adicional: fechas, códigos, rutas, etc.

**Por qué `.jsonl` y no `.json`?**
- **Ventajas:**
  - Puedes leer línea por línea (no cargar todo en memoria)
  - Más eficiente para archivos grandes
  - Fácil de procesar en streaming
  - Si una línea tiene error, no rompe todo el archivo

**Ejemplo de uso:**
```python
# Cargar JSONL
with open("docs_meta.jsonl", "r") as f:
    for line in f:
        obj = json.loads(line)  # Cada línea es un JSON
        print(obj["chunk_id"])
```

---

## 🔄 Diferencia Arquitectónica: Tickets vs Docs

### Sistema de TICKETS (Simple - 1:1)

**Estructura:**
```
faiss_index_ip.bin  → Vectores (1 por ticket)
faiss_ids.npy       → IDs [123, 456, 789, ...]
```

**Características:**
- **1 vector = 1 ticket completo**
- **Sin chunking**: cada ticket es un solo vector
- **Sin metadata JSONL**: no necesita información adicional
- **Mapeo directo**: posición en índice → ticket_id

**Flujo de búsqueda:**
```
1. Buscar en FAISS → obtener índices [5, 12, 8]
2. Usar índices directamente como ticket_ids (o mapear con faiss_ids.npy)
3. Llamar API: fetch_ticket_data(ticket_id=5)
4. Devolver datos completos del ticket
```

**¿Por qué es simple?**
- Los tickets son entidades completas y relativamente pequeñas
- No necesitas buscar "partes" de un ticket
- La información completa está en la API, no en el índice

---

### Sistema de DOCS (Complejo - Chunking)

**Estructura:**
```
docs_policies_iso.index        → Vectores (múltiples por documento)
docs_policies_iso_meta.jsonl   → Metadata de cada chunk
```

**Características:**
- **Múltiples vectores por documento**: se divide en "chunks" (pedazos)
- **Chunking**: documento largo → varios pedazos pequeños → varios vectores
- **Metadata JSONL**: información rica sobre cada chunk
- **Mapeo indirecto**: posición en índice → metadata JSONL → chunk_id/doc_id

**¿Por qué chunking?**
- Documentos pueden ser MUY largos (100+ páginas)
- Un embedding tiene límite de tokens (~8000 tokens)
- Necesitas buscar en "secciones" específicas, no el documento completo

**Ejemplo:**
```
Documento: "Manual de Calidad" (50 páginas)
  → Chunk 1: "Sección 1: Introducción" → Vector 1
  → Chunk 2: "Sección 2: Alcance" → Vector 2
  → Chunk 3: "Sección 3: Procesos" → Vector 3
  ... (20 chunks total)
```

**Flujo de búsqueda:**
```
1. Buscar en FAISS → obtener índices [42, 15, 89]
2. Mapear índices a metadata: meta[42], meta[15], meta[89]
3. Extraer información: chunk_id, doc_id, title, section, text
4. Devolver chunks específicos (no el documento completo)
```

**¿Por qué metadata JSONL?**
- Necesitas saber: ¿qué documento es? ¿qué sección? ¿qué texto completo?
- El índice FAISS solo tiene números (vectores)
- JSONL guarda toda la información contextual

---

## 📊 Comparación Visual

### TICKETS (1:1 Simple)

```
Ticket #123: "Error en login"
  ↓ (embeddings)
Vector: [0.2, 0.8, 0.3, ...]
  ↓ (guardado en)
faiss_index_ip.bin [posición 0]
faiss_ids.npy [posición 0] = 123

Búsqueda:
  Query → Vector → FAISS → índice 0 → ticket_id 123 → API
```

### DOCS (Chunking Complejo)

```
Documento "Manual.pdf" (50 páginas)
  ↓ (chunking)
Chunk 1: "Introducción" → Vector 1 → FAISS posición 42
Chunk 2: "Alcance" → Vector 2 → FAISS posición 43
Chunk 3: "Procesos" → Vector 3 → FAISS posición 44
  ↓ (metadata)
JSONL línea 42: {chunk_id: "abc", doc_id: "Manual", section: "Introducción", text: "..."}
JSONL línea 43: {chunk_id: "def", doc_id: "Manual", section: "Alcance", text: "..."}
JSONL línea 44: {chunk_id: "ghi", doc_id: "Manual", section: "Procesos", text: "..."}

Búsqueda:
  Query → Vector → FAISS → índice 43 → meta[43] → chunk_id "def", doc_id "Manual", text completo
```

---

## 🤔 ¿Qué Sistema Usar para Cotizaciones?

### Opción 1: Sistema Simple (como Tickets)
**Ventajas:**
- Más simple de implementar
- 1 cotización = 1 vector
- No necesita metadata JSONL
- Más rápido (menos archivos, menos procesamiento)

**Cuándo usar:**
- Si las cotizaciones son relativamente pequeñas
- Si no necesitas buscar en "partes" de una cotización
- Si toda la info está en la API/BD

**Estructura:**
```
faiss_quotes_index.bin  → Vectores (1 por cotización)
faiss_quotes_ids.npy    → IDs [101, 102, 103, ...]
```

### Opción 2: Sistema Complejo (como Docs)
**Ventajas:**
- Puedes buscar en partes específicas de cotizaciones largas
- Metadata rica (cliente, fecha, productos, etc.)
- Más flexible para cotizaciones complejas

**Cuándo usar:**
- Si las cotizaciones son muy largas (muchas líneas/productos)
- Si necesitas buscar en secciones específicas
- Si quieres metadata rica sin llamar a la API

**Estructura:**
```
quotes_index.bin         → Vectores (múltiples por cotización)
quotes_meta.jsonl        → Metadata de cada chunk
```

---

## 📝 Resumen de Formatos

| Formato | Contenido | Uso | Ejemplo |
|---------|-----------|-----|---------|
| `.bin` / `.index` | Vectores FAISS (binario) | Búsqueda rápida | `faiss_index_ip.bin` |
| `.npy` | Array NumPy (IDs numéricos) | Mapeo simple posición→ID | `faiss_ids.npy` |
| `.jsonl` | Metadata rica (texto) | Información contextual | `docs_meta.jsonl` |

---

## 🎯 Respuesta Directa a tus Preguntas

### 1. ¿Qué es JSONL?
**JSON Lines**: cada línea es un objeto JSON. Permite procesar archivos grandes línea por línea sin cargar todo en memoria.

### 2. ¿Por qué diferentes extensiones?
- **`.bin` / `.index`**: Índices FAISS binarios (vectores optimizados)
- **`.npy`**: Arrays NumPy simples (IDs numéricos)
- **`.jsonl`**: Metadata rica en texto (información contextual)

### 3. ¿Por qué uno usa una cosa y otro otra?
- **Tickets**: Simple (1:1), no necesita metadata, usa `.npy` para IDs
- **Docs**: Complejo (chunking), necesita metadata rica, usa `.jsonl`

### 4. ¿Cómo funciona la búsqueda?
1. Pregunta → Vector (1536 números)
2. Buscar en universo de vectores guardados
3. Encontrar los más cercanos (similarity)
4. Mapear índice → ID/metadata
5. Devolver resultados

---

## 💡 Recomendación para Cotizaciones

**Recomiendo Sistema SIMPLE (como tickets)** porque:
- Las cotizaciones suelen ser entidades completas (no documentos largos)
- La información completa está en BD/API
- Más fácil de mantener
- Más rápido

**Estructura sugerida:**
```
Data/faiss_quotes_index.bin  → Vectores (1 por cotización)
Data/faiss_quotes_ids.npy    → IDs [101, 102, 103, ...]
```

