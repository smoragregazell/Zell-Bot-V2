# Diagnóstico del Problema con Meetings Weekly

## 🔴 Problema Encontrado

Al hacer una búsqueda **EXACTA** del texto que está documentado en las minutas:
```
"En mantenimiento del servidor a todos los clientes, GFI reportó que el consecutivo de los ID no estaba correcto, saltando 10,000 números."
```

**Resultado:**
- El chunk objetivo (`058d5aec1a2f_5`, tema #5 del 10-01-2025) **NO aparece** en el top 10 resultados
- El mejor score fue **0.935701** (muy alto, significa muy diferente)
- Todos los resultados tienen scores > 0.8 (irrelevantes)

## ✅ Lo que está bien

1. **Normalización de embeddings:**
   - `generate_openai_embedding()` normaliza correctamente con `faiss.normalize_L2`
   - La normalización adicional en `embed_text_cached()` es idempotente (no cambia nada)
   - El query y los vectores indexados están normalizados consistentemente

2. **Calidad de los embeddings:**
   - La cosine similarity entre el query exacto y el chunk objetivo es **0.9476** (muy alta, casi perfecta)
   - Los embeddings capturan correctamente la semántica del texto

## ❌ El Problema Real

**El índice FAISS está desactualizado o corrupto.**

Aunque los embeddings son correctos y tienen alta similitud (0.9476), el índice FAISS no está devolviendo el chunk objetivo en el top 10. Esto indica que:

1. Los vectores en el índice pueden no estar normalizados correctamente
2. O el índice fue construido con vectores de una versión anterior
3. O hay una inconsistencia entre cómo se indexaron los vectores y cómo se están buscando

## 🔧 Solución

**Re-indexar el universo `meetings_weekly`:**

```bash
python -m Tools.docs_indexer --universe meetings_weekly --input knowledgebase/meetings_weekly --out Data --force
```

Esto reconstruirá el índice desde cero con los vectores correctamente normalizados.

## 📊 Evidencia

### Test de búsqueda exacta:
- **Query:** Texto exacto del tema #5
- **Chunk objetivo:** `058d5aec1a2f_5`
- **Resultado:** NO aparece en top 10
- **Mejor score:** 0.935701 (irrelevante)

### Test de embeddings:
- **Cosine similarity query vs chunk objetivo:** 0.9476 (muy alta)
- **Normalización:** Correcta e idempotente
- **Conclusión:** Los embeddings están bien, el índice está mal

## 🎯 Próximos Pasos

1. **Re-indexar meetings_weekly** para reconstruir el índice
2. **Verificar** que los scores mejoren después de re-indexar
3. **Implementar filtro de score** en `search_docs.py` para meetings_weekly (filtrar > 0.6)
4. **Probar** las 5 preguntas de alta semejanza después de re-indexar

