# Análisis del Archivo "Etiquetas ZELL V1.xlsx" para Vectorización

## 📊 Resumen Ejecutivo

El archivo contiene **1,642 filas** de datos estructurados sobre etiquetas del sistema ZELL, con **8 columnas** principales. Este documento analiza la estructura y propone una estrategia de vectorización.

## 📋 Estructura del Archivo

### Columnas Identificadas

1. **Numero** (1,549 valores no nulos - 94.3%)
   - Identificador numérico único de cada etiqueta
   - Rango: 1 - 7,770
   - Tipo: Numérico

2. **Etiqueta** (1,281 valores no nulos - 78.0%)
   - Código de etiqueta en formato `[i101: PID]`
   - 1,276 valores únicos
   - Longitud promedio: 14.9 caracteres
   - Ejemplo: `[i101: PID]`, `[i102: PFNBN]`

3. **Descripcion** (1,431 valores no nulos - 87.1%)
   - Descripción en español de la etiqueta
   - 1,348 valores únicos
   - Longitud promedio: 35.9 caracteres
   - Ejemplo: "Numero de Persona Asignado por el sistema"

4. **CLIENTE QUE LA TIENE** (4 valores no nulos - 0.2%)
   - Información sobre qué cliente tiene la etiqueta
   - Muy pocos valores (solo 4 únicos)
   - Columna casi vacía

5. **Desc Tabla** (852 valores no nulos - 51.9%) ⭐ **IMPORTANTE PARA BÚSQUEDAS**
   - Nombre de la columna en la base de datos (en inglés)
   - 840 valores únicos
   - Longitud promedio: 30.7 caracteres
   - Ejemplo: "Person ID", "Person Full Name (Bussiness Name)"
   - **Nota**: Los usuarios frecuentemente buscan etiquetas por este campo técnico

6. **Tipo Dato** (847 valores no nulos - 51.5%)
   - Tipo de dato: 1 o 2
   - Distribución: 675 valores tipo 1, 171 valores tipo 2

7. **Longitud** (860 valores no nulos - 52.3%)
   - Longitud del campo
   - Rango: 0 - 77 caracteres
   - Promedio: 36.9 caracteres

8. **Query** (846 valores no nulos - 51.5%)
   - Query SQL para insertar en catInformation
   - 846 valores únicos
   - Longitud promedio: 81.4 caracteres
   - Ejemplo: `insert into catInformation select 101,'Numero de Persona Asignado por el sistema',0,2`

## 🔍 Análisis de Calidad de Datos

### Completitud por Columna

| Columna | Valores No Nulos | Porcentaje | Útil para Vectorización |
|---------|------------------|------------|-------------------------|
| Numero | 1,549 | 94.3% | ✅ (metadatos) |
| Etiqueta | 1,281 | 78.0% | ✅ (texto clave) |
| Descripcion | 1,431 | 87.1% | ✅✅ (texto principal) |
| CLIENTE QUE LA TIENE | 4 | 0.2% | ❌ (muy pocos datos) |
| Desc Tabla | 852 | 51.9% | ✅✅ (texto clave - búsquedas frecuentes) |
| Tipo Dato | 847 | 51.5% | ⚠️ (metadatos) |
| Longitud | 860 | 52.3% | ⚠️ (metadatos) |
| Query | 846 | 51.5% | ✅ (texto técnico) |

### Observaciones Importantes

- **Filas con datos completos**: Aproximadamente 846 filas tienen todos los campos principales (Numero, Etiqueta, Descripcion, Desc Tabla, Query)
- **Filas parciales**: Hay ~361 filas sin Etiqueta, ~211 sin Descripcion
- **Columna CLIENTE QUE LA TIENE**: Prácticamente vacía, puede ignorarse para vectorización

## 🎯 Estrategia de Vectorización Recomendada

### 1. Campos para Vectorizar (Prioridad)

#### Alta Prioridad ⭐
- **Descripcion**: Texto principal en español, más completo (87.1% de completitud)
- **Desc Tabla**: ⭐ **CRÍTICO** - Nombre técnico en inglés, los usuarios frecuentemente buscan por este campo (51.9% de completitud pero muy buscado)
- **Etiqueta**: Código identificador que puede ser útil para búsquedas exactas

#### Media Prioridad
- **Query**: Contiene información técnica pero puede ser redundante con Descripcion

#### Baja Prioridad / Metadatos
- **Numero**: ID numérico (no vectorizar, usar como metadato)
- **Tipo Dato**: Categoría simple (no vectorizar, usar como filtro)
- **Longitud**: Valor numérico (no vectorizar, usar como metadato)

### 2. Texto Combinado para Embedding

Para cada fila, crear un texto combinado que **dé prominencia a Desc Tabla**:

**Formato Principal (Recomendado):**
```
"Desc Tabla: [Desc Tabla] | Etiqueta: [Etiqueta] | Descripcion: [Descripcion]"
```

Ejemplo:
```
"Desc Tabla: Person ID | Etiqueta: [i101: PID] | Descripcion: Numero de Persona Asignado por el sistema"
```

