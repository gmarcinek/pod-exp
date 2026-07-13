from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DEBATES_DIR = Path(__file__).parent / "debates"
EDITORIAL_DB_PATH = Path(
    os.environ.get("EDITORIAL_DB_PATH") or Path(__file__).parent / "editorials.sqlite3"
)
FRONTEND_DIR = Path(__file__).parent / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_MANIFEST_PATH = FRONTEND_DIST_DIR / ".vite" / "manifest.json"
FRONTEND_ENTRY_KEY = "index.html"
FRONTEND_ASSETS_URL_PREFIX = "/frontend-assets"
FRONTEND_PREVIEW_PREFIX = "/_react-preview"
FRONTEND_LEGACY_PREFIX = "/_legacy"

MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.5",
        "gpt-5.5-mini",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ],
    "anthropic": ["claude-opus-4-6", "claude-opus-4-8", "claude-3-5-haiku-latest"],
    "ollama": [],
}

LIVE_NOTES_MODEL = "gpt-5.4-mini"
LIVE_NOTES_MAX_TOKENS = 220
LIVE_NOTES_MAX_RETRIES = 4
LIVE_NOTES_INPUT_CHARS = 1400
LIVE_FACTS_MODEL = "gpt-5.4-mini"
LIVE_FACTS_MAX_TOKENS = 220
LIVE_FACTS_MAX_RETRIES = 4
ANALYSIS_MAX_RETRIES = 5

PROVIDER_MAX_TOKENS: dict[str, int] = {
    "openai": 128000,
    "anthropic": 32000,
    "ollama": 4096,
}


def _generate_debate_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}_{uuid4().hex[:8]}"
