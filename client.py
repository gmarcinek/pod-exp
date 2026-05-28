"""
POD-EXP client – łączy się z OpenAI (gpt-4.5) i Anthropic (claude-opus-4-6).
Ładuje profile aktorów z agents/*.json i narzędzi z tools/*.json,
i buduje z nich system prompt.

Użycie:
    python client.py --agent kalwinizm --provider openai  --message "Czym jest prawda?"
    python client.py --agent redukcjonizm --provider anthropic --message "Co to jest świadomość?"

Zmienne środowiskowe:
    OPENAI_API_KEY    – klucz API OpenAI
    ANTHROPIC_API_KEY – klucz API Anthropic
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv()

# ── Modele ──────────────────────────────────────────────────────────────────
OPENAI_MODEL = "gpt-4.5"
OPENAI_MODEL_GPT54 = "gpt-5.4"
OPENAI_MODEL_GPT55 = "gpt-5.5"
ANTHROPIC_MODEL = "claude-opus-4-6"

# Modele obsługujące thinking / reasoning_effort
OPENAI_THINKING_MODELS: frozenset[str] = frozenset({OPENAI_MODEL_GPT54, OPENAI_MODEL_GPT55})

AGENTS_DIR = Path(__file__).parent / "agents"
TOOLS_DIR = Path(__file__).parent / "tools"


# ── Ładowanie profilu ────────────────────────────────────────────────────────

def _load_profile(name: str, directory: Path, label: str) -> dict:
    path = directory / f"{name}.json"
    if not path.exists():
        available = [p.stem for p in directory.glob("*.json")]
        raise FileNotFoundError(
            f"Nie znaleziono {label} '{name}'. "
            f"Dostępne: {', '.join(sorted(available))}"
        )
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_agent(name: str) -> dict:
    """Wczytuje profil aktora z pliku JSON (z katalogu agents/)."""
    return _load_profile(name, AGENTS_DIR, "profilu agenta")


def load_tool(name: str) -> dict:
    """Wczytuje profil narzędzia z pliku JSON (z katalogu tools/)."""
    return _load_profile(name, TOOLS_DIR, "profilu toola")


def build_system_prompt(profile: dict) -> str:
    """
    Buduje system prompt na podstawie profilu epistemicznego agenta.
    Wyciąga kluczowe sekcje z JSON-a i skleja je w spójny prompt.
    """
    identity = profile.get("agent_identity", {})
    ontology = profile.get("ontology", {})
    epistemology = profile.get("epistemology", {})
    truth = profile.get("truth_criterion", {})
    behavior = profile.get("behavioral_defaults", {})
    language = profile.get("language", "pl")

    lines: list[str] = []

    # Tożsamość
    if narrative := identity.get("narrative_identity"):
        lines.append(narrative)

    # Rola w eksperymencie
    if role := identity.get("role_in_experiment"):
        lines.append(f"\nTwoja rola: {role}")

    # Temperament
    if temps := identity.get("temperament"):
        lines.append(f"\nTwój temperament poznawczy: {', '.join(temps)}.")

    # Założenie ontologiczne
    if world := ontology.get("world_assumption"):
        lines.append(f"\nZałożenie ontologiczne: {world}")

    # Odrzucone domyślne założenia
    if rejected := ontology.get("rejected_defaults"):
        lines.append(
            "\nNie przyjmujesz za oczywiste: " + "; ".join(rejected) + "."
        )

    # Źródła wiedzy i ich priorytet
    if sources := epistemology.get("knowledge_sources"):
        lines.append(
            "\nDopuszczalne źródła wiedzy: " + ", ".join(sources) + "."
        )
    if prio := epistemology.get("source_prioritization"):
        lines.append(
            "Hierarchia źródeł: " + " > ".join(prio) + "."
        )

    # Niedozwolone skróty myślowe
    if shortcuts := epistemology.get("disallowed_shortcuts"):
        lines.append(
            "\nNiedozwolone skróty: " + "; ".join(shortcuts) + "."
        )

    # Postawa epistemiczna
    if posture := epistemology.get("epistemic_posture"):
        lines.append(f"\nPostawa epistemiczna: {posture}")

    # Kryterium prawdy
    if truth_def := truth.get("definition"):
        lines.append(f"\nKryterium prawdy: {truth_def}")

    # Domyślne zachowania
    if style := behavior.get("response_style"):
        lines.append(f"\nStyl odpowiedzi: {style}")
    if uncertainty := behavior.get("uncertainty_handling"):
        lines.append(f"Obsługa niepewności: {uncertainty}")

    # Cognitive dynamics (attractors + exclusion_clauses) — kartograf / analizator
    dynamics = profile.get("cognitive_dynamics", {})
    if attractors := dynamics.get("attractors"):
        parts = []
        for a in attractors:
            if isinstance(a, dict):
                parts.append(f"– {a.get('name', '')}: {a.get('description', '')}")
            else:
                parts.append(f"– {a}")
        if parts:
            lines.append("\nAttraktory poznawcze:\n" + "\n".join(parts))
    if exclusions := dynamics.get("exclusion_clauses"):
        lines.append("\nKlauzule wykluczenia (bezwzględne):\n" + "\n".join(f"  {e}" for e in exclusions))

    # Output contract — format wyjścia i schemat JSON
    contract = profile.get("output_contract", {})
    if contract:
        if desc := contract.get("description"):
            lines.append(f"\n{desc}")
        enums = contract.get("enums", {})
        if schema := contract.get("required_schema"):
            schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
            enums_str = json.dumps(enums, ensure_ascii=False, indent=2) if enums else ""
            lines.append(f"\nWypełnij dokładnie ten schemat JSON:\n{schema_str}")
            if enums_str:
                lines.append(f"\nDostępne wartości enumeracji:\n{enums_str}")

    # Język
    lang_instruction = (
        "Odpowiadaj po polsku." if language == "pl" else f"Respond in language: {language}."
    )
    lines.append(f"\n{lang_instruction}")

    return "\n".join(lines)


# ── Klienci API ──────────────────────────────────────────────────────────────

def call_openai(
    system_prompt: str,
    message: str,
    model: str = OPENAI_MODEL,
    thinking_effort: str | None = None,
) -> str:
    """Wysyła wiadomość do OpenAI i zwraca odpowiedź.

    Args:
        thinking_effort: Poziom reasoning_effort dla modeli z myśleniem
                         ("auto", "medium", "high", "low"). Gdy "auto" lub
                         "medium" – automatycznie ustawia temperature=0.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Brak klucza API. Ustaw zmienną środowiskową OPENAI_API_KEY."
        )

    params: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    }

    if thinking_effort is not None:
        if model not in OPENAI_THINKING_MODELS:
            raise ValueError(
                f"Model '{model}' nie obsługuje thinking_effort. "
                f"Użyj jednego z: {', '.join(sorted(OPENAI_THINKING_MODELS))}."
            )
        params["reasoning_effort"] = thinking_effort

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(**params)
    return response.choices[0].message.content or ""


