from __future__ import annotations

import os

from client import OLLAMA_DEFAULT_BASE_URL, OLLAMA_DEFAULT_MODELS
from config import MODELS


def _fetch_ollama_models_live() -> list[str]:
    """Odpytuje Ollama o wszystkie pobrane modele (GET /api/tags) z 2s timeoutem."""
    raw = os.environ.get("OLLAMA_MODELS", "")
    if raw.strip():
        return [m.strip() for m in raw.split(",") if m.strip()]
    base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL)
    # Wytnij sufiks /v1, żeby trafić w korzeń Ollama API
    ollama_root = base_url.rstrip("/")
    if ollama_root.endswith("/v1"):
        ollama_root = ollama_root[:-3]
    try:
        import httpx
        resp = httpx.get(f"{ollama_root}/api/tags", timeout=2.0)
        resp.raise_for_status()
        data = resp.json()
        models = [m["name"] for m in data.get("models", []) if m.get("name")]
        return sorted(models)
    except Exception:
        return []


def _build_current_models() -> dict[str, list[str]]:
    """Buduje katalog modeli z live listą Ollama."""
    try:
        ollama = _fetch_ollama_models_live()
    except Exception:
        ollama = list(OLLAMA_DEFAULT_MODELS)
    return {
        "openai": MODELS["openai"],
        "anthropic": MODELS["anthropic"],
        "ollama": ollama,
    }
