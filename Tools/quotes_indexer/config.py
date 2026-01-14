# Tools/quotes_indexer/config.py
# Configuración y constantes para el indexador de cotizaciones

# Nombre del universo
UNIVERSE_NAME = "quotes"

# Archivo Excel de entrada
DEFAULT_EXCEL_PATH = "knowledgebase/quotes/cotizaciones-13-enero.xlsx"

# Nombres de columnas esperadas en el Excel
COL_ISSUE_ID = "iIssueId"
COL_QUOTE_ID = "iQuoteId"
COL_TITLE = "vTitle"
COL_UNITS = "iUnits"
COL_PAYMENT_DATE = "fPaymentDate"
COL_DESCRIPTIONS = "Descriptions"

# Fila donde están los encabezados (0-indexed)
EXCEL_HEADER_ROW = 0