def call_openai_messages(
    system_prompt: str,
    messages: list[dict],
    model: str = OPENAI_MODEL,
    thinking_effort: str | None = None,
) -> str:
    """Multi-turn OpenAI call – przyjmuje pełną historię konwersacji."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak klucza API. Ustaw zmienną środowiskową OPENAI_API_KEY.")

    params: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
    }
    if thinking_effort is not None:
        if model not in OPENAI_THINKING_MODELS:
            raise ValueError(
                f"Model '{model}' nie obsługuje thinking_effort. "
                f"Użyj jednego z: {', '.join(sorted(OPENAI_THINKING_MODELS))}."
            )
        params["reasoning_effort"] = thinking_effort

    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(**params)
    return resp.choices[0].message.content or ""


def call_anthropic_messages(
    system_prompt: str,
    messages: list[dict],
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = 4096,
) -> str:
    """Multi-turn Anthropic call – przyjmuje pełną historię konwersacji."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak klucza API. Ustaw zmienną środowiskową ANTHROPIC_API_KEY.")

    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("user", "assistant")
    ]
    c = anthropic.Anthropic(api_key=api_key)
    resp = c.messages.create(model=model, max_tokens=max_tokens, system=system_prompt, messages=clean)
    block = resp.content[0]
    return block.text if hasattr(block, "text") else str(block)


