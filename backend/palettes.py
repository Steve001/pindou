import json
from pathlib import Path
from typing import Dict, List

DATA_FILE = Path(__file__).resolve().parent / "palettes_data.json"

_palettes: Dict = {}


def load_palettes():
    global _palettes
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            _palettes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        print(f"Warning: failed to load palettes: {e}")
        _palettes = {}


def get_palette_list() -> List[dict]:
    return [
        {"id": pid, "name": p["name"], "color_count": len(p["colors"])}
        for pid, p in _palettes.items()
    ]


def get_palette(palette_id: str):
    return _palettes.get(palette_id)


def get_color_hex_list(palette_id: str) -> List[str]:
    palette = _palettes.get(palette_id)
    if not palette:
        raise ValueError(f"未知色板: {palette_id}")
    return [c["hex"] for c in palette["colors"].values()]


def get_color_entries(palette_id: str) -> List[dict]:
    palette = _palettes.get(palette_id)
    if not palette:
        raise ValueError(f"未知色板: {palette_id}")
    return [
        {"code": code, "hex": c["hex"], "name": c["name"]}
        for code, c in palette["colors"].items()
    ]


# Load on import
load_palettes()