**Alternativa (si Desc Tabla está vacío):**
```
"[Etiqueta] - Descripcion"
```

**Ventajas de este formato:**
- ⭐ **Desc Tabla al inicio** - Mayor peso en el embedding para búsquedas por nombre técnico
- Combina información en español e inglés de forma balanceada
- Incluye código de etiqueta para búsquedas exactas
- Mantiene contexto técnico y descriptivo
- Permite búsquedas como "Person ID", "Person Full Name", etc. con mejor precisión

**Nota**: Si una fila no tiene "Desc Tabla", usar solo "Etiqueta" y "Descripcion" pero priorizar que siempre se incluya cuando esté disponible.

### 3. Metadatos a Almacenar

Para cada vector, almacenar:
```json
{
  "numero": 101,
  "etiqueta": "[i101: PID]",
  "descripcion": "Numero de Persona Asignado por el sistema",
  "desc_tabla": "Person ID",
  "tipo_dato": 2,
  "longitud": 41,
  "query": "insert into catInformation select 101,..."
}
```

### 4. Chunking Strategy

**Opción A: Un vector por fila** (Recomendado)
- Cada etiqueta es una entidad independiente
- Texto combinado es corto (promedio ~80 caracteres)
- Permite búsqueda precisa por etiqueta específica

**Opción B: Agrupar por categorías** (Si hay muchas etiquetas relacionadas)
- Agrupar etiquetas similares (ej: todas las de "Person")
- Crear chunks más grandes con múltiples etiquetas relacionadas

### 5. Modelo de Embedding

Basado en el código existente del proyecto:
- **Modelo**: `text-embedding-ada-002` (OpenAI)
- **Dimensión**: 1536
- **Normalización**: L2 (como se hace actualmente con FAISS)

### 6. Índice Vectorial

**Recomendación**: Usar FAISS (como se hace actualmente para tickets)
- Índice: `faiss.IndexFlatL2` o `faiss.IndexIVFFlat` para mejor rendimiento
- Almacenar metadatos en archivo JSON paralelo
- Mapeo: índice FAISS → número de etiqueta

## 📝 Ejemplo de Implementación

### Estructura de Datos Vectorizada

```python
# Texto para embedding - Priorizando Desc Tabla
if pd.notna(row['Desc Tabla']) and str(row['Desc Tabla']).strip():
    # Formato principal: Desc Tabla primero para mejor matching
    text_to_embed = f"Desc Tabla: {row['Desc Tabla']} | Etiqueta: {row['Etiqueta']} | Descripcion: {row['Descripcion']}"
else:
    # Fallback si no hay Desc Tabla
    text_to_embed = f"{row['Etiqueta']} - {row['Descripcion']}"

# Metadatos
metadata = {
    "numero": row['Numero'],
    "etiqueta": row['Etiqueta'],
    "descripcion": row['Descripcion'],
    "desc_tabla": row['Desc Tabla'],  # ⭐ Campo crítico para búsquedas
    "tipo_dato": row['Tipo Dato'],
    "longitud": row['Longitud'],
    "query": row['Query']
}
```

### Búsqueda Vectorial

Cuando un usuario pregunta:
- "¿Qué etiqueta corresponde a Person ID?" ⭐ (búsqueda por Desc Tabla)
- "Buscar etiquetas relacionadas con nombres de personas"
- "Etiqueta para número de identificación"
- "Person Full Name" ⭐ (búsqueda directa por Desc Tabla)
- "Person Type Label" ⭐ (búsqueda técnica por nombre de columna)

El sistema:
1. Genera embedding de la pregunta
2. Busca en FAISS los k vectores más cercanos
3. Retorna las etiquetas con sus metadatos completos

## ⚠️ Consideraciones Especiales

1. **Filas incompletas**: 
   - Priorizar filas con "Desc Tabla" completo (51.9% tienen este campo)
   - Para filas sin "Desc Tabla", usar formato alternativo pero incluir en el índice
   
2. **Desc Tabla es crítico**: 
   - ⭐ Muchos usuarios buscan por nombre técnico de columna (Desc Tabla)
   - Asegurar que este campo tenga prominencia en el texto vectorizado
   - Considerar búsqueda exacta adicional por "Desc Tabla" como complemento
   
3. **Duplicados**: Verificar si hay etiquetas duplicadas (parece que no, basado en valores únicos)
4. **Actualizaciones**: Planificar cómo actualizar el índice cuando cambie el Excel
5. **Búsqueda híbrida**: 
   - Combinar búsqueda vectorial con búsqueda exacta por:
     - Código de etiqueta (ej: "[i101: PID]")
     - Desc Tabla (ej: "Person ID")
     - Número de etiqueta

## 🚀 Próximos Pasos

1. ✅ Análisis de estructura completado
2. ⏳ Crear script de vectorización
3. ⏳ Generar embeddings con OpenAI
4. ⏳ Crear índice FAISS
5. ⏳ Implementar tool de búsqueda (similar a `search_knowledge` de tickets)
6. ⏳ Integrar en el sistema de tools del bot

