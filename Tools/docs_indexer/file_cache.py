# Tools/docs_indexer/file_cache.py
# Sistema de caché para rastrear archivos ya procesados
# Evita re-indexar documentos que no han cambiado

import os
import json
from typing import Dict, Set, Optional, Any, List
from datetime import datetime

from .utils import file_sha256


def _file_cache_path(out_dir: str, universe: str) -> str:
    """Retorna la ruta del archivo de caché de archivos procesados para un universo."""
    return os.path.join(out_dir, f"docs_{universe}_file_cache.json")


def load_file_cache(out_dir: str, universe: str) -> Dict[str, Dict[str, Any]]:
    """
    Carga el caché de archivos procesados desde un archivo JSON.
    Returns: dict con clave = path_relativo o path_absoluto, valor = {"sha256": str, "processed_at": str}
    """
    p = _file_cache_path(out_dir, universe)
    if not os.path.exists(p):
        return {}
    
    cache: Dict[str, Dict[str, any]] = {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Compatibilidad: si es una lista antigua, convertir a dict
            if isinstance(data, list):
                cache = {item["path"]: item for item in data if "path" in item}
            else:
                cache = data
    except Exception:
        return {}
    
    return cache


def save_file_cache(out_dir: str, universe: str, cache: Dict[str, Dict[str, Any]]) -> None:
    """Guarda el caché de archivos procesados."""
    os.makedirs(out_dir, exist_ok=True)
    p = _file_cache_path(out_dir, universe)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def is_file_processed(
    file_path: str,
    cache: Dict[str, Dict[str, Any]],
    use_relative_path: bool = True
) -> bool:
    """
    Verifica si un archivo ya fue procesado y no ha cambiado.
    
    Args:
        file_path: Ruta absoluta o relativa del archivo
        cache: Diccionario de caché cargado
        use_relative_path: Si True, usa path relativo como clave; si False, usa absoluto
    
    Returns:
        True si el archivo ya fue procesado y su SHA256 coincide
    """
    if not os.path.exists(file_path):
        return False
    
    # Normalizar path para usar como clave
    if use_relative_path:
        # Intentar hacer relativo si es posible
        try:
            key = os.path.relpath(file_path)
        except ValueError:
            key = os.path.abspath(file_path)
    else:
        key = os.path.abspath(file_path)
    
    if key not in cache:
        return False
    
    cached_info = cache[key]
    cached_sha = cached_info.get("sha256")
    
    if not cached_sha:
        return False
    
    # Verificar que el SHA256 actual coincida
    try:
        current_sha = file_sha256(file_path)
        return current_sha == cached_sha
    except Exception:
        return False


def mark_file_processed(
    file_path: str,
    file_sha: str,
    cache: Dict[str, Dict[str, Any]],
    use_relative_path: bool = True
) -> None:
    """
    Marca un archivo como procesado en el caché.
    
    Args:
        file_path: Ruta del archivo
        file_sha: SHA256 del archivo
        cache: Diccionario de caché (se modifica in-place)
        use_relative_path: Si True, usa path relativo como clave
    """
    if use_relative_path:
        try:
            key = os.path.relpath(file_path)
        except ValueError:
            key = os.path.abspath(file_path)
    else:
        key = os.path.abspath(file_path)
    
    cache[key] = {
        "sha256": file_sha,
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "path": key
    }


def get_unprocessed_files(
    file_paths: List[str],
    cache: Dict[str, Dict[str, Any]],
    use_relative_path: bool = True
) -> List[str]:
    """
    Filtra una lista de archivos y retorna solo los que NO han sido procesados o han cambiado.
    
    Args:
        file_paths: Lista de rutas de archivos a verificar
        cache: Diccionario de caché cargado
        use_relative_path: Si True, usa path relativo como clave
    
    Returns:
        Lista de archivos que necesitan ser procesados
    """
    unprocessed = []
    
    for path in file_paths:
        if not os.path.exists(path):
            continue
        
        if not is_file_processed(path, cache, use_relative_path):
            unprocessed.append(path)
    
    return unprocessed


def get_file_cache_path(out_dir: str, universe: str) -> str:
    """Obtiene la ruta del archivo de caché (función pública)."""
    return _file_cache_path(out_dir, universe)

