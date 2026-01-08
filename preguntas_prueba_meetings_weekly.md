# Preguntas de Prueba para Meetings Weekly

## 🎯 OBJETIVO
Verificar que meetings_weekly devuelve resultados relevantes y no trae contenido irrelevante con scores bajos.

---

## 📋 PREGUNTAS DE PRUEBA POR CATEGORÍA

### 1️⃣ PROBLEMAS Y SOLUCIONES DISCUTIDOS

1. **¿Alguien ha tenido problemas con reintentos de domiciliación?**
   - Debería encontrar: temas relacionados con domiciliación y reintentos
   - NO debería traer: temas sobre Banxico, errores 500, configuración de producto

2. **¿Cómo se resolvió el problema de domiciliación?**
   - Debería encontrar: discusiones sobre soluciones de domiciliación
   - Verificar score mínimo

3. **¿Hay experiencia del equipo con errores de Banxico?**
   - Debería encontrar: temas sobre Banxico CEP, mantenimiento
   - NO debería traer: temas sobre domiciliación

4. **¿Alguien ya atendió casos de errores 500?**
   - Debería encontrar: temas sobre errores 500, responsabilidades
   - NO debería traer: temas no relacionados

5. **¿Qué solución se dio para llaves duplicadas en base de datos?**
   - Debería encontrar: tema específico sobre BD y llaves duplicadas

---

### 2️⃣ REUNIONES ESPECÍFICAS

6. **¿Qué se habló en la reunión del 10 de enero?**
   - Debería encontrar: minuta del 2025-01-10
   - Verificar que trae temas relevantes

7. **¿Quiénes asistieron a la reunión del 31 de enero?**
   - Debería encontrar: minuta del 2025-01-31 con asistentes
   - NO debería traer: otras reuniones

8. **¿Qué temas se trataron en las reuniones de enero?**
   - Debería encontrar: todas las minutas de enero
   - Verificar relevancia de temas

---

### 3️⃣ DECISIONES Y ACUERDOS

9. **¿Qué se decidió sobre los errores 500?**
   - Debería encontrar: acuerdos específicos sobre errores 500
   - NO debería traer: temas generales

10. **¿Hubo algún acuerdo sobre responsabilidades de errores?**
    - Debería encontrar: tema #10-12 sobre responsabilidades
    - Verificar score

---

### 4️⃣ CASOS ESPECÍFICOS

11. **¿Hay casos similares al problema de configuración de producto?**
    - Debería encontrar: tema #6 sobre configuración de producto
    - Verificar que no trae temas irrelevantes

12. **¿Se discutió algo sobre tickets de seguimiento?**
    - Debería encontrar: tema #10-12 sobre seguimiento de tickets
    - NO debería traer: temas de domiciliación

---

### 5️⃣ EXPERIENCIAS DEL EQUIPO

13. **¿Alguien ha enfrentado problemas con Banxico CEP?**
    - Debería encontrar: tema #7 sobre Banxico CEP
    - Verificar relevancia

14. **¿Hay experiencia del equipo con mantenimiento de sistemas?**
    - Debería encontrar: discusiones sobre mantenimiento
    - Verificar que no trae contenido genérico

---

## 🔍 ANÁLISIS DE SCORES

Para cada pregunta, registrar:

- [ ] Score mínimo encontrado
- [ ] Score máximo encontrado
- [ ] Score promedio
- [ ] Cantidad de resultados con score > 0.6 (potencialmente irrelevantes)
- [ ] Cantidad de resultados con score > 0.7 (definitivamente irrelevantes)
- [ ] ¿Los resultados son relevantes al query?

---

## 📊 CRITERIOS DE EVALUACIÓN

### ✅ RESULTADO ACEPTABLE:
- Todos los resultados tienen score < 0.6
- Los resultados son relevantes al query
- No hay resultados completamente irrelevantes

### ⚠️ RESULTADO A MEJORAR:
- Hay resultados con score 0.6-0.7
- Algunos resultados son poco relevantes
- Se pueden incluir si hay pocos resultados, pero idealmente filtrar

### ❌ RESULTADO INACEPTABLE:
- Hay resultados con score > 0.7
- Resultados completamente irrelevantes (ej: búsqueda de "domiciliación" trae temas de Banxico)
- Muchos resultados irrelevantes

---

## 🛠️ RECOMENDACIONES DE THRESHOLD

Basado en los análisis:

- **Score < 0.3**: Muy relevante - Incluir siempre ✅
- **Score 0.3-0.5**: Relevante - Incluir si hay pocos resultados ✅
- **Score 0.5-0.6**: Poco relevante - Considerar filtrar ⚠️
- **Score 0.6-0.7**: Irrelevante - Filtrar en la mayoría de casos ❌
- **Score > 0.7**: Muy irrelevante - Filtrar siempre ❌

**Sugerencia inicial**: Filtrar resultados con score > 0.6

---

## 📝 NOTAS

1. FAISS usa distancia L2 normalizada:
   - 0 = idéntico (muy raro)
   - 0.3 = muy similar
   - 0.5 = similar
   - 0.7 = diferente
   - 2.0 = completamente diferente

2. Los scores pueden variar según:
   - Longitud del query
   - Especificidad del query
   - Tamaño del universo meetings_weekly

3. Es importante probar con queries reales del usuario, no solo queries genéricos.

