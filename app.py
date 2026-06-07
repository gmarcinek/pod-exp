"""
POD-EXP – Flask backend dla frontendu czatu epistemicznego.

Uruchomienie:
    python app.py
    (dostępne pod http://localhost:5000)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, send_from_directory, stream_with_context

load_dotenv()

from agents_service import (  # noqa: E402
    _list_agents_with_summaries,
    _sanitize_agent_filename,
    create_agent_profile,
)
from bootstrap_service import (
    _build_bootstrap_payload,
    _build_debate_view_bootstrap_payload,
    _build_debates_bootstrap_payload,
    _build_federation_view_bootstrap_payload,
    _build_home_bootstrap_payload,
    _build_new_debate_bootstrap_payload,
)
from client import (
    AGENTS_DIR,
    ANTHROPIC_MODEL,
    OPENAI_MODEL,
    build_system_prompt,
    call_anthropic_messages,
    call_ollama_messages,
    call_openai_messages,
    load_agent,
)
from config import (
    FRONTEND_DIST_DIR,
    FRONTEND_ASSETS_URL_PREFIX,
    FRONTEND_LEGACY_PREFIX,
    FRONTEND_PREVIEW_PREFIX,
    MODELS,
    _generate_debate_id,
)
from debate_runner import _run_debate
from debate_schema import (
    _build_debate_config,
    _build_public_debate_topic,
    _normalize_debate_setup,
)
from federation_runner import _run_federation
from tts_service import run_piper_tts
from frontend_service import _render_frontend_shell, _render_legacy_template
from live_notes import _empty_live_notes
from models_catalog import _build_current_models
from storage import _list_agents, _load_debate_record, _load_debates_index, _write_debate_snapshot

app = Flask(__name__)


@app.route("/")
def index():
    return _render_frontend_shell(
        bootstrap_payload=_build_home_bootstrap_payload(),
        title="POD-EXP",
    )


@app.route("/api/agents")
def get_agents():
    return jsonify(_list_agents())


@app.route("/api/bootstrap/home")
def get_home_bootstrap():
    return jsonify(_build_home_bootstrap_payload())


@app.route("/api/bootstrap/debates")
def get_debates_bootstrap():
    return jsonify(_build_debates_bootstrap_payload())


@app.route("/api/bootstrap/newDebate")
def get_new_debate_bootstrap():
    return jsonify(_build_new_debate_bootstrap_payload())


@app.route("/api/bootstrap/federation")
def get_federation_bootstrap():
    return jsonify(_build_bootstrap_payload(
        route="federation",
        initial_data={"agents": _list_agents(), "models": _build_current_models()},
    ))


@app.route("/api/bootstrap/debate/<debate_id>")
@app.route("/api/bootstrap/debates/<debate_id>")
def get_debate_view_bootstrap(debate_id: str):
    bootstrap_payload = _build_debate_view_bootstrap_payload(debate_id)
    if bootstrap_payload is None:
        return jsonify({"error": "Nie znaleziono debaty."}), 404

    return jsonify(bootstrap_payload)


@app.route(f"{FRONTEND_ASSETS_URL_PREFIX}/<path:asset_path>")
def frontend_assets(asset_path: str):
    return send_from_directory(FRONTEND_DIST_DIR, asset_path)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)

    agent_name: str = data.get("agent", "")
    provider: str = data.get("provider", "openai")
    model: str = data.get("model") or (OPENAI_MODEL if provider == "openai" else ANTHROPIC_MODEL)
    thinking_effort: str | None = data.get("thinking_effort") or None
    messages: list[dict] = data.get("messages", [])

    if not agent_name:
        return jsonify({"error": "Brak nazwy agenta."}), 400
    if not messages:
        return jsonify({"error": "Brak wiadomości."}), 400

    try:
        profile = load_agent(agent_name)
        system_prompt = build_system_prompt(profile)

        if provider == "openai":
            content = call_openai_messages(
                system_prompt, messages, model=model, thinking_effort=thinking_effort
            )
        elif provider == "anthropic":
            content = call_anthropic_messages(system_prompt, messages, model=model)
        elif provider == "ollama":
            content = call_ollama_messages(system_prompt, messages, model=model)
        else:
            return jsonify({"error": f"Nieznany provider: {provider}"}), 400

        return jsonify({"role": "assistant", "content": content})

    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Błąd API: {e}"}), 502


@app.route("/api/debates/start", methods=["POST"])
def create_debate_record():
    data = request.get_json(force=True)
    setup = _normalize_debate_setup(data)
    debate_id = _generate_debate_id()
    started_at = datetime.now(timezone.utc).isoformat()
    provider1 = str(data.get("provider1") or "openai")
    provider2 = str(data.get("provider2") or "openai")

    def _default_model(provider: str) -> str:
        if provider == "anthropic":
            return ANTHROPIC_MODEL
        if provider == "ollama":
            return MODELS["ollama"][0] if MODELS["ollama"] else "llama3.2"
        return OPENAI_MODEL

    model1 = str(data.get("model1") or _default_model(provider1))
    model2 = str(data.get("model2") or _default_model(provider2))
    topic = str(data.get("topic") or "").strip() or _build_public_debate_topic(setup)
    config = _build_debate_config(
        agent1=str(data.get("agent1") or ""),
        agent2=str(data.get("agent2") or ""),
        provider1=provider1,
        provider2=provider2,
        model1=model1,
        model2=model2,
        thinking_effort1=data.get("thinking_effort1") or None,
        thinking_effort2=data.get("thinking_effort2") or None,
        max_tokens1=str(data.get("max_tokens1") or "4096"),
        max_tokens2=str(data.get("max_tokens2") or "4096"),
        topic=topic,
        debate_mode=str(data.get("debate_mode") or "dialog"),
        debate_mode_custom=str(data.get("debate_mode_custom") or ""),
        max_turns=int(data.get("max_turns") or 10),
    )
    if not config["agent1"] or not config["agent2"]:
        return jsonify({"error": "Brak konfiguracji agentów."}), 400

    record = {
        "id": debate_id,
        "timestamp": started_at,
        "agent1": config["agent1"],
        "agent2": config["agent2"],
        "provider1": provider1,
        "provider2": provider2,
        "model1": model1,
        "model2": model2,
        "thinking_effort1": config["thinking_effort1"],
        "thinking_effort2": config["thinking_effort2"],
        "max_tokens1": config["max_tokens1"],
        "max_tokens2": config["max_tokens2"],
        "debate_mode": config["debate_mode"],
        "debate_mode_custom": config["debate_mode_custom"],
        "topic": topic,
        "config": config,
        "setup": setup,
        "history1": [],
        "history2": [],
        "transcript": [],
        "live_notes": _empty_live_notes(topic),
        "analysis": "",
        "analysis_json": None,
        "analysis_thinking": "",
        "summary": "",
        "summary_thinking": "",
        "continuation_of": None,
    }
    _write_debate_snapshot(record)
    return jsonify({"id": debate_id})




@app.route("/api/federation", methods=["POST"])
def federation():
    data = request.get_json(force=True)

    def generate():
        try:
            for event in _run_federation(data):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield 'data: {"type":"stream_end"}\n\n'

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/tts", methods=["POST"])
def tts():
    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "").strip()
    voice = str(body.get("voice") or "").strip() or None
    if not text:
        return jsonify({"error": "no text"}), 400
    try:
        wav = run_piper_tts(text, voice)
        return Response(wav, mimetype="audio/wav")
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debate", methods=["POST"])
def debate():
    data = request.get_json(force=True)

    def generate():
        try:
            for event in _run_debate(data):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield 'data: {"type":"stream_end"}\n\n'

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Debate archive ───────────────────────────────────────────────────────────

@app.route("/debates")
def debates_list():
    return _render_frontend_shell(
        bootstrap_payload=_build_debates_bootstrap_payload(),
        title="POD-EXP - Archiwum debat",
    )


@app.route("/federation")
def federation_page():
    return _render_frontend_shell(
        bootstrap_payload=_build_bootstrap_payload(
            route="federation",
            initial_data={"agents": _list_agents(), "models": _build_current_models()},
        ),
        title="POD-EXP - Federacja",
    )




@app.route("/federation/<federation_id>")
def federation_saved_view(federation_id: str):
    payload = _build_federation_view_bootstrap_payload(federation_id)
    if payload is None:
        from flask import redirect
        return redirect("/debates")
    return _render_frontend_shell(bootstrap_payload=payload, title="POD-EXP - Federacja")


@app.route("/api/bootstrap/federation/<federation_id>")
def get_federation_view_bootstrap(federation_id: str):
    payload = _build_federation_view_bootstrap_payload(federation_id)
    if payload is None:
        return jsonify({"error": "Nie znaleziono sesji federacji."}), 404
    return jsonify(payload)




@app.route("/agents")
def agents_view():
    return _render_frontend_shell(
        bootstrap_payload=_build_bootstrap_payload(
            route="agents",
            initial_data={"agents": _list_agents_with_summaries()},
        ),
        title="POD-EXP - Agenci",
    )


@app.route("/api/bootstrap/agents")
def get_agents_bootstrap():
    return jsonify(_build_bootstrap_payload(
        route="agents",
        initial_data={"agents": _list_agents_with_summaries()},
    ))


@app.route("/api/agents/create", methods=["POST"])
def create_agent():
    data = request.get_json(force=True)

    designation = str(data.get("designation") or "").strip()
    short_name = str(data.get("short_name") or "").strip().upper()[:12]
    filename = _sanitize_agent_filename(str(data.get("filename") or designation))
    narrative = str(data.get("narrative_identity") or "").strip()
    world = str(data.get("world_assumption") or "").strip()
    knowledge = str(data.get("knowledge_sources") or "").strip()
    truth = str(data.get("truth_criterion") or "").strip()
    rejected = str(data.get("rejected_defaults") or "").strip()
    temperament = str(data.get("temperament") or "").strip()
    federation_desc = str(data.get("federation_description") or "").strip()

    if not designation or not filename:
        return jsonify({"error": "Brak nazwy agenta."}), 400

    target_path = AGENTS_DIR / f"{filename}.json"
    if target_path.exists():
        return jsonify({"error": f"Agent '{filename}' już istnieje."}), 409

    try:
        profile = create_agent_profile(
            designation=designation,
            short_name=short_name,
            filename=filename,
            narrative=narrative,
            world=world,
            knowledge=knowledge,
            truth=truth,
            rejected=rejected,
            temperament=temperament,
            federation_desc=federation_desc,
        )
    except EnvironmentError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Błąd generowania profilu: {e}"}), 502

    AGENTS_DIR.mkdir(exist_ok=True)
    target_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = _list_agents_with_summaries()
    agent_summary = next((a for a in summary if a["name"] == filename), None)

    return jsonify({"name": filename, "agent": agent_summary})



@app.route("/newDebate")
def new_debate_view():
    return _render_frontend_shell(
        bootstrap_payload=_build_new_debate_bootstrap_payload(),
        title="POD-EXP - Nowa debata",
    )


@app.route("/debate/<debate_id>")
@app.route("/debates/<debate_id>")
def debate_view(debate_id: str):
    bootstrap_payload = _build_debate_view_bootstrap_payload(debate_id)
    if bootstrap_payload is None:
        return "Nie znaleziono debaty.", 404
    debate = bootstrap_payload["initialData"]["debate"]
    return _render_frontend_shell(
        bootstrap_payload=bootstrap_payload,
        title=f"POD-EXP - {debate['agent1']} vs {debate['agent2']}",
    )


@app.route(FRONTEND_LEGACY_PREFIX)
def legacy_index():
    return _render_legacy_template("index.html", agents=_list_agents(), models=MODELS)


@app.route(f"{FRONTEND_LEGACY_PREFIX}/debates")
def legacy_debates_list():
    return _render_legacy_template("debates.html", debates=_load_debates_index())


@app.route(f"{FRONTEND_LEGACY_PREFIX}/debates/<debate_id>")
def legacy_debate_view(debate_id: str):
    data = _load_debate_record(debate_id)
    if data is None:
        return "Nie znaleziono debaty.", 404
    return _render_legacy_template("debate_view.html", debate=data)


@app.route(FRONTEND_PREVIEW_PREFIX)
def frontend_preview_home():
    return _render_frontend_shell(
        bootstrap_payload=_build_home_bootstrap_payload(app_base_path=FRONTEND_PREVIEW_PREFIX),
        title="POD-EXP React Preview",
    )


@app.route(f"{FRONTEND_PREVIEW_PREFIX}/debates")
def frontend_preview_debates():
    return _render_frontend_shell(
        bootstrap_payload=_build_debates_bootstrap_payload(app_base_path=FRONTEND_PREVIEW_PREFIX),
        title="POD-EXP React Preview - Debates",
    )


@app.route(f"{FRONTEND_PREVIEW_PREFIX}/newDebate")
def frontend_preview_new_debate():
    return _render_frontend_shell(
        bootstrap_payload=_build_new_debate_bootstrap_payload(app_base_path=FRONTEND_PREVIEW_PREFIX),
        title="POD-EXP React Preview - New Debate",
    )


@app.route(f"{FRONTEND_PREVIEW_PREFIX}/debate/<debate_id>")
@app.route(f"{FRONTEND_PREVIEW_PREFIX}/debates/<debate_id>")
def frontend_preview_debate_view(debate_id: str):
    bootstrap_payload = _build_debate_view_bootstrap_payload(
        debate_id,
        app_base_path=FRONTEND_PREVIEW_PREFIX,
    )
    if bootstrap_payload is None:
        return "Nie znaleziono debaty.", 404

    return _render_frontend_shell(
        bootstrap_payload=bootstrap_payload,
        title="POD-EXP React Preview - Debate View",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
