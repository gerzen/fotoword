import json
from pathlib import Path
from typing import Dict, List

from fotoword_app.errors import FotowordError


def _validate_headers(name: str, headers: List[str]) -> None:
    if not isinstance(headers, list) or not headers:
        raise FotowordError(f"Agency '{name}' must define a non-empty headers list")
    if not any(str(header).lower() == "filename" for header in headers):
        raise FotowordError(f"Agency '{name}' headers must include 'filename'")


def load_config(config_path: Path) -> Dict:
    if not config_path.exists():
        raise FotowordError(f"Config file not found: {config_path}")
    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as exc:
        raise FotowordError(f"Invalid JSON in config file {config_path}: {exc}") from exc

    platforms = cfg.get("platforms")
    if isinstance(platforms, dict) and platforms:
        for platform_name, headers in platforms.items():
            _validate_headers(platform_name, headers)
        cfg.setdefault("ollama_url", "http://localhost:11434")
        return cfg

    agencies = cfg.get("agencies")
    if not isinstance(agencies, list) or not agencies:
        raise FotowordError("Config must define non-empty array: agencies, or legacy object: platforms")

    agencies_dir_name = str(cfg.get("agencies_dir", "agencies")).strip() or "agencies"
    agencies_dir = (config_path.parent / agencies_dir_name).resolve()
    loaded_platforms: Dict[str, List[str]] = {}

    for agency in agencies:
        if not isinstance(agency, str) or not agency.strip():
            raise FotowordError("Each agency name in config must be a non-empty string")
        agency_name = agency.strip().lower()
        agency_path = agencies_dir / f"{agency_name}.json"
        if not agency_path.exists():
            raise FotowordError(f"Agency config not found: {agency_path}")
        try:
            with agency_path.open("r", encoding="utf-8") as f:
                agency_cfg = json.load(f)
        except json.JSONDecodeError as exc:
            raise FotowordError(f"Invalid JSON in agency config {agency_path}: {exc}") from exc

        headers = agency_cfg.get("headers")
        _validate_headers(agency_name, headers)
        loaded_platforms[agency_name] = headers

    cfg["platforms"] = loaded_platforms
    cfg.setdefault("ollama_url", "http://localhost:11434")
    return cfg
