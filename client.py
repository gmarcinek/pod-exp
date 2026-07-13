"""
POD-EXP client – łączy się z OpenAI, Anthropic i Ollama.
Ładuje profile aktorów z agents/*.json i narzędzi z tools/*.json,
i buduje z nich system prompt.

Użycie:
    python client.py --agent kalwinizm --provider openai  --message "Czym jest prawda?"
    python client.py --agent redukcjonizm --provider anthropic --message "Co to jest świadomość?"
    python client.py --agent fizyk --provider ollama --message "Co to jest świadomość?"

Zmienne środowiskowe:
    OPENAI_API_KEY    – klucz API OpenAI
    ANTHROPIC_API_KEY – klucz API Anthropic
    OLLAMA_BASE_URL   – bazowy URL Ollama (domyślnie: http://localhost:11434/v1)
    OLLAMA_MODELS     – lista modeli Ollama oddzielona przecinkami (opcjonalnie)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv()

# ── Modele ──────────────────────────────────────────────────────────────────
OPENAI_MODEL = "gpt-4.5"
OPENAI_MODEL_GPT54 = "gpt-5.4"
OPENAI_MODEL_GPT54_MINI = "gpt-5.4-mini"
OPENAI_MODEL_GPT55 = "gpt-5.5"
OPENAI_MODEL_GPT55_MINI = "gpt-5.5-mini"
OPENAI_MODEL_GPT56_SOL = "gpt-5.6-sol"
OPENAI_MODEL_GPT56_TERRA = "gpt-5.6-terra"
OPENAI_MODEL_GPT56_LUNA = "gpt-5.6-luna"
ANTHROPIC_MODEL = "claude-opus-4-6"
ANTHROPIC_MODEL_HAIKU = "claude-3-5-haiku-latest"

# Modele obsługujące thinking / reasoning_effort
OPENAI_THINKING_MODELS: frozenset[str] = frozenset({
    OPENAI_MODEL_GPT54,
    OPENAI_MODEL_GPT54_MINI,
    OPENAI_MODEL_GPT55,
    OPENAI_MODEL_GPT55_MINI,
    OPENAI_MODEL_GPT56_SOL,
    OPENAI_MODEL_GPT56_TERRA,
    OPENAI_MODEL_GPT56_LUNA,
})

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"
OLLAMA_DEFAULT_MODELS = ["llama3.2", "llama3.1:8b", "mistral", "qwen2.5"]

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
    Buduje prosty system prompt oparty o pełny profil JSON as is.
    """
    return json.dumps(profile, ensure_ascii=False, indent=2)


def check_system_prompt_contains_full_profile(
    profile_name: str,
    *,
    profile_kind: Literal["agent", "tool"] = "agent",
    required_top_level_keys: tuple[str, ...] = (),
) -> None:
    """Lekki lokalny check, że prompt jest dokładnie pełnym serializowanym profilem."""
    loader = load_agent if profile_kind == "agent" else load_tool
    profile = loader(profile_name)
    serialized_profile = json.dumps(profile, ensure_ascii=False, indent=2)
    prompt = build_system_prompt(profile)

    if prompt != serialized_profile:
        raise AssertionError(
            f"Prompt dla {profile_kind} '{profile_name}' nie jest dokładnie pełnym serializowanym JSON-em profilu."
        )

    missing_keys = [key for key in required_top_level_keys if f'"{key}"' not in prompt]
    if missing_keys:
        raise AssertionError(
            f"Prompt dla {profile_kind} '{profile_name}' nie zawiera kluczy top-level: {', '.join(missing_keys)}"
        )


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


# ── Ollama ───────────────────────────────────────────────────────────────────

def call_ollama_messages(
    system_prompt: str,
    messages: list[dict],
    model: str,
    max_tokens: int | None = None,
) -> str:
    """Multi-turn Ollama call przez OpenAI-compatible API."""
    base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL)
    params: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
    }
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    client = openai.OpenAI(api_key="ollama", base_url=base_url)
    resp = client.chat.completions.create(**params)
    return resp.choices[0].message.content or ""


# ── Główna funkcja ───────────────────────────────────────────────────────────

Provider = Literal["openai", "anthropic", "ollama"]


def ask(
    agent_name: str,
    message: str,
    provider: Provider = "openai",
    *,
    openai_model: str = OPENAI_MODEL,
    anthropic_model: str = ANTHROPIC_MODEL,
    ollama_model: str = OLLAMA_DEFAULT_MODELS[0],
    thinking_effort: str | None = None,
) -> str:
    """
    Wysyła pytanie do modelu z zachowaniem profilu epistemicznego agenta.

    Args:
        agent_name:      Nazwa pliku agenta (bez .json), np. "kalwinizm".
        message:         Pytanie lub treść wiadomości.
        provider:        "openai", "anthropic" lub "ollama".
        openai_model:    Nadpisanie domyślnego modelu OpenAI.
        anthropic_model: Nadpisanie domyślnego modelu Anthropic.
        ollama_model:    Nadpisanie domyślnego modelu Ollama.
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
    elif provider == "ollama":
        return call_ollama_messages(system_prompt, [{"role": "user", "content": message}], model=ollama_model)
    else:
        raise ValueError(f"Nieznany provider: '{provider}'. Użyj 'openai', 'anthropic' lub 'ollama'.")


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
        choices=["openai", "anthropic", "ollama"],
        default="openai",
        help="Dostawca modelu: openai (domyślnie), anthropic lub ollama.",
    )
    parser.add_argument(
        "--openai-model",
        default=OPENAI_MODEL,
        choices=[
            OPENAI_MODEL,
            OPENAI_MODEL_GPT54,
            OPENAI_MODEL_GPT54_MINI,
            OPENAI_MODEL_GPT55,
            OPENAI_MODEL_GPT55_MINI,
            OPENAI_MODEL_GPT56_SOL,
            OPENAI_MODEL_GPT56_TERRA,
            OPENAI_MODEL_GPT56_LUNA,
        ],
        help=f"Model OpenAI (domyślnie: {OPENAI_MODEL}).",
    )
    parser.add_argument(
        "--anthropic-model",
        default=ANTHROPIC_MODEL,
        choices=[ANTHROPIC_MODEL, ANTHROPIC_MODEL_HAIKU],
        help=f"Model Anthropic (domyślnie: {ANTHROPIC_MODEL}).",
    )
    parser.add_argument(
        "--ollama-model",
        default=OLLAMA_DEFAULT_MODELS[0],
        help=f"Model Ollama (domyślnie: {OLLAMA_DEFAULT_MODELS[0]}).",
    )
    parser.add_argument(
        "--thinking-effort",
        choices=["auto", "medium", "high", "low"],
        default=None,
        help=(
            "Poziom reasoning_effort dla modeli z myśleniem "
            f"({OPENAI_MODEL_GPT54}, {OPENAI_MODEL_GPT54_MINI}, "
            f"{OPENAI_MODEL_GPT55}, {OPENAI_MODEL_GPT55_MINI}, "
            f"{OPENAI_MODEL_GPT56_SOL}, {OPENAI_MODEL_GPT56_TERRA}, {OPENAI_MODEL_GPT56_LUNA}). "
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
            ollama_model=args.ollama_model,
            thinking_effort=args.thinking_effort,
        )
        print(response)
    except (FileNotFoundError, EnvironmentError, ValueError) as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
