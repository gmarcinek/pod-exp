from __future__ import annotations

import json
import os
import re
import unicodedata

import openai

from client import AGENTS_DIR, OPENAI_MODEL_GPT55

AGENT_GENERATION_SYSTEM = """Generujesz pełny profil agenta epistemicznego w formacie JSON. Pisz wyłącznie po polsku. Zwróć WYŁĄCZNIE czysty JSON, bez markdown, bez komentarzy.
Wypełnij WSZYSTKIE pola schematu. Jeśli użytkownik nie podał szczegółów do jakiegoś pola — wygeneruj je sam, spójnie z całym profilem agenta.

SCHEMAT (wszystkie pola obowiązkowe):
{
  "profile_version": "1.0.0",
  "profile_type": "epistemic_agent_config",
  "language": "pl",
  "federation_description": "2 zdania: czym jest agent + zdanie z 'Aktywuj gdy...' opisujące kiedy go wezwać w debacie wieloagentowej",
  "agent_identity": {
    "designation": "np. 'Agent kartezjański'",
    "short_name": "SKRÓT MAX 12 ZNAKÓW WIELKIE LITERY",
    "narrative_identity": "Kim jesteś w pierwszej osobie — 3-5 zdań",
    "role_in_experiment": "Co reprezentujesz epistemicznie — 1-2 zdania",
    "temperament": ["lista", "2-7", "cech", "charakteru"]
  },
  "ontology": {
    "world_assumption": "Jak rozumiesz naturę rzeczywistości — 2-3 zdania",
    "admitted_entities": ["lista 3-8 encji które uznajesz za realne"],
    "conditionally_admitted_entities": ["0-3 encje warunkowo dopuszczane"],
    "rejected_defaults": ["lista 2-6 rzeczy które odrzucasz"],
    "entity_visibility_policy": "zdanie o tym co jest najbardziej realne poznawczo"
  },
  "epistemology": {
    "knowledge_sources": ["lista 3-6 źródeł wiedzy"],
    "source_prioritization": ["lista 2-5 priorytetów"],
    "disallowed_shortcuts": ["lista 2-5 niedozwolonych skrótów myślowych"],
    "epistemic_posture": "zdanie o postawie epistemicznej"
  },
  "truth_criterion": {
    "definition": "zdanie o tym co jest prawdą dla tego agenta",
    "acceptance_layers": ["lista 2-5 warunków akceptacji"],
    "rejection_conditions": ["lista 2-4 warunków odrzucenia"]
  },
  "cognitive_dynamics": {
    "attractors": [{"name": "...", "description": "..."}, {"name": "...", "description": "..."}],
    "bifurcators": [{"trigger": "...", "effect": "..."}, {"trigger": "...", "effect": "..."}],
    "stability_rules": ["lista 2-4 zasad stabilności poznawczej"]
  },
  "base_beliefs": [
    {"belief": "...", "confidence": "high", "revision_condition": "..."},
    {"belief": "...", "confidence": "medium", "revision_condition": "..."},
    {"belief": "...", "confidence": "low", "revision_condition": "..."}
  ]
}"""


def _list_agents_with_summaries() -> list[dict]:
    agents: list[dict] = []
    for path in sorted(AGENTS_DIR.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            identity = data.get("agent_identity", {})
            ontology = data.get("ontology", {})
            truth = data.get("truth_criterion", {})
            agents.append({
                "name": path.stem,
                "short_name": str(identity.get("short_name") or path.stem),
                "designation": str(identity.get("designation") or path.stem),
                "federation_description": str(data.get("federation_description") or ""),
                "temperament": list(identity.get("temperament") or []),
                "language": str(data.get("language") or "pl"),
                "world_assumption": str(ontology.get("world_assumption") or ""),
                "narrative_identity": str(identity.get("narrative_identity") or ""),
                "truth_definition": str(truth.get("definition") or ""),
            })
        except Exception:
            pass
    return agents


def _sanitize_agent_filename(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.lower().strip())
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str).strip("-")
    return slug or "nowy-agent"


def create_agent_profile(
    *,
    designation: str,
    short_name: str,
    filename: str,
    narrative: str,
    world: str,
    knowledge: str,
    truth: str,
    rejected: str,
    temperament: str,
    federation_desc: str,
) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak OPENAI_API_KEY.")
    user_msg = (
        f"Stwórz pełny profil agenta epistemicznego na podstawie poniższych danych:\n\n"
        f"NAZWA / DESIGNATION: {designation}\n"
        f"SHORT_NAME: {short_name or designation.upper()[:12]}\n"
        f"TOŻSAMOŚĆ NARRACYJNA (kim jesteś): {narrative or '[wygeneruj sam]'}\n"
        f"ZAŁOŻENIE O ŚWIECIE: {world or '[wygeneruj sam]'}\n"
        f"ŹRÓDŁA WIEDZY / EPISTEMOLOGIA: {knowledge or '[wygeneruj sam]'}\n"
        f"KRYTERIUM PRAWDY: {truth or '[wygeneruj sam]'}\n"
        f"ODRZUCANE ZAŁOŻENIA: {rejected or '[wygeneruj sam]'}\n"
        f"TEMPERAMENT: {temperament or '[wygeneruj sam]'}\n"
        f"OPIS FEDERACYJNY: {federation_desc or '[wygeneruj sam]'}\n"
    )
    response = openai.OpenAI(api_key=api_key).chat.completions.create(
        model=OPENAI_MODEL_GPT55,
        messages=[
            {"role": "system", "content": AGENT_GENERATION_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "{}").strip()
    return json.loads(raw)
