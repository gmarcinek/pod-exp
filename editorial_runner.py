from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from client import (
    ANTHROPIC_MODEL,
    OPENAI_MODEL_GPT54,
    call_anthropic_messages,
    call_ollama_messages,
    call_openai_messages,
)
from config import PROVIDER_MAX_TOKENS, _generate_debate_id
from editorial_notifications import EditorialStatusNotifier
from editorial_store import store_editorial_document, store_patch_decisions
from storage import _write_debate_snapshot


EDITORIAL_DEFAULT_MODEL = OPENAI_MODEL_GPT54
EDITORIAL_DEFAULT_MAX_TOKENS = 4096
EDITORIAL_ANALYSIS_HISTORY_LIMIT = 20
EDITORIAL_DEFAULT_READ_WINDOW_LINES = 200
EDITORIAL_MAX_READ_WINDOW_LINES = 2000
EDITORIAL_READING_MODES = {"exhaustive", "range", "search"}
EDITORIAL_READING_TOOLS = {"read_lines", "jump_to_line", "search_text"}
HANDOFF_MARKERS = {"[FAKT]", "[HIPOTEZA]", "[INTERPRETACJA]", "[PYTANIE]", "[DECYZJA AUTORA]"}
HANDOFF_LINE_REFERENCE = re.compile(r"^(L\d+(?:-L?\d+)?)\s*[:\-]?\s*(.*)$")

ANALYTICAL_ROLE_KEYS = {"marker", "coherence_guard", "critic"}
PATCH_SCOPES = {"word", "phrase", "sentence", "paragraph"}
PATCH_CHANGE_TYPES = {"punctuation", "language", "reference", "continuity"}
EDITORIAL_LAYERS = {"language", "reference", "continuity", "logic", "register", "repetition"}
MODEL_SIGNATURES = (
    "to był ten rodzaj",
    "było w tym coś",
    "coś się przesunęło",
    "coś było nie tak",
    "i wtedy to poczuł",
    "dopiero później miał zrozumieć",
    "to miało zmienić wszystko",
    "w pewnym sensie",
    "na swój sposób",
    "w jakiś sposób",
)

ROLE_SPECS: list[dict[str, str]] = [
    {
        "key": "marker",
        "label": "Znacznik fragmentów",
        "instruction": (
            "Jesteś redaktorem oznaczającym fragmenty problematyczne. "
            "Czytasz tekst i zwracasz wyłącznie listę oznaczonych fragmentów. "
            "Dla każdego punktu podaj: [KATEGORIA], cytat 1-3 zdań, diagnozę, minimalną zalecaną ingerencję "
            "i poziom pewności. Kategorie ogranicz do: BŁĄD JĘZYKOWY, LOGIKA, CIĄGŁOŚĆ, "
            "NIEJASNE ODNIESIENIE, NIEZAMIERZONE POWTÓRZENIE, REJESTR, WIARYGODNOŚĆ, "
            "MOŻLIWA DECYZJA AUTORSKA. Ostatnia kategoria nie uprawnia do samodzielnej zmiany tekstu. "
            "Nie przepisuj całego tekstu. Wybierz maksymalnie 8 najważniejszych miejsc."
        ),
    },
    {
        "key": "coherence_guard",
        "label": "Strażnik sensu i ciągłości",
        "instruction": (
            "Jesteś redaktorem pilnującym sensowności zdań w kontekście całego tekstu. "
            "Masz wychwytywać porównania z sufitu, nielogiczne przeskoki, zdania które nie pasują do reszty, "
            "pęknięcia rejestru, sztuczne domknięcia typowe dla LLM i miejsca, które brzmią gładko, ale nie są ludzkie. "
            "Zwróć 4 sekcje: NIESPOJNOSCI, PODEJRZANE POROWNANIA, REJESTR I TON, SZTUCZNE DOMKNIECIA. "
            "W każdej sekcji wskaż konkretne cytaty i bardzo krótko powiedz, co z nimi zrobić."
        ),
    },
    {
        "key": "critic",
        "label": "Krytyk wydawniczy",
        "instruction": (
            "Jesteś krytykiem wydawniczym pracującym wyłącznie diagnostycznie. "
            "Masz ocenić tekst bez grzecznościowego rozmywania problemu, ale nie wolno ci projektować utworu. "
            "Nie proponuj zmiany kolejności scen, skracania lub rozwijania scen, odsłaniania informacji wcześniej, "
            "zmiany hierarchii scen ani nowych zdarzeń. Wskazuj wyłącznie konkretne lokalne problemy obecne w tekście. "
            "Zwróć 4 sekcje: MOCNE STRONY, GLOWNE RYZYKA, CO NIE DZIALA, PRIORYTET NAPRAWY. "
            "Każdy punkt naprawy musi odwoływać się do cytatu i pozostawać zgodny z briefem autora."
        ),
    },
]

