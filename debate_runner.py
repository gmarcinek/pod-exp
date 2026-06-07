from __future__ import annotations

import json
from datetime import datetime, timezone

from client import (
    ANTHROPIC_MODEL,
    OPENAI_MODEL,
    OPENAI_MODEL_GPT55,
    build_system_prompt,
    load_agent,
    load_tool,
)
from config import ANALYSIS_MAX_RETRIES, MODELS, _generate_debate_id
from debate_schema import (
    _build_debate_config,
    _build_public_debate_topic,
    _build_setup_prompt_block,
    _normalize_debate_setup,
    _resolve_debate_mode,
    _resolve_debate_prompt_shape,
)
from live_notes import _normalize_live_notes, _resolve_turn_max_tokens, _update_live_notes
from storage import _write_debate_snapshot
from streaming import _stream_anthropic, _stream_openai, _streamer


def _run_debate(data: dict):
    a1, a2 = data["agent1"], data["agent2"]
    p1, p2 = data.get("provider1", "openai"), data.get("provider2", "openai")

    def _fallback_model(provider: str) -> str:
        if provider == "anthropic":
            return ANTHROPIC_MODEL
        if provider == "ollama":
            return MODELS["ollama"][0] if MODELS["ollama"] else "llama3.2"
        return OPENAI_MODEL

    m1 = data.get("model1") or _fallback_model(p1)
    m2 = data.get("model2") or _fallback_model(p2)
    te1, te2 = data.get("thinking_effort1") or None, data.get("thinking_effort2") or None
    raw_mt1 = data.get("max_tokens1") or "4096"
    raw_mt2 = data.get("max_tokens2") or "4096"
    mt1 = _resolve_turn_max_tokens(raw_mt1, p1)
    mt2 = _resolve_turn_max_tokens(raw_mt2, p2)
    setup = _normalize_debate_setup(data)
    topic = data.get("topic", "Czym jest prawda?") or _build_public_debate_topic(setup)
    debate_mode_label, debate_mode_locative = _resolve_debate_mode(data)
    prompt_shape = _resolve_debate_prompt_shape(data)
    max_turns = int(data.get("max_turns", 33))
    continuation_of = data.get("continuation_of") or None
    debate_id = str(data.get("debate_id") or _generate_debate_id())
    started_at = datetime.now(timezone.utc).isoformat()

    profile1 = load_agent(a1)
    profile2 = load_agent(a2)
    sys1 = build_system_prompt(profile1)
    sys2 = build_system_prompt(profile2)

    identity1 = profile1.get("agent_identity", {})
    identity2 = profile2.get("agent_identity", {})

    def _identity_label(identity: dict, fallback_name: str) -> str:
        designation = str(identity.get("designation") or "").strip()
        short_name = str(identity.get("short_name") or "").strip()
        parts = [part for part in (designation, short_name) if part]
        return " / ".join(parts) or fallback_name

    def _identity_prefix(
        own_identity: dict,
        own_fallback_name: str,
        counterpart_identity: dict,
        counterpart_fallback_name: str,
    ) -> str:
        label = _identity_label(own_identity, own_fallback_name)
        counterpart_label = _identity_label(counterpart_identity, counterpart_fallback_name)
        return (
            f'\n\nUczestniczysz w {debate_mode_locative} na temat: \u201e{topic}\u201d. '
            f'Twoja tożsamość w tej rozmowie: {label}. '
            f'Rozmowę prowadzisz z: {counterpart_label}. '
            'Adaptuj się do rozmowy, reaguj na argumenty, zadawaj pytania i odpowiadaj zgodnie ze swoim profilem. '
            'Nie wychodź poza rolę, bądź osobą, którą grasz. '
        )

    sys1 += _identity_prefix(identity1, a1, identity2, a2)
    sys2 += _identity_prefix(identity2, a2, identity1, a1)
    sys1 += _build_setup_prompt_block(setup, 1)
    sys2 += _build_setup_prompt_block(setup, 2)

    initial_h1 = [{
        "role": "user",
        "content": f'Temat: \u201e{topic}\u201d. {prompt_shape["opening"]}',
    }]
    h1: list[dict] = list(data.get("history1") or initial_h1)
    h2: list[dict] = list(data.get("history2") or [])
    transcript: list[dict] = list(data.get("transcript") or [])
    live_notes = _normalize_live_notes(data.get("live_notes"), topic)
    start_turn = len(transcript)
    total_turns = start_turn + max_turns
    debate_mode = data.get("debate_mode") or "dialog"
    debate_mode_custom = data.get("debate_mode_custom") or ""
    config = _build_debate_config(
        agent1=a1,
        agent2=a2,
        provider1=p1,
        provider2=p2,
        model1=m1,
        model2=m2,
        thinking_effort1=te1,
        thinking_effort2=te2,
        max_tokens1=str(raw_mt1),
        max_tokens2=str(raw_mt2),
        topic=topic,
        debate_mode=debate_mode,
        debate_mode_custom=debate_mode_custom,
        max_turns=max_turns,
    )

    def build_record(
        *,
        analysis: str = "",
        analysis_json: dict | None = None,
        analysis_thinking: str = "",
        summary: str = "",
        summary_thinking: str = "",
        summary_error: str | None = None,
    ) -> dict:
        return {
            "id": debate_id,
            "timestamp": started_at,
            "agent1": a1,
            "agent2": a2,
            "provider1": p1,
            "provider2": p2,
            "model1": m1,
            "model2": m2,
            "thinking_effort1": te1,
            "thinking_effort2": te2,
            "max_tokens1": str(raw_mt1),
            "max_tokens2": str(raw_mt2),
            "debate_mode": debate_mode_label,
            "debate_mode_custom": debate_mode_custom,
            "topic": topic,
            "config": config,
            "setup": setup,
            "history1": h1,
            "history2": h2,
            "transcript": transcript,
            "live_notes": live_notes,
            "analysis": analysis,
            "analysis_json": analysis_json,
            "analysis_thinking": analysis_thinking,
            "summary": summary,
            "summary_thinking": summary_thinking,
            "summary_error": summary_error,
            "continuation_of": continuation_of,
        }

    for offset in range(max_turns):
        turn = start_turn + offset
        is1 = (turn % 2 == 0)
        name = a1 if is1 else a2
        prov = p1 if is1 else p2
        model = m1 if is1 else m2
        te = te1 if is1 else te2
        mt = mt1 if is1 else mt2
        hist = h1 if is1 else h2
        sys = sys1 if is1 else sys2

        yield {"type": "turn_start", "agent": name, "turn": turn + 1, "total": total_turns}

        full = ""
        turn_thinking = ""
        for ev in _streamer(prov)(sys, hist, model, te, max_tokens=mt):
            if ev["type"] == "thinking":
                turn_thinking += ev["delta"]
                yield {"type": "thinking", "agent": name, "delta": ev["delta"]}
            elif ev["type"] == "text":
                full += ev["delta"]
                yield {"type": "text", "agent": name, "delta": ev["delta"]}
            elif ev["type"] == "done":
                full = ev.get("content", full)

        transcript.append({"agent": name, "content": full, "thinking": turn_thinking})

        try:
            live_notes = _update_live_notes(topic, transcript, live_notes)
            yield {"type": "live_notes", "turn": turn + 1, "data": live_notes}
        except Exception as e:
            yield {"type": "live_notes_error", "message": str(e), "turn": turn + 1}

        if is1:
            h1.append({"role": "assistant", "content": full})
            if h2:
                h2.append({"role": "user", "content": full})
            else:
                h2 = [{
                    "role": "user",
                    "content": (
                        f'Temat: \u201e{topic}\u201d. '
                        f'{prompt_shape["counterpart_label"]}: \u201e{full}\u201d. '
                        f'{prompt_shape["response"]}'
                    ),
                }]
        else:
            h2.append({"role": "assistant", "content": full})
            h1.append({"role": "user", "content": full})

        _write_debate_snapshot(build_record())
        yield {"type": "turn_end", "agent": name, "turn": turn + 1, "total": total_turns}

    # ANALIZATOR
    yield {"type": "analysis_start"}

    analyser_profile = load_tool("_analyser")
    analyser_sys = build_system_prompt(analyser_profile)

    tx_lines = [f"[wymiana {i+1}] {t['agent'].upper()}: {t['content']}" for i, t in enumerate(transcript)]
    tx = "\n\n".join(tx_lines)

    try:
        p1_data = json.dumps(load_agent(a1), ensure_ascii=False, indent=2)
        p2_data = json.dumps(load_agent(a2), ensure_ascii=False, indent=2)
        profiles_ctx = f"\n\n=== PROFIL {a1.upper()} (agent_1) ===\n{p1_data}\n\n=== PROFIL {a2.upper()} (agent_2) ===\n{p2_data}"
    except Exception:
        profiles_ctx = ""

    user_msg = (
        f"Agenci: {a1} (agent_1) i {a2} (agent_2)\n"
        f"Tryb rozmowy: \"{debate_mode_label}\"\n"
        f"Temat debaty: \"{topic}\"\n"
        f"Liczba wymian: {len(transcript)}"
        f"{profiles_ctx}\n\n"
        f"=== TRANSKRYPT ===\n\n{tx}"
    )
    analyser_msgs = [{"role": "user", "content": user_msg}]
    analysis_text = ""
    analysis_thinking = ""
    analysis_json = None
    analysis_error = None

    for attempt in range(1, ANALYSIS_MAX_RETRIES + 1):
        analysis_text = ""
        analysis_thinking = ""
        try:
            if p1 != "anthropic":
                analysis_iter = _stream_openai(
                    analyser_sys, analyser_msgs, OPENAI_MODEL_GPT55, None,
                    response_format={"type": "json_object"},
                )
            else:
                analysis_iter = _stream_anthropic(
                    analyser_sys, analyser_msgs, OPENAI_MODEL_GPT55, None,
                    prefill="{",
                )
            for ev in analysis_iter:
                if ev["type"] == "thinking":
                    analysis_thinking += ev["delta"]
                elif ev["type"] == "text":
                    analysis_text += ev["delta"]
                    yield {"type": "analysis_text", "delta": ev["delta"]}
            analysis_error = None
            break
        except Exception as e:
            analysis_error = str(e)
            yield {
                "type": "analysis_retry",
                "attempt": attempt,
                "max_attempts": ANALYSIS_MAX_RETRIES,
                "message": analysis_error,
            }

    if analysis_error:
        yield {
            "type": "analysis_skipped",
            "message": analysis_error,
            "attempts": ANALYSIS_MAX_RETRIES,
        }

    yield {"type": "analysis_done"}

    if not analysis_error:
        try:
            analysis_json = json.loads(analysis_text)
            yield {"type": "analysis_json", "data": analysis_json}
        except Exception:
            analysis_json = None

    # SUMMARISER
    yield {"type": "summary_start"}

    summariser_profile = load_tool("_sumariser")
    summariser_sys = build_system_prompt(summariser_profile)
    notes_json = json.dumps(live_notes, ensure_ascii=False, indent=2)
    analysis_json_str = json.dumps(analysis_json, ensure_ascii=False, indent=2) if analysis_json else "null"
    summariser_msg = (
        f"Agenci: {a1} i {a2}\n"
        f"Tryb rozmowy: \"{debate_mode_label}\"\n"
        f"Temat: \"{topic}\"\n"
        f"Liczba wymian: {len(transcript)}\n\n"
        f"=== TRANSKRYPT ===\n{tx}\n\n"
        f"=== ANALIZA KARTOGRAFA (tekst) ===\n{analysis_text or '[brak]'}\n\n"
        f"=== ANALIZA KARTOGRAFA (json) ===\n{analysis_json_str}\n\n"
        f"=== SZYBKIE NOTATKI I FISZKI ===\n{notes_json}"
    )
    summariser_msgs = [{"role": "user", "content": summariser_msg}]
    summary_text = ""
    summary_thinking = ""
    summary_error = None

    try:
        if p1 != "anthropic":
            summary_iter = _stream_openai(summariser_sys, summariser_msgs, OPENAI_MODEL_GPT55, None)
        else:
            summary_iter = _stream_anthropic(summariser_sys, summariser_msgs, OPENAI_MODEL_GPT55, None)
        for ev in summary_iter:
            if ev["type"] == "thinking":
                summary_thinking += ev["delta"]
            elif ev["type"] == "text":
                summary_text += ev["delta"]
                yield {"type": "summary_text", "delta": ev["delta"]}
    except Exception as e:
        summary_error = str(e)
        yield {"type": "summary_error", "message": summary_error}

    yield {"type": "summary_done"}

    _write_debate_snapshot(
        build_record(
            analysis=analysis_text,
            analysis_json=analysis_json,
            analysis_thinking=analysis_thinking,
            summary=summary_text,
            summary_thinking=summary_thinking,
            summary_error=summary_error,
        )
    )
    yield {
        "type": "saved",
        "id": debate_id,
        "config": config,
        "continuation": {
            "history1": h1,
            "history2": h2,
            "transcript": transcript,
            "live_notes": live_notes,
            "turns_completed": len(transcript),
        },
    }
