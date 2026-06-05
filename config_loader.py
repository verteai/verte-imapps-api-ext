"""Load configuration from config.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_config() -> dict:
    config_file = Path(__file__).resolve().parent / "config.py"
    if not config_file.is_file():
        raise FileNotFoundError(
            "config.py not found. Copy config.example.py to config.py and set your p_access_key."
        )

    spec = importlib.util.spec_from_file_location("verte_config", config_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {config_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "CONFIG"):
        raise RuntimeError("config.py must define a CONFIG dict.")

    return module.CONFIG