EDITORIAL_CONSERVATION_CHARTER = """
Jesteś redaktorem literackim pracującym na gotowym tekście autora. Poprawiasz tekst, nie
przepisujesz go według własnych preferencji. Każda zmiana musi wynikać z konkretnego problemu
obecnego w tekście, zachowywać sens, ton, rytm, obrazowanie i indywidualny głos autora.

Nie jesteś współautorem. Nie dodawaj czynności, faktów, motywacji, reakcji, informacji o świecie,
procedur, wyjaśnień, symboli ani puent. Nie zmieniaj psychologii postaci, punktu widzenia,
temperatury emocjonalnej, kolejności zdarzeń lub akapitów, długości scen, tempa, funkcji scen ani
miejsca ujawnienia informacji. Nie zastępuj metafory objaśnieniem, nie upraszczaj jej tylko dlatego,
że jest intensywna, i nie redukuj celowej wieloznaczności do jednej interpretacji.

Rozróżniaj błąd od preferencji. Błędem może być sprzeczność logiczna, błąd językowy, nieczytelne
odniesienie, niezamierzone powtórzenie, literalna niewiarygodność lub niejasność uniemożliwiająca
zrozumienie zdarzenia. Preferencją jest chęć skrócenia sceny, przyspieszenia akcji, uproszczenia
metafory, ujednolicenia rejestru lub zastąpienia stylu autora stylem neutralnym. Preferencji nie
realizuj. Element nie jest niewiarygodny tylko dlatego, że pozostaje niewyjaśniony lub odbiega od
realizmu; zgłoś go wyłącznie, gdy przeczy ustaleniom samego tekstu albo literalnie uniemożliwia
dane zdarzenie.

Stosuj minimalną ingerencję: interpunkcja, fleksja lub składnia przed zmianą słowa; zmiana słowa
przed zmianą zdania; zmiana zdania przed ingerencją w akapit. W razie wątpliwości pozostaw oryginał.
Uwagi diagnostyczne są materiałem do oceny, nie poleceniem do automatycznego wykonania.

GLOBALNE WYTYCZNE ANTYMODELOWE
Nie wprowadzaj do replacementów rozpoznawalnych sygnatur prozy modelowej. Poniższa lista nie jest
poleceniem automatycznego usuwania ich z ORYGINAŁU: jeżeli autor użył ich celowo i nie stanowią
konkretnego błędu, zachowaj je. Zakaz dotyczy przede wszystkim nowych sformułowań tworzonych przez
redaktora.

Unikaj konstrukcji przeciwstawnych i seryjnych negacji typu "Nie X, tylko Y", "To nie jest X. To
jest Y", "nie tyle X, ile Y", "raczej X niż Y" oraz wyliczania odrzuconych interpretacji przed
podaniem właściwej. Nie dodawaj gotowych sygnałów tajemnicy i znaczenia: "To był ten rodzaj",
"Było w tym coś", "Coś się przesunęło", "coś było nie tak", "I wtedy to poczuł",
"Dopiero później miał zrozumieć", "to miało zmienić wszystko".

Nie twórz aforystycznych domknięć, symetrycznych puent, trailerowego rytmu, seryjnych
jednozdaniowych akapitów, pytań retorycznych ani filmowych zapowiedzi. Nie personifikuj abstrakcji
i przedmiotów dla efektu: historia, procedura, budynek, lustro, cisza, światło czy dokument nie
mają samodzielnie pamiętać, wiedzieć, obiecywać, oskarżać ani obserwować, chyba że jest to dosłowna
cecha świata przedstawionego.

Nie objaśniaj metafory po jej użyciu, nie reklamuj tezy tekstu, nie przechodź od szczegółu do
pseudo-filozoficznej prawdy o człowieku i nie zastępuj sceny diagnozą. Nie dodawaj automatycznych
wzmacniaczy i asekuracji: "głębszy", "cichszy", "trudny do nazwania", "w pewnym sensie",
"na swój sposób", "w jakiś sposób", "być może", "wydawało się, że". Nie nadużywaj "jakby",
"ale", "jednak", "mimo to" ani "a jednak" jako sygnałów sztucznej głębi.

Nie używaj generycznej somatyki jako gotowej reakcji emocjonalnej ani katalogowych metafor psychiki,
architektury, biologii, otchłani, mechanizmów lub ciężaru przeszłości, jeśli nie wynikają z konkretu
sceny. Nie mieszaj kilku pól metaforycznych bez funkcji, nie kończ obrazu abstrakcyjnym rzeczownikiem
i nie używaj jednowyrazowych zdań wyłącznie dla emfazy.

Nie normalizuj potoczności, brutalności, szorstkości ani celowej nieelegancji autora. Nie zamieniaj
konkretu na abstrakcję, obrazu na komentarz, czasownika na nominalizację, ani głosu autora na
rozpoznawalny głos redaktora-modelu. Nie używaj archaizacji, stylizowanej ludowości, biblijności,
udawanej filozoficzności, anglicyzujących kalek, nadmiaru średników, dwukropków, kursywy,
dywizów-em-dashów ani cudzysłowów jako zastępczych nośników stylu.
""".strip()

CLEAN_MODEL_SIGNATURES_INSTRUCTION = """
TRYB AKTYWNY: OCZYSZCZANIE NIECHCIANYCH SYGNATUR MODELOWYCH
Autor świadomie zezwolił na usuwanie z ORYGINAŁU rozpoznawalnych sygnatur prozy modelowej, jeżeli
nie są one funkcjonalne dla sceny. Obejmuje to gotowe sygnały tajemnicy, aforystyczne domknięcia,
trailerowe zapowiedzi, seryjne negacje, pozorną głębię, generyczną somatykę oraz zautomatyzowane
metafory wymienione w globalnych wytycznych antymodelowych. Zgłaszaj je jako REJESTR lub
NIEZAMIERZONE POWTÓRZENIE tylko wtedy, gdy konkretnie osłabiają zdanie. Nie usuwaj celowych,
znaczących elementów stylu autora. Każda korekta nadal musi być lokalna, minimalna i przejść wybór
najlepszego wariantu przez walidatora.
""".strip()

EDITORIAL_PLANNER_INSTRUCTION = (
    EDITORIAL_CONSERVATION_CHARTER
    + """

Otrzymujesz końcowy handoff z sekwencyjnego rozpoznania dokumentu, nie pełny tekst. Nie proponujesz
podmian ani nie oceniasz poszczególnych zdań. Rozpoznaj wyłącznie warstwy, które rzeczywiście
wymagają sprawdzenia, i ułóż minimalny plan pracy dla kolejnych porcji tekstu. Warstwa jest potrzebna
tylko wtedy, gdy konkretny problem może przez nią przebiegać; nie planuj kontroli dla formalności.
Każdy wpis reading_protocol musi jawnie określać cel czytania, tryb i narzędzie. Zwróć wyłącznie JSON:
{"document_handoff":{"summary":"krótka mapa całości","continuity":["L12-L18 [FAKT] fakt lub relacja do zachowania"],"voice":["L42-L57 [INTERPRETACJA] cecha głosu autora"],"open_questions":["L88 [PYTANIE] nierozstrzygnięta kwestia"]},"whole_text_notes":["krótka obserwacja"],"layers":[{"id":"continuity","label":"Ciągłość zdarzeń","reason":"co sprawdzić między porcjami","priority":1}],"reading_protocol":[{"mode":"range","purpose":"sprawdzić ciągłość między L201-L400","tool":"read_lines","line_start":201,"line_end":400,"handoff_goal":"przekazać ustalenia potrzebne następnej porcji"}],"handoff_notes":["L12-L18 [FAKT] polecenie dla kolejnych porcji"]}
"""
).strip()

EDITORIAL_DISCOVERY_INSTRUCTION = (
    EDITORIAL_CONSERVATION_CHARTER
    + """

Prowadzisz sekwencyjne rozpoznanie dużego dokumentu przed redakcją. Czytasz wyłącznie wskazany
zakres linii; nie proponujesz patchy, nie oceniasz pojedynczych zdań i nie projektujesz utworu.
Cel czytania oraz tryb są podane w wiadomości i muszą zostać zachowane. Zaktualizuj handoff tak,
aby kolejna porcja znała jedynie fakty, ciągłość, głos i otwarte kwestie potrzebne dalej. Handoff ma
być konkretny, z odwołaniami do linii, i nie może być transkrypcją czy streszczeniem każdej sceny.
Zwróć wyłącznie JSON:
{"document_handoff":{"summary":"mapa dokumentu po przeczytaniu zakresu","continuity":["L1-L12 [FAKT] fakt do zachowania"],"voice":["L34-L40 [INTERPRETACJA] cecha głosu autora"],"open_questions":["L57 [PYTANIE] kwestia do zweryfikowania dalej"]},"findings":[{"marker":"[FAKT]","text":"L1-L12 potwierdzone ustalenie"}],"open_questions_for_reading":["L57 [PYTANIE] pytanie pozostające po tym czytaniu"],"handoff_out":["L201-L400 [FAKT] co następna porcja musi wiedzieć"]}
"""
).strip()

