import pandas as pd
import os
import re
from datetime import datetime
import csv

# Paths relativos
CONV_LOG_PATH = "logs/conversation_log.csv"
OPENAI_LOG_PATH = "logs/openai_calls.csv"
OUTPUT_DIR = "logs/indicadores"

# Costo por 1000 tokens de GPT-4o-mini
COSTO_PROMPT = 0.0005
COSTO_COMPLETION = 0.0015

# Crear carpeta si no existe
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Función para agregar fila TOTAL
# ─────────────────────────────────────────────────────────────────────────────
def add_summary_row(csv_file_path, columns_to_sum, label_col, label_value="TOTAL"):
    """
    Lee el csv, suma las columnas numéricas indicadas en 'columns_to_sum',
    elimina cualquier fila anterior que tuviera 'label_value' en 'label_col',
    agrega una nueva fila con esa misma etiqueta y con los totales.
    """
    if not os.path.isfile(csv_file_path):
        print(f"No existe el archivo {csv_file_path}, no se pudo agregar fila TOTAL.")
        return

    # Cargamos todo el CSV en memoria
    with open(csv_file_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Sumar las columnas de interés
    sums = {col: 0.0 for col in columns_to_sum}
    cleaned_rows = []

    for row in rows:
        # Si ya existiera una fila con label_value, la saltamos
        if row.get(label_col, "") == label_value:
            continue

        cleaned_rows.append(row)
        # Intentamos sumar las columnas que nos interesan
        for col in columns_to_sum:
            try:
                sums[col] += float(row[col])
            except (ValueError, KeyError):
                pass

    # Construimos la fila final con los totales
    total_row = {fn: "" for fn in fieldnames}  # fila "vacía"
    # Etiqueta en la columna que definimos
    if label_col in total_row:
        total_row[label_col] = label_value

    # Ponemos cada suma en su columna
    for col in columns_to_sum:
        if col in total_row:
            total_row[col] = str(sums[col])

    # Reescribir el CSV
    with open(csv_file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in cleaned_rows:
            writer.writerow(row)
        writer.writerow(total_row)


# ───────────────────────────────
# Procesar conversation_log
# ───────────────────────────────
df_conv = pd.read_csv(CONV_LOG_PATH, parse_dates=["timestamp"])
df_conv["date"] = df_conv["timestamp"].dt.date

# Conversaciones únicas por día: (date, conversation_id)
conv_por_dia = df_conv.groupby("date")["conversation_id"].nunique().reset_index()
conv_por_dia.columns = ["fecha", "conversaciones_unicas"]

# ───────────────────────────────
# Procesar openai_calls
# ───────────────────────────────
df_openai = pd.read_csv(OPENAI_LOG_PATH, parse_dates=["timestamp"])

# Extraer tokens del texto
def extract_token_value(text, token_type):
    match = re.search(fr"{token_type}=(\d+)", str(text))
    return int(match.group(1)) if match else 0

df_openai["prompt_tokens"] = df_openai["token_usage"].apply(lambda x: extract_token_value(x, "prompt_tokens"))
df_openai["completion_tokens"] = df_openai["token_usage"].apply(lambda x: extract_token_value(x, "completion_tokens"))
df_openai["total_tokens"] = df_openai["prompt_tokens"] + df_openai["completion_tokens"]
df_openai["costo_usd"] = (
    df_openai["prompt_tokens"] / 1000 * COSTO_PROMPT +
    df_openai["completion_tokens"] / 1000 * COSTO_COMPLETION
)
df_openai["fecha"] = df_openai["timestamp"].dt.date

# ───────────────────────────────
# Indicadores por día
# ───────────────────────────────
llamados_por_dia = df_openai.groupby("fecha").size().reset_index(name="llamados_openai")
tokens_por_dia = df_openai.groupby("fecha")[["total_tokens", "costo_usd"]].sum().reset_index()

indicadores_dia = conv_por_dia \
    .merge(llamados_por_dia, on="fecha", how="outer") \
    .merge(tokens_por_dia, on="fecha", how="outer") \
    .fillna(0)

# Ajustar tipos
indicadores_dia["conversaciones_unicas"] = indicadores_dia["conversaciones_unicas"].astype(int)
indicadores_dia["llamados_openai"] = indicadores_dia["llamados_openai"].astype(int)

# Reordenar
indicadores_dia = indicadores_dia[["fecha", "conversaciones_unicas", "llamados_openai", "total_tokens", "costo_usd"]]

# ───────────────────────────────
# Indicadores por conversación
# ───────────────────────────────
tokens_conversacion = df_openai.groupby(["fecha", "conversation_id"])[["total_tokens", "costo_usd"]].sum().reset_index()
llamados_conversacion = df_openai.groupby("conversation_id").size().reset_index(name="llamados_openai")

indicadores_conversacion = tokens_conversacion.merge(llamados_conversacion, on="conversation_id")
indicadores_conversacion = indicadores_conversacion[["fecha", "conversation_id", "total_tokens", "costo_usd", "llamados_openai"]]

# ───────────────────────────────
# Guardar archivos
# ───────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)

path_dia = f"{OUTPUT_DIR}/indicadores_por_dia.csv"
path_conv = f"{OUTPUT_DIR}/indicadores_por_conversacion.csv"

indicadores_dia.to_csv(path_dia, index=False)
indicadores_conversacion.to_csv(path_conv, index=False)

# ───────────────────────────────
# Agregar fila TOTAL
# ───────────────────────────────
add_summary_row(
    csv_file_path=path_dia,
    columns_to_sum=["llamados_openai", "total_tokens", "costo_usd"],
    label_col="fecha",    # Etiqueta en la columna 'fecha'
    label_value="TOTAL"
)

add_summary_row(
    csv_file_path=path_conv,
    columns_to_sum=["llamados_openai", "total_tokens", "costo_usd"],
    label_col="conversation_id",  # Etiqueta en la columna 'conversation_id'
    label_value="TOTAL"
)

print("✅ Indicadores generados en logs/indicadores/")

