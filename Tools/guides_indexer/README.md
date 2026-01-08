# Indexador de Guías de Usuario del Sistema Zell

Este módulo indexa las guías de usuario del sistema Zell (~200 documentos DOCX) en un índice vectorial FAISS para búsqueda semántica.

## Estructura de las Guías

Las guías tienen una estructura específica:
- **Página 1**: Título en formato `(N) Zell - Nombre de la guía`
- **Página 2**: Índice (se filtra, no se indexa)
- **Páginas siguientes**: Pasos numerados con texto e imágenes (capturas de pantalla)

## Flujo de Trabajo

### 1. Construir el Catálogo desde Excel

Primero, construir el catálogo desde el Excel maestro "LISTADO MAESTRO DE GUÍAS":

```bash
python -m Tools.guides_catalog_builder \
    --xlsx "path/to/LISTADO_MAESTRO_DE_GUIAS.xlsx" \
    --out Data/guides_catalog.json
```

Esto genera `Data/guides_catalog.json` con toda la metadata del Excel (OBJETIVO, REFERENCIA CLIENTE/TICKET, etc.)

### 2. Indexar las Guías

Indexar todos los documentos DOCX:

```bash
python -m Tools.guides_indexer \
    --input knowledgebase/user_guides \
    --out Data \
    --catalog Data/guides_catalog.json
```

O solo los primeros 10 archivos para prueba:

```bash
python -m Tools.guides_indexer \
    --input knowledgebase/user_guides \
    --max-files 10
```

### 3. Usar en Búsqueda

Las guías ya están disponibles automáticamente en el universo `user_guides`:

```python
from Tools.search_docs import search_docs

results = search_docs(
    query="¿Cómo configurar reintentos de domiciliación?",
    universe="user_guides",
    top_k=5
)
```

## Archivos Generados

- `Data/user_guides.index` - Índice FAISS con vectores
- `Data/user_guides_meta.jsonl` - Metadata completa de cada chunk (JSONL)
- `Data/user_guides_emb_cache.jsonl` - Cache de embeddings (evita re-generar)
- `Data/user_guides_file_cache.jsonl` - Cache de archivos procesados (actualización incremental)

## Metadata Incluida

Cada chunk incluye metadata enriquecida desde el catálogo:

- `doc_number`: Número del documento
- `objetivo`: OBJETIVO (muy importante para búsqueda)
- `referencia_cliente_ticket`: Referencia a cliente/ticket donde se habló
- `fecha_ultimo_cambio`, `version`, `cambio_realizado`
- `autores`, `verifico`, `asignada_a`
- `fecha_asignacion`, `fecha_entregado`
- `section`: Sección del documento (ej: "Paso 1")
- `step_number`: Número de paso si aplica

## Características

- **Actualización incremental**: Solo procesa archivos nuevos o modificados
- **Cache de embeddings**: No re-genera embeddings de chunks sin cambios (ahorra costos)
- **Filtrado inteligente**: Filtra encabezados/footers comunes automáticamente
- **Extracción de pasos**: Detecta y mantiene estructura de pasos numerados
- **Matching con catálogo**: Coincidencia automática por título/número de documento

