"""Configuration: config.yaml plus environment variables."""
import copy
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def base_cfg() -> dict:
    """config.yaml as shipped (the defaults)."""
    path = Path(os.getenv("GEOMACRO_CONFIG", ROOT / "config.yaml"))
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


_merged: dict | None = None


def cfg() -> dict:
    """Defaults from config.yaml plus admin overrides stored in the database."""
    global _merged
    if _merged is None:
        from . import settings_store
        _merged = settings_store.merge(copy.deepcopy(base_cfg()))
    return _merged


def reload_cfg() -> None:
    global _merged
    _merged = None


def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def database_url() -> str:
    url = env("DATABASE_URL")
    if not url:
        return f"sqlite:///{ROOT / 'geomacro.db'}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def regions() -> dict:
    return cfg()["regions"]


def bbox(region: str):
    return cfg()["regions"][region]["bbox"]


def region_of(lat: float, lon: float):
    """Return the region key containing the point, or None."""
    for key, r in regions().items():
        la0, la1, lo0, lo1 = r["bbox"]
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return key
    return None


def label_for(score: int) -> str:
    bands = cfg()["risk_bands"]
    for name in ("avoid", "high", "caution"):
        if score >= bands[name][0]:
            return name.upper()
    return "NORMAL"


LABEL_RANK = {"NORMAL": 0, "CAUTION": 1, "HIGH": 2, "AVOID": 3}
