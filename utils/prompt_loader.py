import os
import re
import logging

def load_latest_prompt(tool_folder: str,
                       base_pattern: str,
                       with_filename: bool = False):
    """
    Busca en Prompts/{tool_folder} el archivo {base_pattern}_vN.txt de mayor N.
    Si `with_filename=True` devuelve (contenido, nombre_de_archivo),
    de lo contrario solo el contenido.
    """
    folder_path = os.path.join("Prompts", tool_folder)
    if not os.path.isdir(folder_path):
        logging.error(f"❌ Carpeta no existe: {folder_path}")
        if with_filename:
            return None, "N/A"
        return None

    # Regex para capturar la versión después de _v
    rgx = re.compile(rf"^{base_pattern}_v(\d+)\.txt$", re.IGNORECASE)
    candidates = []
    for fname in os.listdir(folder_path):
        m = rgx.match(fname)
        if m:
            version = int(m.group(1))
            candidates.append((version, fname))

    if not candidates:
        logging.error(f"⚠️ No hay prompts que cumplan patrón en {folder_path}")
        if with_filename:
            return None, "N/A"
        return None

    # Elige el mayor
    _, latest_file = max(candidates, key=lambda x: x[0])
    path = os.path.join(folder_path, latest_file)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logging.error(f"❌ Error leyendo prompt {path}: {e}")
        if with_filename:
            return None, latest_file
        return None

    if with_filename:
        return content, latest_file
    return content