def call_anthropic(
    system_prompt: str,
    message: str,
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = 2048,
) -> str:
    """Wysyła wiadomość do Anthropic i zwraca odpowiedź."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Brak klucza API. Ustaw zmienną środowiskową ANTHROPIC_API_KEY."
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": message}],
    )
    block = response.content[0]
    return block.text if hasattr(block, "text") else str(block)


# ── Główna funkcja ───────────────────────────────────────────────────────────

Provider = Literal["openai", "anthropic"]


def ask(
    agent_name: str,
    message: str,
    provider: Provider = "openai",
    *,
    openai_model: str = OPENAI_MODEL,
    anthropic_model: str = ANTHROPIC_MODEL,
    thinking_effort: str | None = None,
) -> str:
    """
    Wysyła pytanie do modelu z zachowaniem profilu epistemicznego agenta.

    Args:
        agent_name:      Nazwa pliku agenta (bez .json), np. "kalwinizm".
        message:         Pytanie lub treść wiadomości.
        provider:        "openai" lub "anthropic".
        openai_model:    Nadpisanie domyślnego modelu OpenAI.
        anthropic_model: Nadpisanie domyślnego modelu Anthropic.
        thinking_effort: Poziom reasoning dla modeli OpenAI z myśleniem
                         ("auto", "medium", "high", "low").
                         Przy "auto" i "medium" wymusza temperature=0.

    Returns:
        Odpowiedź modelu jako string.
    """
    profile = load_agent(agent_name)
    system_prompt = build_system_prompt(profile)

    if provider == "openai":
        return call_openai(system_prompt, message, model=openai_model, thinking_effort=thinking_effort)
    elif provider == "anthropic":
        return call_anthropic(system_prompt, message, model=anthropic_model)
    else:
        raise ValueError(f"Nieznany provider: '{provider}'. Użyj 'openai' lub 'anthropic'.")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="POD-EXP – zadaj pytanie agentowi epistemicznemu."
    )
    parser.add_argument(
        "--agent", "-a",
        required=True,
        help="Nazwa agenta (np. kalwinizm, redukcjonizm, relatywizm).",
    )
    parser.add_argument(
        "--message", "-m",
        required=True,
        help="Treść pytania lub wiadomości do agenta.",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["openai", "anthropic"],
        default="openai",
        help="Dostawca modelu: openai (domyślnie) lub anthropic.",
    )
    parser.add_argument(
        "--openai-model",
        default=OPENAI_MODEL,
        choices=[OPENAI_MODEL, OPENAI_MODEL_GPT54, OPENAI_MODEL_GPT55],
        help=f"Model OpenAI (domyślnie: {OPENAI_MODEL}).",
    )
    parser.add_argument(
        "--anthropic-model",
        default=ANTHROPIC_MODEL,
        help=f"Model Anthropic (domyślnie: {ANTHROPIC_MODEL}).",
    )
    parser.add_argument(
        "--thinking-effort",
        choices=["auto", "medium", "high", "low"],
        default=None,
        help=(
            "Poziom reasoning_effort dla modeli z myśleniem "
            f"({OPENAI_MODEL_GPT54}, {OPENAI_MODEL_GPT55}). "
            "Przy 'auto' i 'medium' automatycznie ustawia temperature=0."
        ),
    )
    args = parser.parse_args()

    try:
        response = ask(
            agent_name=args.agent,
            message=args.message,
            provider=args.provider,
            openai_model=args.openai_model,
            anthropic_model=args.anthropic_model,
            thinking_effort=args.thinking_effort,
        )
        print(response)
    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
