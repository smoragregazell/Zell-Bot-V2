# 5 Preguntas que DEBERÍAN tener Alta Semejanza en Meetings Weekly

Basado en el análisis del archivo `docs_meetings_weekly_meta.jsonl`, estas son preguntas sobre temas específicos que están documentados en las minutas y que **deberían** tener scores bajos (<0.5) pero actualmente están dando scores altos (>0.7).

---

## 1️⃣ Pregunta: Error de Banxico CEP
**Query de prueba:**
```
¿Qué pasó con el error al cargar archivos a Banxico para validar datos CEP?
```

**Tema correspondiente:**
- **Fecha reunión:** 2025-01-10
- **Tema:** #7
- **Texto exacto:** "En INM reportaron que al cargar archivos a Banxico para validar datos CEP había un error. Se vio que no era un error de Zell, sino por mantenimiento de la página de Banxico."

**Score esperado:** < 0.4 (muy relevante)
**Score actual:** ~0.78 (irrelevante) ❌

---

## 2️⃣ Pregunta: Error de llave duplicada en CRF
**Query de prueba:**
```
¿Cómo se resolvió el error de llave duplicada en base de datos que reportó CRF?
```

**Tema correspondiente:**
- **Fecha reunión:** 2025-01-10
- **Tema:** #8
- **Texto exacto:** "En CRF intentaron realizar acción en base de datos pero les aparecía error de llave duplicada. Se le dijo que no se puede modificar a la base de datos por temas de propiedad intelectual..."

**Score esperado:** < 0.4 (muy relevante)
**Score actual:** ~0.78 (irrelevante) ❌

---

## 3️⃣ Pregunta: Responsabilidad de errores 500
**Query de prueba:**
```
¿De quién es la responsabilidad de los errores que empiezan con 500 en círculo de crédito?
```

**Tema correspondiente:**
- **Fecha reunión:** 2025-01-31
- **Tema:** #10
- **Texto exacto:** "En círculo de crédito, todos los errores que empiecen con 500 (501, 502…) son de su responsabilidad."

**Score esperado:** < 0.3 (muy relevante - texto muy específico)
**Score actual:** ~0.79 (irrelevante) ❌

---

## 4️⃣ Pregunta: Configuración producto PyME sin intereses
**Query de prueba:**
```
¿Cómo se configuró el producto PyME sin intereses para DFR?
```

**Tema correspondiente:**
- **Fecha reunión:** 2025-01-10
- **Tema:** #6
- **Texto exacto:** "En DFR configuraron producto PyME donde solicitaron que a un financiamiento de 3 millones no se aplicaran intereses. En Zell no se puede realizar, ya que no se puede realizar producto sin intereses, por lo que agregaron una tasa de 0.000001 para que visualmente en la tabla apareciera así."

**Score esperado:** < 0.4 (muy relevante)
**Score actual:** ~0.82 (irrelevante) ❌

---

## 5️⃣ Pregunta: Consecutivo ID saltando 10,000 números
**Query de prueba:**
```
¿Por qué el consecutivo de los ID estaba saltando 10,000 números en GFI después del mantenimiento del servidor?
```

**Tema correspondiente:**
- **Fecha reunión:** 2025-01-10
- **Tema:** #5
- **Texto exacto:** "En mantenimiento del servidor a todos los clientes, GFI reportó que el consecutivo de los ID no estaba correcto, saltando 10,000 números. Se vio que el proveedor del mantenimiento deja 10,000 caracteres para que no se dupliquen."

**Score esperado:** < 0.4 (muy relevante)
**Score actual:** ~0.78 (irrelevante) ❌

---

## 📊 Análisis de Resultados

**Problema detectado:**
- TODAS las preguntas específicas están dando scores > 0.7 (irrelevantes)
- Incluso preguntas muy específicas sobre temas exactamente documentados no encuentran resultados relevantes
- El mejor score encontrado fue 0.7802 (todavía irrelevante)

**Posibles causas:**
1. El índice FAISS puede no estar bien entrenado o actualizado
2. Los embeddings pueden no estar capturando bien la semántica
3. Puede haber un problema con la normalización de los vectores
4. El universo meetings_weekly puede ser demasiado pequeño para generar buenos embeddings

**Acción recomendada:**
1. **Implementar filtro de score** en `search_docs.py` para meetings_weekly:
   - Filtrar resultados con score > 0.6
   - Si todos los resultados están filtrados, devolver "No se encontraron resultados relevantes"
2. **Re-indexar** meetings_weekly para verificar que los embeddings están correctos
3. **Investigar** por qué los scores son tan altos incluso para preguntas específicas

---

## ✅ Uso de estas preguntas

Estas preguntas deberían usarse para:
- Verificar que el filtro de score funciona correctamente
- Probar después de re-indexar meetings_weekly
- Validar que mejoras en embeddings mejoran los scores
- Como casos de prueba para optimización del sistema de búsqueda