PATCH_REWRITER_INSTRUCTION = (
    EDITORIAL_CONSERVATION_CHARTER
    + """

Przygotowujesz wyłącznie lokalne patche, nigdy pełną wersję tekstu. SOURCE musi wystąpić dosłownie
i dokładnie raz w AKTUALNEJ WERSJI. Nie twórz patcha dla kategorii MOŻLIWA DECYZJA AUTORSKA.
Jeżeli zmiana jest czystą interpunkcją, podaj jeden wariant. Każda zmiana językowa, referencyjna lub
ciągłościowa musi mieć dokładnie 2 albo 3 lokalne warianty. Warianty mają różnić się tylko miejscem
koniecznej korekty; nie wolno im dodawać treści ani przebudowywać zdania poza zakresem błędu.
Zwróć wyłącznie poprawny JSON:
{"patches":[{"id":"p1","source":"dokładny cytat","category":"BŁĄD JĘZYKOWY","change_type":"punctuation|language|reference|continuity","scope":"word|phrase|sentence|paragraph","reason":"konkretny problem z diagnozy","adds_new_fact":false,"author_decision_required":false,"variants":[{"id":"p1-v1","replacement":"minimalna podmiana"}]}]}
"""
).strip()

PATCH_VALIDATOR_INSTRUCTION = (
    EDITORIAL_CONSERVATION_CHARTER
    + """

Jesteś rygorystycznym walidatorem patchy. Porównaj każdy patch z ORYGINAŁEM, AKTUALNĄ WERSJĄ,
BRIEFEM i diagnozą. ACCEPT wydaj wyłącznie dla lokalnej korekty konkretnego błędu, gdy zakres
ingerencji jest najmniejszy możliwy. REJECT wydaj w razie wątpliwości, dla decyzji autorskiej,
nowego faktu, nowej czynności, zmiany metafory bez błędu albo zmiany struktury, tempa, sensu czy
głosu autora. Patch o scope "paragraph" zaakceptuj tylko, gdy mniejsza ingerencja nie może usunąć
konkretnego błędu. Nie wystarczy, że wariant usuwa wskazany problem: sprawdź również, czy nie tworzy
nowego błędu językowego, niezręczności, powtórzenia, sztucznej sygnatury modelowej albo pogorszenia
rytmu. Dla zmian innych niż czysta interpunkcja porównaj wszystkie warianty z ORYGINAŁEM. Wybierz
wyłącznie wariant o najmniejszej zmianie znaczenia i najlepszej naturalności językowej. Jeżeli żaden
wariant nie jest wyraźnie lepszy od oryginału, wydaj REJECT. Bezsporne błędy językowe, gramatyczne,
referencyjne i ciągłości czynności muszą zostać naprawione: zachowawczość nie jest podstawą do
pozostawienia realnego błędu. Zwróć wyłącznie poprawny JSON:
{"verdicts":[{"id":"p1","decision":"ACCEPT" lub "REJECT","selected_variant_id":"p1-v1" lub null,"reason":"krótkie, konkretne uzasadnienie wraz z oceną regresji"}]}
"""
).strip()


def _call_editorial_role(
    *,
    provider: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    messages: list[dict[str, str]],
) -> str:
    if provider == "openai":
        return call_openai_messages(system_prompt, messages, model=model)
    if provider == "anthropic":
        return call_anthropic_messages(system_prompt, messages, model=model, max_tokens=max_tokens)
    if provider == "ollama":
        return call_ollama_messages(system_prompt, messages, model=model, max_tokens=max_tokens)
    raise ValueError(f"Nieznany provider: {provider}")


def _numbered_editorial_text(text: str) -> str:
    return "\n".join(
        f"L{index}: {line}"
        for index, line in enumerate(text.splitlines(), start=1)
    )


def _numbered_editorial_lines(text: str, line_start: int, line_end: int) -> str:
    lines = text.splitlines()
    start = max(1, line_start)
    end = min(len(lines), max(start, line_end))
    return "\n".join(
        f"L{index}: {lines[index - 1]}"
        for index in range(start, end + 1)
    )


def _append_execution_log(log: list[dict[str, object]] | None, event: str, **details: object) -> None:
    if log is not None:
        log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **details,
        })


