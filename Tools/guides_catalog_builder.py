# Tools/guides_catalog_builder.py
# Construye catálogo de guías de usuario desde Excel/CSV maestro
# Columnas esperadas: t, NOMBRE, OBJETIVO, REFERENCIA CLIENTE / TICKET, etc.

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


# Regex para extraer número de documento del título: "(1) Zell - Nombre"
TITLE_NUMBER_RE = re.compile(r"^\((\d+)\)\s+Zell\s+-\s+(.+)$", re.IGNORECASE)


def _to_iso_date(x):
    """Convierte fecha a formato ISO YYYY-MM-DD."""
    if pd.isna(x):
        return None
    try:
        # pandas Timestamp o datetime
        return pd.to_datetime(x).date().isoformat()
    except Exception:
        # Intentar parsear formato DD/MM/YYYY o MM/DD/YYYY
        try:
            return pd.to_datetime(str(x), dayfirst=True).date().isoformat()
        except Exception:
            return str(x) if x else None


def extract_number_from_title(title: str) -> tuple[Optional[int], str]:
    """
    Extrae número de documento y nombre limpio del título.
    Ej: "(1) Zell - Reintentos de domiciliación" -> (1, "Reintentos de domiciliación")
    """
    if pd.isna(title):
        return None, ""
    
    title_str = str(title).strip()
    m = TITLE_NUMBER_RE.match(title_str)
    if m:
        doc_number = int(m.group(1))
        clean_name = m.group(2).strip()
        return doc_number, clean_name
    
    # Si no coincide el patrón, intentar extraer número al inicio
    m = re.match(r"^\((\d+)\)", title_str)
    if m:
        doc_number = int(m.group(1))
        # Remover patrón inicial si existe
        clean_name = re.sub(r"^\(\d+\)\s*Zell\s*-\s*", "", title_str, flags=re.IGNORECASE).strip()
        return doc_number, clean_name
    
    return None, title_str


def load_master_xlsx(xlsx_path: str) -> pd.DataFrame:
    """
    Carga el Excel maestro de guías.
    Espera columnas: t, NOMBRE, OBJETIVO, REFERENCIA CLIENTE / TICKET, etc.
    """
    try:
        # Convertir a Path para manejar mejor encoding de nombres
        xlsx_file = Path(xlsx_path)
        if not xlsx_file.exists():
            # Buscar archivos usando os.listdir (mejor para encoding)
            import os
            current_dir = os.path.dirname(os.path.abspath(xlsx_path)) if os.path.dirname(xlsx_path) else "."
            all_files = [f for f in os.listdir(current_dir) if f.endswith('.xlsx')]
            # Buscar archivo que contenga "LISTADO" y que NO sea "F-SGCSI" (el otro listado)
            possible_files = [f for f in all_files if "LISTADO" in f.upper() and "F-SGCSI" not in f.upper()]
            if possible_files:
                xlsx_file = Path(current_dir) / possible_files[0]
                print(f"[guides_catalog_builder] Archivo encontrado por busqueda: {xlsx_file}")
            else:
                raise FileNotFoundError(f"No se encontro el archivo: {xlsx_path}")
        
        # Intentar leer directamente (header en primera fila)
        df = pd.read_excel(str(xlsx_file))
        
        # Normalizar nombres de columnas (eliminar espacios extra, convertir a minúsculas)
        df.columns = df.columns.str.strip()
        
        # Mapear columnas posibles
        column_mapping = {
            "t": "t",
            "número": "t",
            "numero": "t",
            "nombre": "nombre",
            "objetivo": "objetivo",
            "referencia cliente / ticket": "referencia_cliente_ticket",
            "referencia cliente/ticket": "referencia_cliente_ticket",
            "ref cliente / ticket": "referencia_cliente_ticket",
            "fecha último cambio": "fecha_ultimo_cambio",
            "fecha ultimo cambio": "fecha_ultimo_cambio",
            "último cambio": "fecha_ultimo_cambio",
            "version": "version",
            "versión": "version",
            "cambio realizado": "cambio_realizado",
            "autor/es": "autores",
            "autores": "autores",
            "verificó": "verifico",
            "asignada a": "asignada_a",
            "asignada_a": "asignada_a",
            "fecha asignación": "fecha_asignacion",
            "fecha asignacion": "fecha_asignacion",
            "fecha entregado": "fecha_entregado",
        }
        
        # Renombrar columnas según mapeo
        df = df.rename(columns={col: column_mapping.get(col.lower(), col.lower()) for col in df.columns})
        
        return df
    except Exception as e:
        raise RuntimeError(f"Error cargando Excel: {e}")


