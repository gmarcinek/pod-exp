from __future__ import annotations


def _build_debate_config(
    *,
    agent1: str,
    agent2: str,
    provider1: str,
    provider2: str,
    model1: str,
    model2: str,
    thinking_effort1: str | None,
    thinking_effort2: str | None,
    max_tokens1: str,
    max_tokens2: str,
    topic: str,
    debate_mode: str,
    debate_mode_custom: str,
    max_turns: int,
) -> dict:
    return {
        "agent1": agent1,
        "agent2": agent2,
        "provider1": provider1,
        "provider2": provider2,
        "model1": model1,
        "model2": model2,
        "thinking_effort1": thinking_effort1,
        "thinking_effort2": thinking_effort2,
        "max_tokens1": max_tokens1,
        "max_tokens2": max_tokens2,
        "topic": topic,
        "debate_mode": debate_mode,
        "debate_mode_custom": debate_mode_custom,
        "max_turns": max_turns,
    }


def _build_debate_setup(
    *,
    public_goal: str,
    public_documents: str,
    agent1_private_goal: str,
    agent1_private_documents: str,
    agent2_private_goal: str,
    agent2_private_documents: str,
) -> dict:
    return {
        "publicGoal": public_goal,
        "publicDocuments": public_documents,
        "agent1PrivateGoal": agent1_private_goal,
        "agent1PrivateDocuments": agent1_private_documents,
        "agent2PrivateGoal": agent2_private_goal,
        "agent2PrivateDocuments": agent2_private_documents,
    }


def _normalize_debate_setup(data: dict | None) -> dict:
    source = data if isinstance(data, dict) else {}
    setup_source = source.get("setup") if isinstance(source.get("setup"), dict) else source
    return _build_debate_setup(
        public_goal=str(setup_source.get("publicGoal") or "").strip(),
        public_documents=str(setup_source.get("publicDocuments") or "").strip(),
        agent1_private_goal=str(setup_source.get("agent1PrivateGoal") or "").strip(),
        agent1_private_documents=str(setup_source.get("agent1PrivateDocuments") or "").strip(),
        agent2_private_goal=str(setup_source.get("agent2PrivateGoal") or "").strip(),
        agent2_private_documents=str(setup_source.get("agent2PrivateDocuments") or "").strip(),
    )


def _build_public_debate_topic(setup: dict) -> str:
    public_goal = str(setup.get("publicGoal") or "").strip()
    public_documents = str(setup.get("publicDocuments") or "").strip()
    if public_goal and public_documents:
        return f"Cel wspólny:\n{public_goal}\n\nWspólne dokumenty:\n{public_documents}"
    if public_goal:
        return f"Cel wspólny:\n{public_goal}"
    if public_documents:
        return f"Wspólne dokumenty:\n{public_documents}"
    return "Przeprowadź debatę zgodnie z wybranym setupem."


def _build_setup_prompt_block(setup: dict, slot: int) -> str:
    if not any(str(value or "").strip() for value in setup.values()):
        return ""
    private_goal_key = "agent1PrivateGoal" if slot == 1 else "agent2PrivateGoal"
    private_documents_key = "agent1PrivateDocuments" if slot == 1 else "agent2PrivateDocuments"
    public_goal = str(setup.get("publicGoal") or "").strip() or "Brak"
    public_documents = str(setup.get("publicDocuments") or "").strip() or "Brak"
    private_goal = str(setup.get(private_goal_key) or "").strip() or "Brak"
    private_documents = str(setup.get(private_documents_key) or "").strip() or "Brak"
    return (
        "\n\nDodatkowy setup wejściowy:\n"
        f"[PUBLICZNY CEL]\n{public_goal}\n\n"
        f"[PUBLICZNE DANE]\n{public_documents}\n\n"
        f"[PRYWATNY CEL]\n{private_goal}\n\n"
        f"[PRYWATNE DANE]\n{private_documents}\n\n"
        "Informacje oznaczone jako prywatne są znane tylko tobie na starcie. "
        "Nie zakładaj, że drugi agent je zna, dopóki nie ujawni ich przebieg rozmowy."
    )


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


def _normalize_legacy_debate_mode(value: object) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return "dialog"
    normalized_value = raw_value.lower()
    if normalized_value in DEBATE_MODES:
        return normalized_value
    display_label_map = {
        mode_config["label"].strip().lower(): mode_key
        for mode_key, mode_config in DEBATE_MODES.items()
    }
    return display_label_map.get(normalized_value, "dialog")


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
