# Tools/etiquetas_indexer/config.py
# Configuración y constantes para el indexador de etiquetas

# Nombre del universo
UNIVERSE_NAME = "etiquetas"

# Archivo Excel de entrada
DEFAULT_EXCEL_PATH = "knowledgebase/etiquetas/Etiquetas ZELL V1.xlsx"

# Nombres de columnas esperadas en el Excel
COL_NUMERO = "Numero"
COL_ETIQUETA = "Etiqueta"
COL_DESCRIPCION = "Descripcion"
COL_CLIENTE = "CLIENTE QUE LA TIENE"
COL_DESC_TABLA = "Desc Tabla"
COL_TIPO_DATO = "Tipo Dato"
COL_LONGITUD = "Longitud"
COL_QUERY = "Query"

# Fila donde están los encabezados (0-indexed, después de saltar filas vacías)
EXCEL_HEADER_ROW = 7

