from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import openai

from client import build_system_prompt, load_tool
from config import (
    LIVE_FACTS_MAX_RETRIES,
    LIVE_FACTS_MAX_TOKENS,
    LIVE_FACTS_MODEL,
    LIVE_NOTES_INPUT_CHARS,
    LIVE_NOTES_MAX_RETRIES,
    LIVE_NOTES_MAX_TOKENS,
    LIVE_NOTES_MODEL,
    PROVIDER_MAX_TOKENS,
)


def _resolve_turn_max_tokens(raw_value: object, provider: str) -> int:
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


def _empty_live_notes(topic: str) -> dict:
    return {
        "topic": topic,
        "entries": [],
        "fact_cards": [],
    }


def _normalize_live_notes(data: dict | None, topic: str) -> dict:
    source = data if isinstance(data, dict) else {}
    normalized: dict = {
        "topic": source.get("topic") or topic,
        "entries": list(source.get("entries") or []),
        "fact_cards": list(source.get("fact_cards") or []),
    }
    if source.get("facts_error"):
        normalized["facts_error"] = source["facts_error"]
    return normalized


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
        "Zanotuj tylko nową istotną rzecz z tej tury. "
        "Nie powtarzaj dosłownie poprzednich notatek i nie używaj JSON ani list."
    )
    last_error: Exception | None = None
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
        "Wypisz krótkie 1-3 prośby o fakty do sprawdzenia po tej turze. "
        "Każda linia ma być jedną konkretną rzeczą do weryfikacji. "
        "Zwróć wyłącznie 1-3 osobne linie, bez numeracji, bez wstępu, bez JSON."
    )
    last_error: Exception | None = None
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
            lines: list[str] = []
            for raw_line in payload.splitlines():
                line = raw_line.strip().lstrip("-•* ").strip()
                if line:
                    lines.append(line)
            deduped: list[str] = []
            for line in lines:
                if line not in deduped:
                    deduped.append(line)
            if not deduped:
                raise ValueError("Brak poprawnych fiszek faktów.")
            return deduped
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
    note_error: Exception | None = None
    facts_error: Exception | None = None

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
    updated: dict = {
        "topic": topic,
        "entries": next_entries,
        "fact_cards": next_fact_cards,
    }
    if facts_error and not fact_requests:
        updated["facts_error"] = str(facts_error)
    return updated
