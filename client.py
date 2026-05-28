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
ANTHROPIC_MODEL = "claude-opus-4-6"
ANTHROPIC_MODEL_HAIKU = "claude-3-5-haiku-latest"

# Modele obsługujące thinking / reasoning_effort
OPENAI_THINKING_MODELS: frozenset[str] = frozenset({
    OPENAI_MODEL_GPT54,
    OPENAI_MODEL_GPT54_MINI,
    OPENAI_MODEL_GPT55,
    OPENAI_MODEL_GPT55_MINI,
})

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
    Uwzględnia pełny profil JSON, zachowując czytelne sekcje promptu.
    """
    language = profile.get("language", "pl")
    dynamics = profile.get("cognitive_dynamics", {})
    top_level_exclusions = profile.get("exclusion_clauses")
    exclusions = top_level_exclusions
    if not exclusions and isinstance(dynamics, dict):
        exclusions = dynamics.get("exclusion_clauses")

    def is_empty(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    def scalar_to_text(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def append_value(lines: list[str], value: Any, indent: int = 0) -> None:
        prefix = "  " * indent

        if isinstance(value, dict):
            for key, nested in value.items():
                if is_empty(nested):
                    continue
                if key in {"required_schema", "enums"} and isinstance(nested, (dict, list)):
                    dumped = json.dumps(nested, ensure_ascii=False, indent=2)
                    lines.append(f"{prefix}- {key}:")
                    for dumped_line in dumped.splitlines():
                        lines.append(f"{prefix}  {dumped_line}")
                    continue
                if isinstance(nested, (dict, list)):
                    lines.append(f"{prefix}- {key}:")
                    append_value(lines, nested, indent + 1)
                else:
                    lines.append(f"{prefix}- {key}: {scalar_to_text(nested)}")
            return

        if isinstance(value, list):
            for item in value:
                if is_empty(item):
                    continue
                if isinstance(item, dict):
                    if {"name", "description"}.issubset(item):
                        lines.append(f"{prefix}- {item['name']}: {item['description']}")
                        extras = {
                            key: nested for key, nested in item.items()
                            if key not in {"name", "description"} and not is_empty(nested)
                        }
                        if extras:
                            append_value(lines, extras, indent + 1)
                    elif {"name", "rule"}.issubset(item):
                        lines.append(f"{prefix}- {item['name']}: {item['rule']}")
                        extras = {
                            key: nested for key, nested in item.items()
                            if key not in {"name", "rule"} and not is_empty(nested)
                        }
                        if extras:
                            append_value(lines, extras, indent + 1)
                    elif {"belief", "rank"}.issubset(item):
                        lines.append(f"{prefix}- [{item['rank']}] {item['belief']}")
                        extras = {
                            key: nested for key, nested in item.items()
                            if key not in {"belief", "rank"} and not is_empty(nested)
                        }
                        if extras:
                            append_value(lines, extras, indent + 1)
                    elif {"trigger", "effect"}.issubset(item):
                        lines.append(f"{prefix}- trigger: {item['trigger']}")
                        lines.append(f"{prefix}  effect: {item['effect']}")
                        extras = {
                            key: nested for key, nested in item.items()
                            if key not in {"trigger", "effect"} and not is_empty(nested)
                        }
                        if extras:
                            append_value(lines, extras, indent + 1)
                    else:
                        lines.append(f"{prefix}-")
                        append_value(lines, item, indent + 1)
                elif isinstance(item, list):
                    lines.append(f"{prefix}-")
                    append_value(lines, item, indent + 1)
                else:
                    lines.append(f"{prefix}- {scalar_to_text(item)}")
            return

        lines.append(f"{prefix}{scalar_to_text(value)}")

    def append_section(
        lines: list[str],
        title: str,
        value: Any,
        preferred_order: list[str] | None = None,
    ) -> None:
        if is_empty(value):
            return

        if isinstance(value, dict) and preferred_order:
            ordered_value: dict[str, Any] = {}
            for key in preferred_order:
                nested = value.get(key)
                if not is_empty(nested):
                    ordered_value[key] = nested
            for key, nested in value.items():
                if key not in ordered_value and not is_empty(nested):
                    ordered_value[key] = nested
            value = ordered_value

        if lines:
            lines.append("")
        lines.append(f"{title}:")
        append_value(lines, value, indent=1)

    prompt_lines = [
        "Traktuj poniższy profil jako wiążący porządek poznawczy, styl odpowiedzi i ograniczenia operacyjne.",
    ]

    metadata = {
        "profile_type": profile.get("profile_type"),
        "profile_version": profile.get("profile_version"),
        "language": language,
    }
    append_section(prompt_lines, "Metadane profilu", metadata)
    append_section(
        prompt_lines,
        "Agent identity",
        profile.get("agent_identity"),
        preferred_order=[
            "designation",
            "short_name",
            "class",
            "narrative_identity",
            "core_sentence",
            "tone",
            "role_in_experiment",
            "temperament",
        ],
    )
    append_section(
        prompt_lines,
        "Ontology",
        profile.get("ontology"),
        preferred_order=[
            "world_assumption",
            "admitted_entities",
            "conditionally_admitted_entities",
            "rejected_defaults",
            "entity_visibility_policy",
        ],
    )
    append_section(
        prompt_lines,
        "Epistemology",
        profile.get("epistemology"),
        preferred_order=[
            "knowledge_sources",
            "source_prioritization",
            "disallowed_shortcuts",
            "epistemic_posture",
        ],
    )
    append_section(
        prompt_lines,
        "Truth criterion",
        profile.get("truth_criterion"),
        preferred_order=[
            "definition",
            "acceptance_layers",
            "rejection_conditions",
        ],
    )

    dynamics_section = dynamics
    if isinstance(dynamics_section, dict):
        dynamics_section = {
            key: value for key, value in dynamics_section.items() if key != "exclusion_clauses"
        }
    append_section(
        prompt_lines,
        "Cognitive dynamics",
        dynamics_section,
        preferred_order=["attractors", "bifurcators", "stability_rules"],
    )
    append_section(prompt_lines, "Base beliefs", profile.get("base_beliefs"))
    append_section(prompt_lines, "Exclusion clauses", exclusions)
    append_section(
        prompt_lines,
        "Blind spots",
        profile.get("blind_spots"),
        preferred_order=["known_risks", "self_warning", "visibility_limit_statement"],
    )
    append_section(
        prompt_lines,
        "Expression policy",
        profile.get("expression_policy"),
        preferred_order=["style", "tone", "must_include", "must_not_include"],
    )
    append_section(
        prompt_lines,
        "Blindness radius",
        profile.get("blindness_radius"),
        preferred_order=["level", "score", "primary_invisible_zones", "notes"],
    )
    append_section(
        prompt_lines,
        "Uncertainty resilience",
        profile.get("uncertainty_resilience"),
        preferred_order=["level", "score", "behaviour_under_uncertainty", "failure_modes"],
    )
    append_section(
        prompt_lines,
        "Cognitive tendencies",
        profile.get("cognitive_tendencies"),
        preferred_order=["dominant_tendencies", "secondary_tendencies", "counter_tendencies"],
    )
    append_section(
        prompt_lines,
        "Behavioral defaults",
        profile.get("behavioral_defaults"),
        preferred_order=["response_style", "uncertainty_handling"],
    )

    known_top_level_keys = {
        "profile_type",
        "profile_version",
        "language",
        "agent_identity",
        "ontology",
        "epistemology",
        "truth_criterion",
        "cognitive_dynamics",
        "base_beliefs",
        "exclusion_clauses",
        "blind_spots",
        "expression_policy",
        "blindness_radius",
        "uncertainty_resilience",
        "cognitive_tendencies",
        "behavioral_defaults",
        "output_contract",
    }
    for key, value in profile.items():
        if key in known_top_level_keys or is_empty(value):
            continue
        append_section(prompt_lines, f"Additional section: {key}", value)

    append_section(
        prompt_lines,
        "Output contract",
        profile.get("output_contract"),
        preferred_order=[
            "format",
            "preferred_format",
            "description",
            "notes",
            "minimum_quality_bar",
            "agent_motto",
            "final_instruction",
            "enums",
            "required_schema",
        ],
    )

    if language == "pl":
        prompt_lines.append("")
        prompt_lines.append("Odpowiadaj po polsku.")
    else:
        prompt_lines.append("")
        prompt_lines.append(f"Respond in language: {language}.")

    return "\n".join(prompt_lines)


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
        choices=[
            OPENAI_MODEL,
            OPENAI_MODEL_GPT54,
            OPENAI_MODEL_GPT54_MINI,
            OPENAI_MODEL_GPT55,
            OPENAI_MODEL_GPT55_MINI,
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
        "--thinking-effort",
        choices=["auto", "medium", "high", "low"],
        default=None,
        help=(
            "Poziom reasoning_effort dla modeli z myśleniem "
            f"({OPENAI_MODEL_GPT54}, {OPENAI_MODEL_GPT54_MINI}, "
            f"{OPENAI_MODEL_GPT55}, {OPENAI_MODEL_GPT55_MINI}). "
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
