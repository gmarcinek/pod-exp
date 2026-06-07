from __future__ import annotations

from flask import request

from models_catalog import _build_current_models
from storage import _list_agents, _load_debate_record, _load_debates_index


def _build_bootstrap_payload(*, route: str, initial_data: dict, app_base_path: str = "") -> dict:
    return {
        "route": route,
        "apiBaseUrl": request.script_root or "",
        "appBasePath": app_base_path,
        "initialData": initial_data,
    }


def _build_home_bootstrap_payload(*, app_base_path: str = "") -> dict:
    return _build_bootstrap_payload(
        route="home",
        app_base_path=app_base_path,
        initial_data={
            "agents": _list_agents(),
            "models": _build_current_models(),
            "debates": _load_debates_index(),
        },
    )


def _build_debates_bootstrap_payload(*, app_base_path: str = "") -> dict:
    return _build_bootstrap_payload(
        route="debates",
        app_base_path=app_base_path,
        initial_data={
            "debates": _load_debates_index(),
        },
    )


def _build_new_debate_bootstrap_payload(*, app_base_path: str = "") -> dict:
    return _build_bootstrap_payload(
        route="new-debate",
        app_base_path=app_base_path,
        initial_data={
            "agents": _list_agents(),
            "models": _build_current_models(),
        },
    )


def _build_debate_view_bootstrap_payload(debate_id: str, *, app_base_path: str = "") -> dict | None:
    debate = _load_debate_record(debate_id)
    if debate is None:
        return None
    return _build_bootstrap_payload(
        route="debate-view",
        app_base_path=app_base_path,
        initial_data={
            "agents": _list_agents(),
            "models": _build_current_models(),
            "debate": debate,
        },
    )


def _build_federation_view_bootstrap_payload(federation_id: str) -> dict | None:
    record = _load_debate_record(federation_id)
    if record is None or str(record.get("type") or "") != "federation":
        return None
    transcript = list(record.get("transcript") or [])
    return _build_bootstrap_payload(
        route="federation-view",
        initial_data={
            "record": {
                "id": str(record.get("id") or ""),
                "timestamp": str(record.get("timestamp") or ""),
                "topic": str(record.get("topic") or ""),
                "agents": list(record.get("agents") or []),
                "model": str(record.get("model") or record.get("model1") or ""),
                "transcript": transcript,
                "live_notes": record.get("live_notes"),
                "summary": str(record.get("summary") or ""),
                "total_steps": int(record.get("total_steps") or len(transcript)),
            },
        },
    )