def build_guides_catalog(df: pd.DataFrame) -> dict:
    """
    Construye catálogo de guías desde DataFrame.
    Usa número de documento (t) o extraído del título como clave.
    """
    catalog = {}

    for _, row in df.iterrows():
        # Intentar obtener número de documento desde columna 't' o extraer del título
        doc_number = None
        nombre = None
        
        if "t" in row and not pd.isna(row.get("t")):
            try:
                doc_number = int(row["t"])
            except (ValueError, TypeError):
                pass
        
        # Obtener nombre
        nombre_raw = row.get("nombre") or row.get("NOMBRE") or ""
        if not nombre_raw or pd.isna(nombre_raw):
            continue
        
        nombre_str = str(nombre_raw).strip()
        if not nombre_str:
            continue
        
        # Si no tenemos número de columna 't', intentar extraer del título
        if doc_number is None:
            doc_number, nombre_clean = extract_number_from_title(nombre_str)
            if doc_number:
                nombre = nombre_clean
            else:
                nombre = nombre_str
        else:
            # Ya tenemos número, limpiar nombre si tiene el patrón
            _, nombre_clean = extract_number_from_title(nombre_str)
            nombre = nombre_clean if nombre_clean else nombre_str
        
        # Usar número de documento como clave (si no hay, usar nombre normalizado)
        if doc_number is None:
            # Fallback: usar hash del nombre como clave temporal
            key = f"guide_{hash(nombre_str) % 10000}"
        else:
            key = str(doc_number)
        
        # Construir item del catálogo
        item = {
            "doc_number": doc_number,
            "nombre": nombre,
            "nombre_completo": nombre_str,  # Nombre completo del Excel
            "objetivo": None if pd.isna(row.get("objetivo")) else str(row.get("objetivo")).strip(),
            "referencia_cliente_ticket": None if pd.isna(row.get("referencia_cliente_ticket")) else str(row.get("referencia_cliente_ticket")).strip(),
            "fecha_ultimo_cambio": _to_iso_date(row.get("fecha_ultimo_cambio")),
            "version": None if pd.isna(row.get("version")) else str(row.get("version")).strip(),
            "cambio_realizado": None if pd.isna(row.get("cambio_realizado")) else str(row.get("cambio_realizado")).strip(),
            "autores": None if pd.isna(row.get("autores")) else str(row.get("autores")).strip(),
            "verifico": None if pd.isna(row.get("verifico")) else str(row.get("verifico")).strip(),
            "asignada_a": None if pd.isna(row.get("asignada_a")) else str(row.get("asignada_a")).strip(),
            "fecha_asignacion": _to_iso_date(row.get("fecha_asignacion")),
            "fecha_entregado": _to_iso_date(row.get("fecha_entregado")),
        }

        catalog[key] = item

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(catalog),
        "items": catalog,
    }


def match_guide_to_catalog(filename: str, catalog: dict) -> Optional[dict]:
    """
    Encuentra entrada del catálogo que coincida con el nombre del archivo.
    Busca por número de documento extraído del título del archivo.
    """
    # Extraer número del filename si tiene formato "(1) Zell - ..."
    doc_number, _ = extract_number_from_title(filename)
    
    if doc_number is not None:
        key = str(doc_number)
        return catalog.get(key)
    
    # Fallback: buscar por coincidencia parcial del nombre
    filename_lower = filename.lower()
    for item in catalog.values():
        nombre_lower = (item.get("nombre_completo") or "").lower()
        if nombre_lower and nombre_lower in filename_lower:
            return item
        if item.get("nombre") and item["nombre"].lower() in filename_lower:
            return item
    
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Construye catálogo de guías de usuario desde Excel maestro"
    )
    ap.add_argument("--xlsx", required=True, help="Ruta al Excel maestro (LISTADO MAESTRO DE GUÍAS)")
    ap.add_argument("--out", default="Data/guides_catalog.json", help="Salida JSON")
    args = ap.parse_args()

    df = load_master_xlsx(args.xlsx)
    catalog = build_guides_catalog(df)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"[guides_catalog_builder] OK -> {out_path} (items={catalog['count']})")
    print(f"   Ejemplo de claves: {list(catalog['items'].keys())[:5]}")


if __name__ == "__main__":
    main()

