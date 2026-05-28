"""
POD-EXP – Flask backend dla frontendu czatu epistemicznego.

Uruchomienie:
    python app.py
    (dostępne pod http://localhost:5000)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import openai
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

load_dotenv()

from client import (  # noqa: E402
    AGENTS_DIR,
    ANTHROPIC_MODEL,
    OPENAI_MODEL,
    build_system_prompt,
    call_anthropic_messages,
    call_openai_messages,
    load_agent,
    load_tool,
)

app = Flask(__name__)

DEBATES_DIR = Path(__file__).parent / "debates"

MODELS: dict[str, list[str]] = {
    "openai": ["gpt-5.4", "gpt-5.5"],
    "anthropic": ["claude-opus-4-6"],
}

LIVE_NOTES_MODEL = "gpt-5.4-mini"
LIVE_NOTES_MAX_TOKENS = 220
LIVE_NOTES_MAX_RETRIES = 4
LIVE_NOTES_INPUT_CHARS = 1400
LIVE_FACTS_MODEL = "gpt-5.4-mini"
LIVE_FACTS_MAX_TOKENS = 220
LIVE_FACTS_MAX_RETRIES = 4
ANALYSIS_MAX_RETRIES = 5
PROVIDER_MAX_TOKENS = {
    "openai": 128000,
    "anthropic": 32000,
}


def _empty_live_notes(topic: str) -> dict:
    return {
        "topic": topic,
        "entries": [],
        "fact_cards": [],
    }


def _normalize_live_notes(data: dict | None, topic: str) -> dict:
    source = data if isinstance(data, dict) else {}
    normalized = {
        "topic": source.get("topic") or topic,
        "entries": list(source.get("entries") or []),
        "fact_cards": list(source.get("fact_cards") or []),
    }
    if source.get("facts_error"):
        normalized["facts_error"] = source["facts_error"]
    return normalized


def _resolve_turn_max_tokens(raw_value, provider: str) -> int:
    text = str(raw_value or "").strip().lower()
    if not text:
        return 4096
    if text == "max":
        return PROVIDER_MAX_TOKENS.get(provider, 4096)
    try:
        return max(1, int(text))
    except (TypeError, ValueError):
        return 4096


def _clip_text(text: str, limit: int = LIVE_NOTES_INPUT_CHARS) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _generate_live_note(topic: str, transcript: list[dict], previous_notes: dict) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not transcript:
        return ""

    tool_system_prompt = build_system_prompt(load_tool("notatnik"))

    recent = transcript[-6:]
    recent_lines = "\n".join(
        f"- {item['agent']}: {_clip_text(item['content'])}"
        for item in recent
    )
    latest = transcript[-1]
    prev_entries = previous_notes.get("entries", [])[-8:]
    prev_text = "\n".join(
        f"- tura {item['turn']} / {item['agent']}: {item['note']}"
        for item in prev_entries
    ) or "- brak"
    user_prompt = (
        f"Temat debaty: {topic}\n"
        f"Dotychczasowe notatki:\n{prev_text}\n\n"
        f"Najnowszy wpis:\n- {latest['agent']}: {_clip_text(latest['content'])}\n\n"
        f"Ostatnie wymiany:\n{recent_lines}\n\n"
        "Napisz jedną krótką notatkę po polsku, maksymalnie 1-5 zdań. "
        "Zanotuj tylko nową istotną rzecz z tej tury: argument, przesunięcie sporu albo doprecyzowanie. "
        "Nie powtarzaj dosłownie poprzednich notatek i nie używaj JSON ani list."
    )

    last_error = None
    for _ in range(LIVE_NOTES_MAX_RETRIES):
        try:
            response = openai.OpenAI(api_key=api_key).chat.completions.create(
                model=LIVE_NOTES_MODEL,
                messages=[
                    {"role": "system", "content": tool_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=LIVE_NOTES_MAX_TOKENS,
                temperature=0,
            )
            payload = (response.choices[0].message.content or "").strip()
            if not payload:
                raise ValueError("Pusta odpowiedź notatek szybkich.")
            return payload
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    return ""


def _generate_live_fact_requests(topic: str, transcript: list[dict]) -> list[str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not transcript:
        return []

    tool_system_prompt = build_system_prompt(load_tool("notatnik"))

    latest = transcript[-1]
    recent = transcript[-6:]
    recent_lines = "\n".join(
        f"- {item['agent']}: {_clip_text(item['content'])}"
        for item in recent
    )
    user_prompt = (
        f"Temat debaty: {topic}\n"
        f"Najnowszy wpis:\n- {latest['agent']}: {_clip_text(latest['content'])}\n\n"
        f"Ostatnie wymiany:\n{recent_lines}\n\n"
        "Wypisz 2-3 krótkie prośby o fakty do sprawdzenia po tej turze. "
        "Każda linia ma być jedną konkretną rzeczą do weryfikacji. "
        "Pisz po polsku. Zaczynaj od czasownika, np. 'Sprawdź, czy...' lub 'Ustal, czy...'. "
        "Zwróć wyłącznie 2-3 osobne linie, bez numeracji, bez wstępu, bez JSON."
    )

    last_error = None
    for _ in range(LIVE_FACTS_MAX_RETRIES):
        try:
            response = openai.OpenAI(api_key=api_key).chat.completions.create(
                model=LIVE_FACTS_MODEL,
                messages=[
                    {"role": "system", "content": tool_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=LIVE_FACTS_MAX_TOKENS,
                temperature=0,
            )
            payload = (response.choices[0].message.content or "").strip()
            if not payload:
                raise ValueError("Pusta odpowiedź fiszek faktów.")
            lines = []
            for raw_line in payload.splitlines():
                line = raw_line.strip().lstrip("-•* ").strip()
                if line:
                    lines.append(line)
            deduped = []
            for line in lines:
                if line not in deduped:
                    deduped.append(line)
            if not deduped:
                raise ValueError("Brak poprawnych fiszek faktów.")
            return deduped[:3]
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    return []


def _update_live_notes(topic: str, transcript: list[dict], previous_notes: dict) -> dict:
    if not transcript:
        return previous_notes

    latest = transcript[-1]
    note_text = ""
    fact_requests: list[str] = []
    note_error = None
    facts_error = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        note_future = executor.submit(_generate_live_note, topic, transcript, previous_notes)
        facts_future = executor.submit(_generate_live_fact_requests, topic, transcript)
        try:
            note_text = note_future.result()
        except Exception as e:
            note_error = e
        try:
            fact_requests = facts_future.result()
        except Exception as e:
            facts_error = e

    if note_error and not note_text:
        raise note_error

    next_entries = list(previous_notes.get("entries", []))
    if note_text:
        next_entries.append({
            "turn": len(transcript),
            "agent": latest["agent"],
            "note": note_text,
        })

    next_fact_cards = list(previous_notes.get("fact_cards", []))
    for fact_request in fact_requests:
        next_fact_cards.append({
            "turn": len(transcript),
            "agent": latest["agent"],
            "request": fact_request,
        })

    updated = {
        "topic": topic,
        "entries": next_entries,
        "fact_cards": next_fact_cards,
    }
    if facts_error and not fact_requests:
        updated["facts_error"] = str(facts_error)
    return updated


@app.route("/")
def index():
    agents = sorted(p.stem for p in AGENTS_DIR.glob("*.json") if not p.stem.startswith("_"))
    return render_template("index.html", agents=agents, models=MODELS)


@app.route("/api/agents")
def get_agents():
    return jsonify(sorted(p.stem for p in AGENTS_DIR.glob("*.json") if not p.stem.startswith("_")))


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
        else:
            return jsonify({"error": f"Nieznany provider: {provider}"}), 400

        return jsonify({"role": "assistant", "content": content})

    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Błąd API: {e}"}), 502


# ── Streaming helpers ────────────────────────────────────────────────────────

def _stream_openai(
    system_prompt: str, messages: list[dict], model: str,
    thinking_effort: str | None = None, max_tokens: int | None = None,
    response_format: dict | None = None,
):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak OPENAI_API_KEY.")
    params: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
    }
    if thinking_effort:
        params["reasoning_effort"] = thinking_effort
    if max_tokens:
        params["max_completion_tokens"] = max_tokens
    if response_format:
        params["response_format"] = response_format
    full = ""
    for chunk in openai.OpenAI(api_key=api_key).chat.completions.create(**params):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if rc := getattr(delta, "reasoning_content", None):
            yield {"type": "thinking", "delta": rc}
        if delta.content:
            full += delta.content
            yield {"type": "text", "delta": delta.content}
    yield {"type": "done", "content": full}


def _stream_anthropic(
    system_prompt: str,
    messages: list[dict],
    model: str,
    thinking_effort: str | None = None,
    max_tokens: int | None = 4096,
    prefill: str | None = None,
):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak ANTHROPIC_API_KEY.")
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("user", "assistant")
    ]
    if prefill:
        clean.append({"role": "assistant", "content": prefill})
    if max_tokens is None:
        max_tokens = PROVIDER_MAX_TOKENS["anthropic"]
    params: dict = {"model": model, "max_tokens": max_tokens, "system": system_prompt, "messages": clean}
    if thinking_effort:
        budget = {"auto": 8000, "medium": 5000, "high": 10000, "low": 2000}.get(thinking_effort, 5000)
        params["thinking"] = {"type": "enabled", "budget_tokens": budget}
        params["max_tokens"] = max(params["max_tokens"], budget + 1000)
    full = prefill or ""
    if prefill:
        yield {"type": "text", "delta": prefill}
    with anthropic.Anthropic(api_key=api_key).messages.stream(**params) as stream:
        for event in stream:
            if getattr(event, "type", None) == "content_block_delta":
                d = event.delta
                if getattr(d, "type", None) == "thinking_delta":
                    yield {"type": "thinking", "delta": d.thinking}
                elif getattr(d, "type", None) == "text_delta":
                    full += d.text
                    yield {"type": "text", "delta": d.text}
    yield {"type": "done", "content": full}


def _streamer(provider: str):
    return _stream_openai if provider == "openai" else _stream_anthropic


DEBATE_MODES: dict[str, dict[str, str]] = {
    "dialog": {
        "label": "Dialog",
        "locative": "dialogu",
        "opening": "Przedstaw swoje ujęcie tematu i pierwszy istotny argument.",
        "counterpart_label": "Rozmówca",
        "response": "Odpowiedz na ostatnią wypowiedź i rozwijaj rozmowę zgodnie ze swoim profilem.",
    },
    "rozmowa": {
        "label": "Rozmowa",
        "locative": "rozmowie",
        "opening": "Przedstaw swoje ujęcie tematu i pierwszy istotny argument.",
        "counterpart_label": "Rozmówca",
        "response": "Odpowiedz na ostatnią wypowiedź i rozwijaj rozmowę zgodnie ze swoim profilem.",
    },
    "debata": {
        "label": "Debata",
        "locative": "debacie",
        "opening": "Przedstaw stanowisko i główne argumenty.",
        "counterpart_label": "Oponent",
        "response": "Odpowiedz na argumenty oponenta i broń swojego stanowiska zgodnie ze swoim profilem.",
    },
    "spor": {
        "label": "Spór",
        "locative": "sporze",
        "opening": "Przedstaw stanowisko i główne argumenty.",
        "counterpart_label": "Oponent",
        "response": "Odpowiedz na argumenty oponenta i broń swojego stanowiska zgodnie ze swoim profilem.",
    },
    "klotnia": {
        "label": "Kłótnia",
        "locative": "kłótni",
        "opening": "Przedstaw stanowisko i to, co najmocniej cię w nim porusza.",
        "counterpart_label": "Druga strona",
        "response": "Odpowiedz na ostatnią wypowiedź drugiej strony zgodnie ze swoim profilem.",
    },
    "terapia": {
        "label": "Terapia",
        "locative": "terapii",
        "opening": "Przedstaw swoje ujęcie tematu w sposób wspierający i pogłębiający rozumienie.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika w sposób pogłębiający rozumienie zgodnie ze swoim profilem.",
    },
    "konsultacja": {
        "label": "Konsultacja",
        "locative": "konsultacji",
        "opening": "Przedstaw swoje ujęcie tematu i najbardziej użyteczne rozpoznanie.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika i rozwijaj temat zgodnie ze swoim profilem.",
    },
    "wspolne_dociekanie": {
        "label": "Wspólne dociekanie",
        "locative": "wspólnym dociekaniu",
        "opening": "Przedstaw hipotezę, rozróżnienia albo pytania, które pomagają wspólnie zbadać temat.",
        "counterpart_label": "Drugi badacz",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego badacza, doprecyzuj lub rozwiń wspólne dociekanie zgodnie ze swoim profilem.",
    },
    "burza_rozwiazan": {
        "label": "Burza rozwiązań",
        "locative": "burzy rozwiązań",
        "opening": "Zaproponuj kierunek, pomysł albo rozróżnienie, które może posunąć temat do przodu.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika i zaproponuj kolejny konstruktywny krok zgodnie ze swoim profilem.",
    },
    "mentoring": {
        "label": "Mentoring",
        "locative": "mentoringu",
        "opening": "Przedstaw swoje ujęcie tematu w sposób prowadzący i objaśniający.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika i rozwijaj temat w sposób prowadzący zgodnie ze swoim profilem.",
    },
    "pojednanie": {
        "label": "Pojednanie",
        "locative": "pojednaniu",
        "opening": "Przedstaw swoje ujęcie tematu tak, by szukać porozumienia i zrozumienia.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika tak, by szukać porozumienia zgodnie ze swoim profilem.",
    },
    "negocjacje": {
        "label": "Negocjacje",
        "locative": "negocjacjach",
        "opening": "Przedstaw swoje priorytety, warunki i możliwe ustępstwa.",
        "counterpart_label": "Druga strona",
        "response": "Odnieś się do propozycji drugiej strony i rozwijaj negocjacje zgodnie ze swoim profilem.",
    },
    "mediacja": {
        "label": "Mediacja",
        "locative": "mediacji",
        "opening": "Przedstaw swoje ujęcie tematu tak, by ułatwić zrozumienie stron i szukanie rozwiązania.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika i pomagaj porządkować wspólne rozumienie zgodnie ze swoim profilem.",
    },
    "rozprawa": {
        "label": "Rozprawa",
        "locative": "rozprawie",
        "opening": "Przedstaw stanowisko i główne argumenty.",
        "counterpart_label": "Druga strona",
        "response": "Odnieś się do stanowiska drugiej strony zgodnie ze swoim profilem.",
    },
    "burza_mozgow": {
        "label": "Burza mózgów",
        "locative": "burzy mózgów",
        "opening": "Zaproponuj pomysł, trop albo rozróżnienie, które może otworzyć temat.",
        "counterpart_label": "Drugi uczestnik",
        "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika i dodaj kolejny użyteczny trop zgodnie ze swoim profilem.",
    },
}


def _resolve_debate_mode(data: dict) -> tuple[str, str]:
    mode_key = str(data.get("debate_mode") or "dialog").strip().lower()
    custom_mode = str(data.get("debate_mode_custom") or "").strip()
    if mode_key == "inne" and custom_mode:
        return custom_mode, custom_mode
    selected = DEBATE_MODES.get(mode_key) or DEBATE_MODES["dialog"]
    return selected["label"], selected["locative"]


def _resolve_debate_prompt_shape(data: dict) -> dict[str, str]:
    mode_key = str(data.get("debate_mode") or "dialog").strip().lower()
    custom_mode = str(data.get("debate_mode_custom") or "").strip()
    if mode_key == "inne" and custom_mode:
        return {
            "opening": "Przedstaw swoje ujęcie tematu zgodnie ze swoim profilem.",
            "counterpart_label": "Drugi uczestnik",
            "response": "Odnieś się do ostatniej wypowiedzi drugiego uczestnika zgodnie ze swoim profilem.",
        }
    selected = DEBATE_MODES.get(mode_key) or DEBATE_MODES["dialog"]
    return {
        "opening": selected["opening"],
        "counterpart_label": selected["counterpart_label"],
        "response": selected["response"],
    }


# ── Debate runner ────────────────────────────────────────────────────────────

def _run_debate(data: dict):
    a1, a2     = data["agent1"],                    data["agent2"]
    p1, p2     = data.get("provider1", "openai"),   data.get("provider2", "openai")
    m1, m2     = data.get("model1") or OPENAI_MODEL, data.get("model2") or OPENAI_MODEL
    te1, te2   = data.get("thinking_effort1") or None, data.get("thinking_effort2") or None
    raw_mt1    = data.get("max_tokens1") or "4096"
    raw_mt2    = data.get("max_tokens2") or "4096"
    mt1        = _resolve_turn_max_tokens(raw_mt1, p1)
    mt2        = _resolve_turn_max_tokens(raw_mt2, p2)
    topic      = data.get("topic", "Czym jest prawda?")
    debate_mode_label, debate_mode_locative = _resolve_debate_mode(data)
    prompt_shape = _resolve_debate_prompt_shape(data)
    max_turns  = int(data.get("max_turns", 33))
    continuation_of = data.get("continuation_of") or None

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

    for offset in range(max_turns):
        turn = start_turn + offset
        is1    = (turn % 2 == 0)
        name   = a1  if is1 else a2
        prov   = p1  if is1 else p2
        model  = m1  if is1 else m2
        te     = te1 if is1 else te2
        mt     = mt1 if is1 else mt2
        hist   = h1  if is1 else h2
        sys    = sys1 if is1 else sys2

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

        yield {"type": "turn_end", "agent": name, "turn": turn + 1, "total": total_turns}
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

    # ANALIZATOR
    yield {"type": "analysis_start"}

    analyser_profile = load_tool("_analyser")
    analyser_sys = build_system_prompt(analyser_profile)

    # Format transcript with numbered exchanges
    tx_lines = [f"[wymiana {i+1}] {t['agent'].upper()}: {t['content']}" for i, t in enumerate(transcript)]
    tx = "\n\n".join(tx_lines)

    # Include both agent profiles so analyser can detect unspoken/blind spots
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
            if p1 == "openai":
                analysis_iter = _stream_openai(
                    analyser_sys, analyser_msgs, m1, None,
                    response_format={"type": "json_object"},
                )
            else:
                analysis_iter = _stream_anthropic(
                    analyser_sys, analyser_msgs, m1, None,
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
        if p1 == "openai":
            summary_iter = _stream_openai(summariser_sys, summariser_msgs, m1, None)
        else:
            summary_iter = _stream_anthropic(summariser_sys, summariser_msgs, m1, None)

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

    # ZAPIS NA DYSK
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    debate_id = f"{ts}_{a1}_vs_{a2}"
    record = {
        "id": debate_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent1": a1, "agent2": a2,
        "provider1": p1, "provider2": p2,
        "model1": m1, "model2": m2,
        "thinking_effort1": te1, "thinking_effort2": te2,
        "max_tokens1": str(raw_mt1),
        "max_tokens2": str(raw_mt2),
        "debate_mode": debate_mode_label,
        "debate_mode_custom": data.get("debate_mode_custom") or "",
        "topic": topic,
        "history1": h1,
        "history2": h2,
        "transcript": transcript,
        "live_notes": live_notes,
        "analysis": analysis_text,
        "analysis_json": analysis_json,
        "analysis_thinking": analysis_thinking,
        "summary": summary_text,
        "summary_thinking": summary_thinking,
        "summary_error": summary_error,
        "continuation_of": continuation_of,
    }
    DEBATES_DIR.mkdir(exist_ok=True)
    (DEBATES_DIR / f"{debate_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    yield {
        "type": "saved",
        "id": debate_id,
        "config": {
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
            "topic": topic,
            "debate_mode": data.get("debate_mode") or "dialog",
            "debate_mode_custom": data.get("debate_mode_custom") or "",
            "max_turns": max_turns,
        },
        "continuation": {
            "history1": h1,
            "history2": h2,
            "transcript": transcript,
            "live_notes": live_notes,
            "turns_completed": len(transcript),
        },
    }


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
    files = sorted(DEBATES_DIR.glob("*.json"), reverse=True) if DEBATES_DIR.exists() else []
    debates = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            debates.append({
                "id": d["id"],
                "timestamp": d.get("timestamp", ""),
                "agent1": d["agent1"],
                "agent2": d["agent2"],
                "topic": d.get("topic", ""),
                "turns": len(d.get("transcript", [])),
                "model1": d.get("model1", ""),
                "model2": d.get("model2", ""),
            })
        except Exception:
            pass
    return render_template("debates.html", debates=debates)


@app.route("/debates/<debate_id>")
def debate_view(debate_id: str):
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", debate_id)
    path = DEBATES_DIR / f"{safe_id}.json"
    if not path.exists():
        return "Nie znaleziono debaty.", 404
    data = json.loads(path.read_text(encoding="utf-8"))
    return render_template("debate_view.html", debate=data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