def _read_editorial_lines(
    text: str,
    line_start: int,
    line_end: int,
    execution_log: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if line_start < 1 or line_end < line_start:
        raise ValueError("Nieprawidłowy zakres linii.")
    if line_end - line_start + 1 > EDITORIAL_MAX_READ_WINDOW_LINES:
        raise ValueError("Jednorazowy odczyt nie może przekroczyć 2000 linii.")
    total_lines = len(text.splitlines())
    if line_start > total_lines:
        result = {"line_start": line_start, "line_end": line_start - 1, "content": ""}
        _append_execution_log(
            execution_log,
            "function_call",
            function="read_lines",
            status="completed",
            arguments={"line_start": line_start, "line_end": line_end},
            result=result,
        )
        return result
    resolved_end = min(line_end, total_lines)
    result = {
        "line_start": line_start,
        "line_end": resolved_end,
        "content": _numbered_editorial_lines(text, line_start, resolved_end),
    }
    _append_execution_log(
        execution_log,
        "function_call",
        function="read_lines",
        status="completed",
        arguments={"line_start": line_start, "line_end": line_end},
        result=result,
    )
    return result


def _jump_to_editorial_line(
    text: str,
    line_number: int,
    execution_log: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    result = _read_editorial_lines(text, line_number, line_number)
    _append_execution_log(
        execution_log,
        "function_call",
        function="jump_to_line",
        status="completed",
        arguments={"line_number": line_number},
        result=result,
    )
    return result


def _search_editorial_text(
    text: str,
    query: str,
    limit: int = 12,
    execution_log: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    needle = query.strip().lower()
    if not needle:
        _append_execution_log(
            execution_log,
            "function_call",
            function="search_text",
            status="completed",
            arguments={"query": query, "limit": limit},
            result=[],
        )
        return []
    matches: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if needle in line.lower():
            matches.append({"line": line_number, "content": f"L{line_number}: {line}"})
        if len(matches) >= limit:
            break
    _append_execution_log(
        execution_log,
        "function_call",
        function="search_text",
        status="completed",
        arguments={"query": query, "limit": limit},
        result=matches,
    )
    return matches


def _normalize_marked_notes(values: object, default_marker: str) -> list[str]:
    if not isinstance(values, list):
        return []
    notes: list[str] = []
    for value in values:
        note = str(value).strip()[:500]
        if not note:
            continue
        marker = next((item for item in HANDOFF_MARKERS if note.startswith(item)), None)
        if marker:
            note = note[len(marker):].strip()
        line_match = HANDOFF_LINE_REFERENCE.match(note)
        if not line_match:
            continue
        line_reference, content = line_match.groups()
        content_marker = next((item for item in HANDOFF_MARKERS if content.startswith(item)), None)
        if content_marker:
            content = content[len(content_marker):].strip()
        selected_marker = marker or content_marker or default_marker
        if content:
            notes.append(f"{line_reference} {selected_marker} {content}")
    return notes[:12]


def _normalize_reading_findings(payload: dict[str, object]) -> list[dict[str, str]]:
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        return []
    findings: list[dict[str, str]] = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            continue
        marker = str(raw_finding.get("marker") or "").strip().upper()
        text = str(raw_finding.get("text") or "").strip()[:500]
        if marker not in HANDOFF_MARKERS or not text or not HANDOFF_LINE_REFERENCE.match(text):
            continue
        findings.append({"marker": marker, "text": text})
    return findings[:12]


def _build_editorial_context(
    *,
    title: str,
    brief: str,
    original_text: str,
    current_text: str,
    cycle: int,
    clean_model_signatures: bool,
    include_current_text: bool = True,
) -> str:
    parts = [
        f"TYTUŁ/PROJEKT: {title or 'Bez tytułu'}",
        f"ITERACJA: {cycle}",
    ]
    if clean_model_signatures:
        parts.append(CLEAN_MODEL_SIGNATURES_INSTRUCTION)
    if brief:
        parts.append(f"BRIEF REDAKCYJNY:\n{brief}")
    parts.append(f"ORYGINAŁ INPUT:\n{original_text}")
    if include_current_text:
        parts.append(f"AKTUALNA WERSJA ROBOCZA:\n{current_text}")
    return "\n\n".join(parts)


def _build_role_message(
    *,
    context_block: str,
    historical_outputs: list[dict[str, str | int]],
    cycle_outputs: dict[str, str],
) -> str:
    sections = [context_block]

    analysis_history = [
        entry
        for entry in historical_outputs
        if str(entry.get("role") or "") in ANALYTICAL_ROLE_KEYS
    ][-EDITORIAL_ANALYSIS_HISTORY_LIMIT:]
    if analysis_history:
        analysis_sections = []
        for entry in analysis_history:
            label = str(entry.get("label") or entry.get("role") or "Rola")
            cycle = int(entry.get("cycle") or 0)
            content = str(entry.get("content") or "")
            analysis_sections.append(f"ITERACJA {cycle} | {label}:\n{content}")
        sections.append(
            "OSTATNIE WYMIANY ANALITYCZNO-KRYTYCZNE (MAX 20):\n\n"
            + "\n\n".join(analysis_sections)
        )

    if cycle_outputs:
        current_cycle_sections = []
        for spec in ROLE_SPECS:
            output = cycle_outputs.get(spec["key"])
            if output:
                current_cycle_sections.append(
                    f"WYJSCIE ROLI {spec['label'].upper()}:\n{output}"
                )
        if current_cycle_sections:
            sections.append(
                "BIEŻĄCA ITERACJA - DOTYCHCZASOWE WYJŚCIA:\n\n"
                + "\n\n".join(current_cycle_sections)
            )
    return "\n\n".join(sections)


def _parse_json_object(content: str, key: str) -> list[dict[str, object]]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    values = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return []
    return [entry for entry in values if isinstance(entry, dict)]


def _parse_json_dict(content: str) -> dict[str, object]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _split_editorial_sections(text: str) -> list[dict[str, object]]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    sections: list[dict[str, object]] = []
    line_start = 1
    paragraph_start = 1
    while line_start <= len(lines):
        default_end = min(line_start + EDITORIAL_DEFAULT_READ_WINDOW_LINES - 1, len(lines))
        max_end = min(line_start + EDITORIAL_MAX_READ_WINDOW_LINES - 1, len(lines))
        line_end = default_end
        if default_end < len(lines) and lines[default_end - 1].strip():
            for candidate in range(default_end, max_end):
                if not lines[candidate - 1].strip():
                    line_end = candidate
                    break
        content = "".join(lines[line_start - 1:line_end])
        paragraph_count = max(1, len([line for line in content.splitlines() if line.strip()]))
        sections.append({
            "id": f"section-{len(sections) + 1}",
            "paragraph_start": paragraph_start,
            "paragraph_end": paragraph_start + paragraph_count - 1,
            "line_start": line_start,
            "line_end": line_end,
            "read_window_lines": line_end - line_start + 1,
            "reading_mode": "exhaustive",
            "reading_purpose": "Rozpoznać fakty, głos i ciągłość w tym zakresie przed redakcją.",
            "reading_reason": "Pierwsze przejście ma zbudować mapę dokumentu bez diagnozowania ani poprawiania zdań.",
            "reading_tools": ["read_lines", "jump_to_line"],
            "handoff_goal": "Przekazać następnej porcji wyłącznie ustalenia potrzebne dla ciągłości.",
            "text": content,
        })
        paragraph_start += paragraph_count
        line_start = line_end + 1
    return sections


def _normalize_editorial_plan(payload: dict[str, object]) -> dict[str, object]:
    raw_layers = payload.get("layers")
    layers: list[dict[str, object]] = []
    seen_layer_ids: set[str] = set()
    if isinstance(raw_layers, list):
        for raw_layer in raw_layers:
            if not isinstance(raw_layer, dict):
                continue
            layer_id = str(raw_layer.get("id") or "").strip().lower()
            if layer_id not in EDITORIAL_LAYERS or layer_id in seen_layer_ids:
                continue
            priority = raw_layer.get("priority")
            layers.append({
                "id": layer_id,
                "label": str(raw_layer.get("label") or layer_id).strip()[:80],
                "reason": str(raw_layer.get("reason") or "").strip()[:500],
                "priority": max(1, min(int(priority) if isinstance(priority, int) else 3, 5)),
            })
            seen_layer_ids.add(layer_id)

    def notes(key: str) -> list[str]:
        values = payload.get(key)
        return [str(value).strip()[:500] for value in values if str(value).strip()][:12] if isinstance(values, list) else []

    def notes_from(source: dict[str, object], key: str) -> list[str]:
        values = source.get(key)
        return [str(value).strip()[:500] for value in values if str(value).strip()][:12] if isinstance(values, list) else []

    raw_handoff = payload.get("document_handoff")
    handoff = raw_handoff if isinstance(raw_handoff, dict) else {}
    raw_protocol = payload.get("reading_protocol")
    reading_protocol: list[dict[str, object]] = []
    if isinstance(raw_protocol, list):
        for raw_step in raw_protocol:
            if not isinstance(raw_step, dict):
                continue
            mode = str(raw_step.get("mode") or "").strip().lower()
            tool = str(raw_step.get("tool") or "").strip()
            line_start = raw_step.get("line_start")
            line_end = raw_step.get("line_end")
            if (
                mode not in EDITORIAL_READING_MODES
                or tool not in EDITORIAL_READING_TOOLS
                or not isinstance(line_start, int)
                or not isinstance(line_end, int)
                or line_start < 1
                or line_end < line_start
                or line_end - line_start + 1 > EDITORIAL_MAX_READ_WINDOW_LINES
            ):
                continue
            purpose = str(raw_step.get("purpose") or "").strip()[:500]
            handoff_goal = str(raw_step.get("handoff_goal") or "").strip()[:500]
            if not purpose or not handoff_goal:
                continue
            reading_protocol.append({
                "mode": mode,
                "purpose": purpose,
                "tool": tool,
                "line_start": line_start,
                "line_end": line_end,
                "handoff_goal": handoff_goal,
            })

    return {
        "document_handoff": {
            "summary": str(handoff.get("summary") or "").strip()[:1000],
            "continuity": _normalize_marked_notes(handoff.get("continuity"), "[FAKT]"),
            "voice": _normalize_marked_notes(handoff.get("voice"), "[INTERPRETACJA]"),
            "open_questions": _normalize_marked_notes(handoff.get("open_questions"), "[PYTANIE]"),
        },
        "whole_text_notes": notes("whole_text_notes"),
        "layers": sorted(layers, key=lambda layer: int(layer["priority"])),
        "reading_protocol": reading_protocol,
        "handoff_notes": _normalize_marked_notes(payload.get("handoff_notes"), "[FAKT]"),
    }


def _normalize_document_handoff(payload: dict[str, object]) -> dict[str, object]:
    raw_handoff = payload.get("document_handoff")
    handoff = raw_handoff if isinstance(raw_handoff, dict) else {}

    return {
        "summary": str(handoff.get("summary") or "").strip()[:1000],
        "continuity": _normalize_marked_notes(handoff.get("continuity"), "[FAKT]"),
        "voice": _normalize_marked_notes(handoff.get("voice"), "[INTERPRETACJA]"),
        "open_questions": _normalize_marked_notes(handoff.get("open_questions"), "[PYTANIE]"),
    }


def _build_patchset(raw_patches: list[dict[str, object]]) -> list[dict[str, object]]:
    patches: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_patch in enumerate(raw_patches, start=1):
        patch_id = str(raw_patch.get("id") or f"p{index}").strip()
        source = str(raw_patch.get("source") or "")
        category = str(raw_patch.get("category") or "").strip()
        change_type = str(raw_patch.get("change_type") or "").strip().lower()
        scope = str(raw_patch.get("scope") or "").strip().lower()
        reason = str(raw_patch.get("reason") or "").strip()
        adds_new_fact = raw_patch.get("adds_new_fact") is True
        author_decision_required = raw_patch.get("author_decision_required") is True
        raw_variants = raw_patch.get("variants")
        variants: list[dict[str, str]] = []
        seen_variant_ids: set[str] = set()
        if isinstance(raw_variants, list):
            for variant_index, raw_variant in enumerate(raw_variants, start=1):
                if not isinstance(raw_variant, dict):
                    continue
                variant_id = str(raw_variant.get("id") or f"{patch_id}-v{variant_index}").strip()
                replacement = str(raw_variant.get("replacement") or "")
                if not variant_id or variant_id in seen_variant_ids or not replacement or replacement == source:
                    continue
                seen_variant_ids.add(variant_id)
                variants.append({"id": variant_id, "replacement": replacement})
        if (
            not patch_id
            or patch_id in seen_ids
            or not source
            or not category
            or change_type not in PATCH_CHANGE_TYPES
            or scope not in PATCH_SCOPES
            or adds_new_fact
            or author_decision_required
            or category == "MOŻLIWA DECYZJA AUTORSKA"
            or not variants
            or (change_type == "punctuation" and len(variants) != 1)
            or (change_type != "punctuation" and len(variants) not in {2, 3})
        ):
            continue
        seen_ids.add(patch_id)
        patches.append({
            "id": patch_id,
            "source": source,
            "category": category,
            "change_type": change_type,
            "scope": scope,
            "reason": reason,
            "adds_new_fact": adds_new_fact,
            "author_decision_required": author_decision_required,
            "variants": variants,
        })
    return patches


def _replacement_has_obvious_regression(source: str, replacement: str) -> bool:
    source_lower = source.lower()
    replacement_lower = replacement.lower()
    if any(
        signature in replacement_lower and signature not in source_lower
        for signature in MODEL_SIGNATURES
    ):
        return True
    if re.search(
        r"\b(?:ale|lecz|a|i|oraz),\s+(?:nie\s+)?\w+(?:ąc|wszy|łszy)\b",
        replacement_lower,
    ):
        return True
    words = re.findall(r"\w+", replacement_lower)
    return any(words[index:index + 3] == words[index + 3:index + 6] for index in range(len(words) - 5))


def _apply_accepted_patches(
    text: str,
    patches: list[dict[str, object]],
    verdicts: list[dict[str, object]],
) -> tuple[str, list[dict[str, object]], list[dict[str, object]]]:
    decisions = {
        str(verdict.get("id") or ""): str(verdict.get("decision") or "").upper()
        for verdict in verdicts
    }
    verdict_reasons = {
        str(verdict.get("id") or ""): str(verdict.get("reason") or "").strip()
        for verdict in verdicts
    }
    selected_variants = {
        str(verdict.get("id") or ""): str(verdict.get("selected_variant_id") or "")
        for verdict in verdicts
    }
    candidates: list[tuple[int, dict[str, object]]] = []
    rejected: list[dict[str, object]] = []
    for patch in patches:
        patch_id = str(patch["id"])
        if decisions.get(patch_id) != "ACCEPT":
            rejected.append({**patch, "reason": verdict_reasons.get(patch_id) or "Odrzucone przez walidator."})
            continue
        selected_variant_id = selected_variants.get(patch_id)
        selected_variant = next(
            (variant for variant in patch["variants"] if variant["id"] == selected_variant_id),
            None,
        )
        if selected_variant is None:
            rejected.append({**patch, "reason": "Walidator nie wskazał poprawnego wariantu."})
            continue
        source = str(patch["source"])
        replacement = selected_variant["replacement"]
        if _replacement_has_obvious_regression(source, replacement):
            rejected.append({**patch, "reason": "Wybrany wariant wprowadza oczywistą regresję stylistyczną lub powtórzenie."})
            continue
        occurrences = text.count(source)
        if occurrences != 1:
            rejected.append({**patch, "reason": "Cytat źródłowy nie występuje dokładnie raz w tekście."})
            continue
        candidates.append((
            text.index(source),
            {**patch, "selected_variant_id": selected_variant_id, "replacement": replacement},
        ))

    candidates.sort(key=lambda item: item[0])
    cursor = 0
    parts: list[str] = []
    accepted: list[dict[str, object]] = []
    for start, patch in candidates:
        source = str(patch["source"])
        end = start + len(source)
        if start < cursor:
            rejected.append({**patch, "reason": "Patch koliduje z inną zaakceptowaną podmianą."})
            continue
        parts.extend((text[cursor:start], str(patch["replacement"])))
        cursor = end
        accepted.append(patch)
    parts.append(text[cursor:])
    return "".join(parts), accepted, rejected


def _resolve_editorial_max_tokens(value: object, provider: str) -> int:
    provider_limit = PROVIDER_MAX_TOKENS.get(provider, EDITORIAL_DEFAULT_MAX_TOKENS)
    raw = str(value or EDITORIAL_DEFAULT_MAX_TOKENS).strip().lower()
    if raw == "max":
        return provider_limit

    return max(512, min(int(raw), provider_limit))


def _build_editorial_summary(*, title: str, cycles_completed: int, final_text: str) -> str:
    normalized_text = " ".join(final_text.split())
    excerpt = normalized_text[:220].rstrip()
    if len(normalized_text) > len(excerpt):
        excerpt += "…"
    return f"{title}: {cycles_completed} iter. {excerpt}" if excerpt else title


def _run_editorial_loop(data: dict):
    title = str(data.get("title") or data.get("topic") or "Sesja redakcyjna").strip()
    brief = str(data.get("brief") or "").strip()
    original_text = str(data.get("text") or "").strip()
    provider = str(data.get("provider") or "openai").strip()
    if provider not in {"openai", "anthropic", "ollama"}:
        raise ValueError("Nieobsługiwany provider dla modułu redakcyjnego.")

    default_model = EDITORIAL_DEFAULT_MODEL if provider == "openai" else ANTHROPIC_MODEL
    model = str(data.get("model") or default_model).strip()
    max_cycles = max(1, min(int(data.get("max_cycles") or 2), 5))
    max_tokens = _resolve_editorial_max_tokens(data.get("max_tokens"), provider)
    clean_model_signatures = data.get("clean_model_signatures") is True

    if not original_text:
        raise ValueError("Brak tekstu do opracowania.")

    edit_id = _generate_debate_id()
    started_at = datetime.now(timezone.utc).isoformat()
    current_text = original_text
    source_manifest = store_editorial_document(
        editorial_id=edit_id,
        version=0,
        text=original_text,
    )
    current_manifest = source_manifest
    transcript: list[dict[str, str | int]] = []
    historical_outputs: list[dict[str, str | int]] = []
    execution_log: list[dict[str, object]] = []
    workflow: dict[str, object] = {
        "mode": "adaptive",
        "status": "planning",
        "plan": {},
        "adaptive_plan": {
            "status": "working",
            "steps": [
                {
                    "id": "document_discovery",
                    "label": "Rozpoznać dokument",
                    "purpose": "Ustalić rozmiar, strukturę i zakres dalszego czytania.",
                    "status": "working",
                    "conclusion": "",
                },
                {
                    "id": "reader",
                    "label": "Czytać dokument Readerem",
                    "purpose": "Zbudować handoff faktów, głosu i ciągłości dla każdej porcji.",
                    "status": "planned",
                    "conclusion": "",
                },
                {
                    "id": "planning",
                    "label": "Wyciągnąć wnioski i ustalić plan",
                    "purpose": "Na podstawie handoffu wybrać wyłącznie potrzebne warstwy redakcji.",
                    "status": "planned",
                    "conclusion": "",
                },
                {
                    "id": "layers",
                    "label": "Zweryfikować warstwy problemów",
                    "purpose": "Uruchomić kolejne role tylko dla warstw wynikających z rozpoznania.",
                    "status": "planned",
                    "conclusion": "",
                },
            ],
        },
        "sections": [],
        "document_storage": {
            "source": source_manifest,
            "current": current_manifest,
        },
        "execution_log": execution_log,
    }

    def call_role(
        *,
        phase: str,
        role: str,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        request = {
            "provider": provider,
            "model": model,
            "max_tokens": max_tokens,
            "system_prompt": system_prompt,
            "messages": messages,
        }
        try:
            response = _call_editorial_role(
                provider=provider,
                model=model,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                messages=messages,
            )
        except Exception as exc:
            _append_execution_log(
                execution_log,
                "llm_call",
                phase=phase,
                role=role,
                status="failed",
                request=request,
                error=str(exc),
            )
            raise
        _append_execution_log(
            execution_log,
            "llm_call",
            phase=phase,
            role=role,
            status="completed",
            request=request,
            response=response,
        )
        return response

    _append_execution_log(
        execution_log,
        "session",
        status="started",
        edit_id=edit_id,
        title=title,
    )
    notifier = EditorialStatusNotifier(edit_id=edit_id, execution_log=execution_log)

    def build_record(*, cycles_completed: int, status: str, error: str | None = None) -> dict:
        record = {
            "id": edit_id,
            "type": "edit",
            "status": status,
            "timestamp": started_at,
            "topic": title,
            "brief": brief,
            "provider": provider,
            "model": model,
            "max_cycles": max_cycles,
            "max_tokens": max_tokens,
            "clean_model_signatures": clean_model_signatures,
            "document_storage": {
                "source": source_manifest,
                "current": current_manifest,
            },
            "summary": _build_editorial_summary(
                title=title,
                cycles_completed=cycles_completed,
                final_text=current_text,
            ),
            "workflow": workflow,
            "transcript": list(transcript),
            "cycles_completed": cycles_completed,
        }
        if error:
            record["error"] = error
        return record

    _write_debate_snapshot(build_record(cycles_completed=0, status="running"))

    yield {
        "type": "editorial_start",
        "id": edit_id,
        "title": title,
        "total_cycles": max_cycles,
        "provider": provider,
        "model": model,
        "clean_model_signatures": clean_model_signatures,
    }

    section_plan = _split_editorial_sections(original_text)
    total_lines = len(original_text.splitlines())
    discovery_conclusion = (
        f"Dokument ma {total_lines} linii, więc wymaga dokładnego odczytu w "
        f"{len(section_plan)} porcjach."
        if len(section_plan) > 1
        else f"Dokument ma {total_lines} linii i zostanie przeczytany w jednej porcji."
    )
    adaptive_plan = workflow["adaptive_plan"]
    assert isinstance(adaptive_plan, dict)
    adaptive_steps = adaptive_plan["steps"]
    assert isinstance(adaptive_steps, list)
    discovery_step = adaptive_steps[0]
    reader_step = adaptive_steps[1]
    assert isinstance(discovery_step, dict) and isinstance(reader_step, dict)
    discovery_step["status"] = "completed"
    discovery_step["conclusion"] = discovery_conclusion
    reader_step["status"] = "working"
    _write_debate_snapshot(build_record(cycles_completed=0, status="running"))
    yield notifier.notify(
        role="Planista",
        phase="document_discovery",
        status="completed",
        message=f"Planista: rozpoznałem dokument. {discovery_conclusion}",
        purpose="Określić, czy dokument wymaga kolejnych, ograniczonych odczytów.",
    )
    yield {
        "type": "editorial_adaptive_plan",
        "id": edit_id,
        "adaptive_plan": adaptive_plan,
    }
    yield notifier.notify(
        role="Reader",
        phase="document_reading",
        status="started",
        message="Reader: zaczynam czytanie dokumentu.",
        purpose="Zbudować handoff całości przed planowaniem redakcji.",
    )
    document_handoff: dict[str, object] = {
        "summary": "",
        "continuity": [],
        "voice": [],
        "open_questions": [],
    }
    for section in section_plan:
        handoff_in = document_handoff
        yield notifier.notify(
            role="Reader",
            phase="read_lines",
            status="started",
            message=f"Reader: czytam linie L{section['line_start']}-L{section['line_end']}.",
            line_start=int(section["line_start"]),
            line_end=int(section["line_end"]),
            purpose=str(section["reading_purpose"]),
        )
        read_result = _read_editorial_lines(
            original_text,
            int(section["line_start"]),
            int(section["line_end"]),
            execution_log,
        )
        reading_context = "\n\n".join([
            f"TYTUŁ/PROJEKT: {title or 'Bez tytułu'}",
            f"TRYB CZYTANIA: {section['reading_mode']}",
            f"CEL CZYTANIA: {section['reading_purpose']}",
            f"NARZĘDZIA: {', '.join(str(tool) for tool in section['reading_tools'])}",
            f"WYWOŁANIE read_lines({section['line_start']}, {section['line_end']})",
            f"CEL HANDOFFU: {section['handoff_goal']}",
            "DOTYCHCZASOWY HANDOFF:\n" + json.dumps(document_handoff, ensure_ascii=False),
            "WYNIK NARZĘDZIA read_lines:\n" + str(read_result["content"]),
        ])
        discovery_response = call_role(
            phase="discovery",
            role="reader_handoff",
            system_prompt=EDITORIAL_DISCOVERY_INSTRUCTION,
            messages=[{"role": "user", "content": reading_context}],
        )
        discovery_payload = _parse_json_dict(discovery_response)
        updated_handoff = _normalize_document_handoff(discovery_payload)
        if any(updated_handoff.values()):
            document_handoff = updated_handoff
        raw_handoff_out = discovery_payload.get("handoff_out")
        section["handoff_out"] = _normalize_marked_notes(raw_handoff_out, "[FAKT]")
        section["handoff_in"] = handoff_in
        section["status"] = "read"
        unread_after = []
        if int(read_result["line_end"]) < len(original_text.splitlines()):
            unread_after.append({
                "line_start": int(read_result["line_end"]) + 1,
                "line_end": len(original_text.splitlines()),
                "reason": "Poza zakresem tego odczytu; oczekuje na kolejną porcję.",
            })
        section["reading_audit"] = {
            "status": "completed",
            "purpose": section["reading_purpose"],
            "reason": section["reading_reason"],
            "requested_range": {
                "line_start": section["line_start"],
                "line_end": section["line_end"],
            },
            "read_range": {
                "line_start": read_result["line_start"],
                "line_end": read_result["line_end"],
            },
            "skipped_within_range": [],
            "unread_after": unread_after,
            "findings": _normalize_reading_findings(discovery_payload),
            "open_questions": _normalize_marked_notes(
                discovery_payload.get("open_questions_for_reading"),
                "[PYTANIE]",
            ),
        }
        reader_entry = {
            "cycle": 0,
            "role": "reader_handoff",
            "label": f"Czytanie {section['id']} L{section['line_start']}-L{section['line_end']}",
            "content": json.dumps(
                {
                    "mode": section["reading_mode"],
                    "purpose": section["reading_purpose"],
                    "reason": section["reading_reason"],
                    "tools": section["reading_tools"],
                    "audit": section["reading_audit"],
                    "handoff_goal": section["handoff_goal"],
                    "handoff_out": section["handoff_out"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        }
        transcript.append(reader_entry)
        historical_outputs.append(reader_entry)
        _write_debate_snapshot(build_record(cycles_completed=0, status="running"))
        yield notifier.notify(
            role="Reader",
            phase="read_lines",
            status="completed",
            message=f"Reader: zakończyłem czytanie linii L{read_result['line_start']}-L{read_result['line_end']}.",
            line_start=int(read_result["line_start"]),
            line_end=int(read_result["line_end"]),
            purpose="Przekazać ustalenia i pytania otwarte do następnej porcji.",
        )
        yield {
            "type": "editorial_reading",
            "id": edit_id,
            "section": {key: value for key, value in section.items() if key != "text"},
        }

    yield notifier.notify(
        role="Reader",
        phase="document_reading",
        status="completed",
        message="Reader: zakończyłem czytanie dokumentu.",
        purpose="Wszystkie zaplanowane porcje zostały przeczytane.",
    )
    reader_step["status"] = "completed"
    reader_step["conclusion"] = (
        f"Odczytano {len(section_plan)} z {len(section_plan)} porcji; handoff jest gotowy do syntezy."
    )
    planning_step = adaptive_steps[2]
    assert isinstance(planning_step, dict)
    planning_step["status"] = "working"
    _write_debate_snapshot(build_record(cycles_completed=0, status="running"))
    yield notifier.notify(
        role="Planista",
        phase="planning",
        status="started",
        message="Planista: wyciągam wnioski z handoffu i ustalam plan redakcji.",
        purpose="Wybrać warstwy wynikające z odczytu, bez planowania kontroli dla formalności.",
    )
    yield {
        "type": "editorial_adaptive_plan",
        "id": edit_id,
        "adaptive_plan": adaptive_plan,
    }
    yield notifier.notify(
        role="Reader",
        phase="handoff_synthesis",
        status="working",
        message="Reader: syntezuję handoff całości.",
        purpose="Scalić ustalenia z porcji w kontekst dla planisty.",
    )
    planner_context = "\n\n".join([
        f"TYTUŁ/PROJEKT: {title or 'Bez tytułu'}",
        f"BRIEF REDAKCYJNY:\n{brief}" if brief else "",
        "KOŃCOWY HANDOFF PO SEKWENCYJNYM CZYTANIU:\n"
        + json.dumps(document_handoff, ensure_ascii=False),
        "MANIFEST PORCJI I DOSTĘPNYCH NARZĘDZI:\n"
        + json.dumps(
            [
                {key: value for key, value in section.items() if key not in {"text", "handoff_in", "handoff_out"}}
                for section in section_plan
            ],
            ensure_ascii=False,
        ),
    ]).strip()
    planner_response = call_role(
        phase="planning",
        role="planner",
        system_prompt=EDITORIAL_PLANNER_INSTRUCTION,
        messages=[{"role": "user", "content": planner_context}],
    )
    plan = _normalize_editorial_plan(_parse_json_dict(planner_response))
    if not any(plan["document_handoff"].values()):
        plan["document_handoff"] = document_handoff
    planning_step["status"] = "completed"
    planning_step["conclusion"] = "Handoff został przekształcony w minimalny plan dalszej redakcji."
    layers_step = adaptive_steps[3]
    assert isinstance(layers_step, dict)
    layers_step["status"] = "completed"
    layers_step["conclusion"] = (
        f"Znaleziono {len(plan['layers'])} warstw problemów do zbadania i zweryfikowania; "
        "uruchamiam dalszy krok redakcji."
    )
    adaptive_plan["status"] = "completed"
    yield notifier.notify(
        role="Reader",
        phase="handoff_synthesis",
        status="completed",
        message="Reader: synteza handoffu zakończona.",
        purpose="Przekazać spójny kontekst do planowania warstw.",
    )
    workflow["plan"] = plan
    workflow["sections"] = [
        {
            **section,
            "status": "planned",
            "plan_notes": plan["handoff_notes"] if index == 0 else [],
            "artifacts": [],
        }
        for index, section in enumerate(section_plan)
    ]
    workflow["status"] = "editing"
    planner_entry = {
        "cycle": 0,
        "role": "planner",
        "label": "Planista całości i warstw",
        "content": json.dumps(plan, ensure_ascii=False, indent=2),
    }
    transcript.append(planner_entry)
    historical_outputs.append(planner_entry)
    _write_debate_snapshot(build_record(cycles_completed=0, status="running"))
    yield notifier.notify(
        role="Planista",
        phase="planning",
        status="completed",
        message=f"Planista: znalazłem {len(plan['layers'])} warstw problemów do zbadania i zweryfikowania.",
        purpose="Przekazać zatwierdzony zakres dalszym rolom redakcyjnym.",
    )
    yield {
        "type": "editorial_adaptive_plan",
        "id": edit_id,
        "adaptive_plan": adaptive_plan,
    }
    yield {
        "type": "editorial_workflow_plan",
        "id": edit_id,
        "plan": plan,
        "sections": [
            {
                "id": section["id"],
                "paragraph_start": section["paragraph_start"],
                "paragraph_end": section["paragraph_end"],
                "line_start": section["line_start"],
                "line_end": section["line_end"],
                "read_window_lines": section["read_window_lines"],
                "reading_mode": section["reading_mode"],
                "reading_purpose": section["reading_purpose"],
                "reading_reason": section["reading_reason"],
                "reading_tools": section["reading_tools"],
                "handoff_goal": section["handoff_goal"],
                "reading_audit": section["reading_audit"],
            }
            for section in workflow["sections"]
        ],
    }
    yield {
        "type": "editorial_role_output",
        "cycle": 0,
        "role": "planner",
        "label": "Planista całości i warstw",
        "content": planner_entry["content"],
    }

    cycles_completed = 0
    try:
        for cycle in range(1, max_cycles + 1):
            cycle_outputs: dict[str, str] = {}
            context_block = _build_editorial_context(
                title=title,
                brief=brief,
                original_text=original_text,
                current_text=current_text,
                cycle=cycle,
                clean_model_signatures=clean_model_signatures,
            )

            for spec in ROLE_SPECS:
                role_output = call_role(
                    phase="analysis",
                    role=spec["key"],
                    system_prompt=spec["instruction"],
                    messages=[
                        {
                            "role": "user",
                            "content": _build_role_message(
                                context_block=context_block,
                                historical_outputs=historical_outputs,
                                cycle_outputs=cycle_outputs,
                            ),
                        }
                    ],
                ).strip()
                cycle_outputs[spec["key"]] = role_output
                entry = {
                    "cycle": cycle,
                    "role": spec["key"],
                    "label": spec["label"],
                    "content": role_output,
                }
                transcript.append(entry)
                historical_outputs.append(entry)
                _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="running"))
                yield {
                    "type": "editorial_role_output",
                    "cycle": cycle,
                    "role": spec["key"],
                    "label": spec["label"],
                    "content": role_output,
                }

            patch_response = call_role(
                phase="patch_proposal",
                role="patch_rewriter",
                system_prompt=PATCH_REWRITER_INSTRUCTION,
                messages=[
                    {
                        "role": "user",
                        "content": _build_role_message(
                            context_block=context_block,
                            historical_outputs=historical_outputs,
                            cycle_outputs=cycle_outputs,
                        ),
                    }
                ],
            )
            proposed_patches = _build_patchset(_parse_json_object(patch_response, "patches"))
            proposal_content = json.dumps({"patches": proposed_patches}, ensure_ascii=False, indent=2)
            proposal_entry = {
                "cycle": cycle,
                "role": "patch_rewriter",
                "label": "Rewriter patchy",
                "content": proposal_content,
            }
            transcript.append(proposal_entry)
            historical_outputs.append(proposal_entry)
            _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="running"))
            yield {
                "type": "editorial_role_output",
                "cycle": cycle,
                "role": "patch_rewriter",
                "label": "Rewriter patchy",
                "content": proposal_content,
            }

            validation_response = call_role(
                phase="patch_validation",
                role="patch_validator",
                system_prompt=PATCH_VALIDATOR_INSTRUCTION,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            _build_role_message(
                                context_block=context_block,
                                historical_outputs=historical_outputs,
                                cycle_outputs=cycle_outputs,
                            )
                            + "\n\nPROPONOWANE PATCHES:\n"
                            + proposal_content
                        ),
                    }
                ],
            )
            verdicts = _parse_json_object(validation_response, "verdicts")
            current_text, accepted_patches, rejected_patches = _apply_accepted_patches(
                current_text,
                proposed_patches,
                verdicts,
            )
            current_manifest = store_editorial_document(
                editorial_id=edit_id,
                version=cycle,
                text=current_text,
            )
            workflow["document_storage"] = {
                "source": source_manifest,
                "current": current_manifest,
            }
            store_patch_decisions(
                editorial_id=edit_id,
                cycle=cycle,
                accepted=accepted_patches,
                rejected=rejected_patches,
            )
            _append_execution_log(
                execution_log,
                "patch_application",
                status="completed",
                cycle=cycle,
                proposed_patches=proposed_patches,
                verdicts=verdicts,
                accepted_patches=accepted_patches,
                rejected_patches=rejected_patches,
            )
            validation_content = json.dumps(
                {
                    "verdicts": verdicts,
                    "accepted": accepted_patches,
                    "rejected": rejected_patches,
                },
                ensure_ascii=False,
                indent=2,
            )
            validation_entry = {
                "cycle": cycle,
                "role": "patch_validator",
                "label": "Walidator patchy",
                "content": validation_content,
            }
            transcript.append(validation_entry)
            historical_outputs.append(validation_entry)
            _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="running"))
            yield {
                "type": "editorial_role_output",
                "cycle": cycle,
                "role": "patch_validator",
                "label": "Walidator patchy",
                "content": validation_content,
            }

            synthesis_content = json.dumps(
                {
                    "accepted_patch_ids": [patch["id"] for patch in accepted_patches],
                    "rejected_patch_ids": [patch["id"] for patch in rejected_patches],
                    "method": "deterministyczne zastosowanie zatwierdzonych podmian",
                },
                ensure_ascii=False,
                indent=2,
            )
            synthesis_entry = {
                "cycle": cycle,
                "role": "synthesizer",
                "label": "Syntezator zatwierdzonych patchy",
                "content": synthesis_content,
            }
            transcript.append(synthesis_entry)
            historical_outputs.append(synthesis_entry)
            _append_execution_log(
                execution_log,
                "synthesis",
                status="completed",
                cycle=cycle,
                result=json.loads(synthesis_content),
            )
            cycles_completed = cycle
            _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="running"))
            yield {
                "type": "editorial_role_output",
                "cycle": cycle,
                "role": "synthesizer",
                "label": "Syntezator zatwierdzonych patchy",
                "content": synthesis_content,
            }
            yield {
                "type": "editorial_draft",
                "cycle": cycle,
                "text": current_text,
            }

    except GeneratorExit:
        _append_execution_log(execution_log, "session", status="cancelled")
        _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="cancelled"))
        raise
    except Exception as exc:
        _append_execution_log(execution_log, "session", status="failed", error=str(exc))
        _write_debate_snapshot(
            build_record(cycles_completed=cycles_completed, status="failed", error=str(exc))
        )
        raise

    _append_execution_log(
        execution_log,
        "session",
        status="completed",
        cycles_completed=cycles_completed,
    )
    _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="completed"))

    yield {
        "type": "editorial_end",
        "id": edit_id,
        "title": title,
        "final_text": current_text,
        "cycles_completed": cycles_completed,
    }