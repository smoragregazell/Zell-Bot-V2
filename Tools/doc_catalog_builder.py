# Tools/doc_catalog_builder.py
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


CODE_RE = re.compile(r"^[A-Z]{1,4}-[A-Z]{2,6}-\d{2}$")


def _to_iso_date(x):
    if pd.isna(x):
        return None
    try:
        # pandas Timestamp o datetime
        return pd.to_datetime(x).date().isoformat()
    except Exception:
        return str(x)


def parse_code(code: str):
    """
    Ej: P-SGSI-14 => family=P, domain=SGSI, num=14
    """
    parts = code.split("-")
    if len(parts) >= 3 and parts[-1].isdigit():
        family = parts[0]
        domain = "-".join(parts[1:-1])
        num = parts[-1]
        return family, domain, num
    return None, None, None


def load_master_xlsx(xlsx_path: str) -> pd.DataFrame:
    # En tu archivo real, el header útil empieza en la fila 8 (header=7)
    raw = pd.read_excel(xlsx_path, header=7)

    # La primer fila trae los nombres “reales” de columnas (Nombre del documento, Código, etc.)
    header_row = raw.iloc[0].tolist()
    raw.columns = header_row
    df = raw.iloc[1:].reset_index(drop=True)

    # Normaliza nombres
    df = df.rename(
        columns={
            "Nombre del documento": "titulo",
            "Fecha de emisión": "fecha_emision",
            "Código": "codigo",
            "Revisión": "revision",
            "Disposición (Documento/ Información)": "disposicion",
            "Alcance ISO*": "alcance_iso",
            "Tipo de información": "tipo_info",
            "Estatus del documento": "estatus",
        }
    )
    return df


def build_catalog(df: pd.DataFrame) -> dict:
    catalog = {}

    for _, row in df.iterrows():
        codigo = row.get("codigo")
        if pd.isna(codigo):
            continue

        codigo = str(codigo).strip()
        if not CODE_RE.match(codigo):
            continue

        family, domain, num = parse_code(codigo)

        revision = row.get("revision")
        try:
            revision = int(revision) if not pd.isna(revision) else None
        except Exception:
            revision = str(revision) if not pd.isna(revision) else None

        item = {
            "codigo": codigo,
            "family": family,
            "domain": domain,
            "num": num,
            "titulo": None if pd.isna(row.get("titulo")) else str(row.get("titulo")).strip(),
            "fecha_emision": _to_iso_date(row.get("fecha_emision")),
            "revision": revision,
            "disposicion": None if pd.isna(row.get("disposicion")) else str(row.get("disposicion")).strip(),
            "alcance_iso": None if pd.isna(row.get("alcance_iso")) else str(row.get("alcance_iso")).strip(),
            "tipo_info": None if pd.isna(row.get("tipo_info")) else str(row.get("tipo_info")).strip(),
            "estatus": None if pd.isna(row.get("estatus")) else str(row.get("estatus")).strip(),
        }

        catalog[codigo] = item

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(catalog),
        "items": catalog,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="Ruta al Excel maestro")
    ap.add_argument("--out", default="Data/doc_catalog.json", help="Salida JSON")
    args = ap.parse_args()

    df = load_master_xlsx(args.xlsx)
    catalog = build_catalog(df)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"[doc_catalog_builder] OK -> {out_path} (items={catalog['count']})")


if __name__ == "__main__":
    main()