from __future__ import annotations

import json

from flask import abort, render_template

from config import (
    FRONTEND_ASSETS_URL_PREFIX,
    FRONTEND_DIST_DIR,
    FRONTEND_ENTRY_KEY,
    FRONTEND_LEGACY_PREFIX,
    FRONTEND_MANIFEST_PATH,
)


def _load_frontend_manifest() -> dict:
    if not FRONTEND_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "Brak manifestu frontendu. Uruchom `npm run build` w katalogu frontend."
        )
    return json.loads(FRONTEND_MANIFEST_PATH.read_text(encoding="utf-8"))


def _get_frontend_entry_assets() -> dict:
    manifest = _load_frontend_manifest()
    entry = manifest.get(FRONTEND_ENTRY_KEY)
    if not isinstance(entry, dict):
        raise KeyError(f"Brak entry `{FRONTEND_ENTRY_KEY}` w manifeście frontendu.")
    script_file = entry.get("file")
    if not isinstance(script_file, str) or not script_file:
        raise KeyError("Manifest frontendu nie zawiera pliku JS dla entrypointu.")
    css_files = entry.get("css")
    if not isinstance(css_files, list):
        css_files = []
    return {
        "script_url": f"{FRONTEND_ASSETS_URL_PREFIX}/{script_file}",
        "css_urls": [
            f"{FRONTEND_ASSETS_URL_PREFIX}/{css_file}"
            for css_file in css_files
            if isinstance(css_file, str)
        ],
    }


def _render_frontend_shell(*, bootstrap_payload: dict, title: str) -> str:
    try:
        assets = _get_frontend_entry_assets()
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        abort(503, description=str(exc))
    return render_template(
        "react_shell.html",
        page_title=title,
        bootstrap_payload=bootstrap_payload,
        frontend_script_url=assets["script_url"],
        frontend_css_urls=assets["css_urls"],
    )


def _render_legacy_template(template_name: str, **context) -> str:
    return render_template(
        template_name,
        legacy_base_path=FRONTEND_LEGACY_PREFIX,
        **context,
    )
