from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

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
EDITORIAL_MAX_EXECUTION_TASKS = 24
EDITORIAL_SHORT_DOCUMENT_PLANNER_LINES = 120
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
Każdy wpis reading_protocol musi jawnie określać cel czytania, tryb i narzędzie. Następnie wybierz
wyłącznie zakresy wymagające faktycznej redakcji jako execution_tasks. Nie planuj pełnego dokumentu
dla formalności: możesz wskazać np. L400-L520 i L1140-L1260, gdy tylko one wymagają pracy. Każde
zadanie ma mieć 1-3 warstwy z listy layers. Zwróć wyłącznie JSON:
{"document_handoff":{"summary":"krótka mapa całości","continuity":["L12-L18 [FAKT] fakt lub relacja do zachowania"],"voice":["L42-L57 [INTERPRETACJA] cecha głosu autora"],"open_questions":["L88 [PYTANIE] nierozstrzygnięta kwestia"]},"whole_text_notes":["krótka obserwacja"],"layers":[{"id":"continuity","label":"Ciągłość zdarzeń","reason":"co sprawdzić między porcjami","priority":1}],"reading_protocol":[{"mode":"range","purpose":"sprawdzić ciągłość między L201-L400","tool":"read_lines","line_start":201,"line_end":400,"handoff_goal":"przekazać ustalenia potrzebne następnej porcji"}],"execution_tasks":[{"id":"task-1","line_start":400,"line_end":520,"layers":["continuity"],"purpose":"zweryfikować przejście pojęciowe i ewentualnie przygotować lokalne patche"}],"handoff_notes":["L12-L18 [FAKT] polecenie dla kolejnych porcji"]}

Jeżeli wiadomość zawiera sekcję KRÓTKI DOKUMENT DO INSPEKCJI, jest to dodatkowy dowód, który możesz
oceniać na poziomie pojedynczych zdań. Dokument w całości może być wtedy jednym zadaniem tylko dlatego,
że mieści się w tym małym, zamkniętym zakresie. Wybierz takie zadanie wyłącznie dla konkretnej,
cytowalnej usterki; nie udawaj problemów ani nie proponuj patchy na tym etapie.
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

Jesteś rygorystycznym walidatorem patchy. Dla każdego patcha dostajesz dossier: cytat źródłowy,
warianty, kontekst przed i po fragmencie, istotne ustalenia o rejestrach dokumentu i diagnozy ról.
Porównaj patch z ORYGINAŁEM, AKTUALNĄ WERSJĄ, BRIEFEM i diagnozą. ACCEPT wydaj wyłącznie dla
lokalnej korekty konkretnego błędu, gdy zakres ingerencji jest najmniejszy możliwy.

REJESTR, metafora, urwane zdanie, kolokwializm, popkulturowe odwołanie lub aforystyczne domknięcie
nie są błędem tylko dlatego, że odbiegają od tonu sąsiednich zdań lub nie dodają nowej informacji.
Patch kategorii REJESTR zaakceptuj wyłącznie, gdy dossier wskazuje konkretną regresję funkcji
retorycznej (np. zaciera referent, przeczy ustalonemu rejestrowi danego modułu albo powtarza tę samą
funkcję bez wariacji). Jeżeli mapa rejestrów lub diagnoza opisuje ten zabieg jako celowy, wydaj REJECT
bez jednoznacznego dowodu konfliktu wewnątrz tekstu. Nie zastępuj metafory objaśnieniem tylko dlatego,
że jest intensywna.

REJECT wydaj w razie wątpliwości, dla decyzji autorskiej, nowego faktu, nowej czynności, zmiany
metafory bez błędu albo zmiany struktury, tempa, sensu czy głosu autora. Patch o scope "paragraph"
zaakceptuj tylko, gdy mniejsza ingerencja nie może usunąć konkretnego błędu. Nie wystarczy, że wariant
usuwa wskazany problem: sprawdź również, czy nie tworzy nowego błędu językowego, niezręczności,
powtórzenia, sztucznej sygnatury modelowej albo pogorszenia rytmu. Dla zmian innych niż czysta
interpunkcja porównaj wszystkie warianty z ORYGINAŁEM. Wybierz wyłącznie wariant o najmniejszej
zmianie znaczenia i najlepszej naturalności językowej. Jeżeli żaden wariant nie jest wyraźnie lepszy
od oryginału, wydaj REJECT. Bezsporne błędy językowe, gramatyczne, referencyjne i ciągłości czynności
muszą zostać naprawione: zachowawczość nie jest podstawą do pozostawienia realnego błędu. Zwróć
wyłącznie poprawny JSON:
{"verdicts":[{"id":"p1","decision":"ACCEPT" lub "REJECT","selected_variant_id":"p1-v1" lub null,"reason":"krótkie, konkretne uzasadnienie wraz z oceną regresji"}]}
"""
).strip()

EDITORIAL_INTEGRITY_VERIFIER_INSTRUCTION = (
    EDITORIAL_CONSERVATION_CHARTER
    + """

Jesteś niezależnym Weryfikatorem integralności redakcji. Otrzymujesz wersję sprzed tej iteracji,
kandydacką wersję po zaakceptowanych patchach, porównania fragmentów w kontekście, mapę rejestrów
dokumentu i wcześniejsze diagnozy. Oceń różnicę oraz skalę wykonanej pracy w perspektywie całego
utworu, nie tylko poprawność pojedynczego patcha.

Zachowuj tylko zmiany, które dają wyraźny zysk redakcyjny. Cofnij zmianę, gdy poprawia powierzchowną
logikę lub klarowność kosztem celowego głosu, rytmu, metafory albo świadomej zmiany rejestru. Zwróć
uwagę na sprzeczności: diagnostyka nie może najpierw uznać rejestru za celowy, a następnie usuwać go
bez nowego, konkretnego dowodu. Oceń też, czy suma zmian jest proporcjonalna do realnego zysku;
aparatura procesu nie jest argumentem za ingerencją. Nie projektuj nowych poprawek.

Zwróć wyłącznie JSON:
{"assessment":{"verdict":"plus|minus|mixed|neutral","scope":"krótka ocena skali pracy","reason":"bilans zysku i strat","contradictions":["konkretna sprzeczność lub []"]},"verdicts":[{"id":"p1","decision":"KEEP" lub "REVERT","reason":"konkretna decyzja w świetle kontekstu i rejestru"}]}
"""
).strip()

EDITORIAL_SUMMARIZER_INSTRUCTION = """
Jesteś redaktorem sporządzającym końcową notę z procesu redakcyjnego. Otrzymujesz wyłącznie
plan, zadania zakresowe i ich artefakty: decyzje o patchach oraz oceny integralności. Nie dostajesz
tekstu dokumentu i nie wolno ci dopowiadać zmian, cytatów, problemów ani efektów, których nie ma w
danych. Napisz po polsku krótkie podsumowanie dla autora: 2-4 zdania, zwykły tekst bez tytułu,
markdownu, list i technicznych identyfikatorów. Powiedz, jakie zakresy i warstwy sprawdzono, co
zostało zastosowane albo świadomie pozostawione oraz dlaczego, jeśli wynika to z assessmentów.
Jeżeli nie zastosowano patchy, nazwij to zachowawczą decyzją wynikającą z walidacji, a nie brakiem
pracy. Rozróżniaj źródło decyzji: brak proposed_patch_ids oznacza, że Rewriter nie zaproponował
bezpiecznej ingerencji; proposed_patch_ids przy braku accepted_patch_ids oznacza odrzucenie przez
walidację albo weryfikację integralności. Nie przypisuj braku propozycji walidacji. Nie podawaj
samych liczników jako substytutu podsumowania.
""".strip()


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


def _patch_context(text: str, source: str, *, radius: int = 5) -> str:
    occurrences = text.count(source)
    if occurrences != 1:
        return f"Brak jednoznacznego kontekstu: cytat występuje {occurrences} razy."
    source_start = text.index(source)
    line_start = text.count("\n", 0, source_start) + 1
    source_end = source_start + len(source)
    line_end = text.count("\n", 0, source_end) + 1
    return _numbered_editorial_lines(
        text,
        max(1, line_start - radius),
        line_end + radius,
    )


def _build_patch_validation_message(
    *,
    context_block: str,
    historical_outputs: list[dict[str, str | int]],
    cycle_outputs: dict[str, str],
    plan: dict[str, object],
    current_text: str,
    patches: list[dict[str, object]],
) -> str:
    compact_context = "\n\n".join(
        section
        for section in context_block.split("\n\n")
        if not section.startswith("ORYGINAŁ INPUT:")
        and not section.startswith("AKTUALNA WERSJA ROBOCZA:")
    )
    base = _build_role_message(
        context_block=compact_context,
        historical_outputs=historical_outputs,
        cycle_outputs=cycle_outputs,
    )
    document_handoff = plan.get("document_handoff")
    register_map = (
        document_handoff.get("voice")
        if isinstance(document_handoff, dict)
        else []
    )
    dossiers = []
    for patch in patches:
        source = str(patch["source"])
        variants = "\n".join(
            f"- {variant['id']}: {variant['replacement']}"
            for variant in patch["variants"]
        )
        dossiers.append(
            "\n".join([
                f"PATCH {patch['id']} | KATEGORIA: {patch['category']}",
                f"DIAGNOZA REWRITERA: {patch['reason']}",
                "KONTEKST AKTUALNEJ WERSJI:",
                _patch_context(current_text, source),
                "WARIANTY:",
                variants,
            ])
        )
    return "\n\n".join([
        base,
        "MAPA CELOWYCH REJESTRÓW Z HANDOFFU:\n" + json.dumps(register_map, ensure_ascii=False),
        "DOSSIERS PATCHY (oceniaj każdy w kontekście):\n" + "\n\n".join(dossiers),
    ])


def _build_integrity_verification_message(
    *,
    plan: dict[str, object],
    cycle_outputs: dict[str, str],
    before_text: str,
    candidate_text: str,
    accepted_patches: list[dict[str, object]],
) -> str:
    comparisons = []
    for patch in accepted_patches:
        comparisons.append(
            "\n".join([
                f"PATCH {patch['id']} | {patch['category']}",
                f"UZASADNIENIE: {patch['reason']}",
                "PRZED:",
                _patch_context(before_text, str(patch["source"])),
                "PO:",
                _patch_context(candidate_text, str(patch["replacement"])),
            ])
        )
    return "\n\n".join([
        "MAPA DOKUMENTU I REJESTRÓW:\n" + json.dumps(plan.get("document_handoff", {}), ensure_ascii=False),
        "DIAGNOZY BIEŻĄCEJ ITERACJI:\n" + json.dumps(cycle_outputs, ensure_ascii=False),
        "PORÓWNANIA ZATWIERDZONYCH PATCHY:\n" + "\n\n".join(comparisons),
    ])


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


def _normalize_editorial_plan(payload: dict[str, object], *, total_lines: int) -> dict[str, object]:
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

    execution_tasks: list[dict[str, object]] = []
    raw_tasks = payload.get("execution_tasks")
    seen_task_ids: set[str] = set()
    if isinstance(raw_tasks, list):
        for index, raw_task in enumerate(raw_tasks, start=1):
            if len(execution_tasks) >= EDITORIAL_MAX_EXECUTION_TASKS or not isinstance(raw_task, dict):
                continue
            task_id = str(raw_task.get("id") or f"task-{index}").strip().lower()
            line_start = raw_task.get("line_start")
            line_end = raw_task.get("line_end")
            raw_task_layers = raw_task.get("layers")
            task_layers = [
                str(layer).strip().lower()
                for layer in raw_task_layers
                if str(layer).strip().lower() in EDITORIAL_LAYERS
            ] if isinstance(raw_task_layers, list) else []
            purpose = str(raw_task.get("purpose") or "").strip()[:500]
            if (
                not task_id
                or task_id in seen_task_ids
                or not isinstance(line_start, int)
                or not isinstance(line_end, int)
                or line_start < 1
                or line_end < line_start
                or line_end > total_lines
                or line_end - line_start + 1 > EDITORIAL_MAX_READ_WINDOW_LINES
                or not task_layers
                or not purpose
            ):
                continue
            seen_task_ids.add(task_id)
            execution_tasks.append({
                "id": task_id,
                "line_start": line_start,
                "line_end": line_end,
                "layers": list(dict.fromkeys(task_layers))[:3],
                "purpose": purpose,
                "status": "planned",
                "artifacts": [],
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
        "execution_tasks": execution_tasks,
        "handoff_notes": _normalize_marked_notes(payload.get("handoff_notes"), "[FAKT]"),
    }


def _ensure_short_document_execution_task(
    plan: dict[str, object],
    *,
    total_lines: int,
) -> None:
    if (
        total_lines > EDITORIAL_SHORT_DOCUMENT_PLANNER_LINES
        or not isinstance(plan.get("execution_tasks"), list)
        or plan["execution_tasks"]
    ):
        return

    layers = plan.get("layers")
    if not isinstance(layers, list):
        layers = []
        plan["layers"] = layers
    existing_layer_ids = {
        str(layer.get("id") or "")
        for layer in layers
        if isinstance(layer, dict)
    }
    for layer_id, label, reason, priority in (
        ("language", "Język i interpunkcja", "Sprawdzić lokalne usterki składniowe, językowe i interpunkcyjne.", 1),
        ("register", "Rejestr", "Sprawdzić tylko konkretne regresje rejestru, bez normalizowania głosu autora.", 2),
    ):
        if layer_id not in existing_layer_ids:
            layers.append({
                "id": layer_id,
                "label": label,
                "reason": reason,
                "priority": priority,
            })
    plan["execution_tasks"].append({
        "id": "task-short-document-baseline",
        "line_start": 1,
        "line_end": total_lines,
        "layers": ["language", "register"],
        "purpose": (
            "Wykonać ograniczoną kontrolę lokalnych usterek językowych, składniowych i interpunkcyjnych "
            "w krótkim, zamkniętym dokumencie; zachować głos autora i nie tworzyć zmian bez konkretnej podstawy."
        ),
        "status": "planned",
        "artifacts": [],
    })


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


def _task_text(text: str, line_start: int, line_end: int) -> str:
    return "".join(text.splitlines(keepends=True)[line_start - 1:line_end])


def _role_specs_for_layers(layers: list[str]) -> list[dict[str, str]]:
    selected = {"marker"}
    if any(layer in {"continuity", "logic", "reference"} for layer in layers):
        selected.add("coherence_guard")
    if any(layer in {"language", "register", "repetition"} for layer in layers):
        selected.add("critic")
    return [spec for spec in ROLE_SPECS if spec["key"] in selected]


def _scope_patch_ids(patches: list[dict[str, object]], task_id: str) -> list[dict[str, object]]:
    scoped: list[dict[str, object]] = []
    for patch in patches:
        scoped.append({
            **patch,
            "id": f"{task_id}:{patch['id']}",
            "variants": [
                {"id": f"{task_id}:{variant['id']}", "replacement": variant["replacement"]}
                for variant in patch["variants"]
            ],
        })
    return scoped


def _normalize_patch_decision_ids(
    verdicts: list[dict[str, object]],
    patches: list[dict[str, object]],
) -> list[dict[str, object]]:
    def resolve_id(raw_id: object, available_ids: set[str]) -> str:
        value = str(raw_id or "").strip()
        if value in available_ids:
            return value
        matches = [candidate for candidate in available_ids if candidate.endswith(f":{value}")]
        return matches[0] if len(matches) == 1 else value

    patch_ids = {str(patch["id"]) for patch in patches}
    normalized: list[dict[str, object]] = []
    for verdict in verdicts:
        patch_id = resolve_id(verdict.get("id"), patch_ids)
        selected_variant_id = verdict.get("selected_variant_id")
        patch = next((item for item in patches if item["id"] == patch_id), None)
        if patch is not None and selected_variant_id:
            variant_ids = {str(variant["id"]) for variant in patch["variants"]}
            selected_variant_id = resolve_id(selected_variant_id, variant_ids)
        normalized.append({
            **verdict,
            "id": patch_id,
            "selected_variant_id": selected_variant_id,
        })
    return normalized


def _patches_in_task(
    patches: list[dict[str, object]],
    *,
    current_text: str,
    task_text: str,
) -> list[dict[str, object]]:
    return [
        patch
        for patch in patches
        if current_text.count(str(patch["source"])) == 1
        and task_text.count(str(patch["source"])) == 1
    ]


def _build_task_context(
    *,
    title: str,
    brief: str,
    cycle: int,
    task: dict[str, object],
    document_handoff: dict[str, object],
    text: str,
    clean_model_signatures: bool,
) -> str:
    parts = [
        f"TYTUŁ/PROJEKT: {title or 'Bez tytułu'}",
        f"ITERACJA: {cycle}",
        f"ZADANIE: {task['id']} | LINIE L{task['line_start']}-L{task['line_end']}",
        "WARSTWY: " + ", ".join(str(layer) for layer in task["layers"]),
        f"CEL: {task['purpose']}",
        "HANDOFF DOKUMENTU:\n" + json.dumps(document_handoff, ensure_ascii=False),
    ]
    if clean_model_signatures:
        parts.append(CLEAN_MODEL_SIGNATURES_INSTRUCTION)
    if brief:
        parts.append(f"BRIEF REDAKCYJNY:\n{brief}")
    parts.append(
        "FRAGMENT DO ANALIZY I REDAKCJI:\n"
        + _numbered_editorial_lines(text, int(task["line_start"]), int(task["line_end"]))
    )
    return "\n\n".join(parts)


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
        if source.count("\n") != replacement.count("\n"):
            rejected.append({**patch, "reason": "Patch zmienia liczbę linii i unieważniłby zakresy zaplanowanych zadań."})
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


def _build_editorial_summary_fallback(
    *,
    title: str,
    cycles_completed: int,
    execution_log: list[dict[str, object]],
) -> str:
    task_runs = [
        entry
        for entry in execution_log
        if entry.get("event") == "task_application" and entry.get("status") == "completed"
    ]
    accepted_count = sum(len(entry.get("accepted_patches") or []) for entry in task_runs)
    rejected_count = sum(len(entry.get("rejected_patches") or []) for entry in task_runs)
    cycle_label = "iterację" if cycles_completed == 1 else "iteracje"
    return (
        f"{title}: zakończono {cycles_completed} {cycle_label}, "
        f"zadania zakresowe: {len(task_runs)}, zastosowano "
        f"{accepted_count} zatwierdzonych patchy i odrzucono {rejected_count}."
    )


def _build_editorial_summary_message(
    *,
    title: str,
    brief: str,
    cycles_completed: int,
    plan: dict[str, object],
) -> str:
    tasks = plan.get("execution_tasks")
    task_artifacts = []
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_artifacts.append({
                "id": task.get("id"),
                "line_start": task.get("line_start"),
                "line_end": task.get("line_end"),
                "layers": task.get("layers"),
                "purpose": task.get("purpose"),
                "artifacts": task.get("artifacts", []),
            })
    return "\n\n".join([
        f"TYTUŁ: {title}",
        f"BRIEF: {brief or 'brak dodatkowego briefu'}",
        f"UKOŃCZONE ITERACJE: {cycles_completed}",
        "WARSTWY PLANU:\n" + json.dumps(plan.get("layers", []), ensure_ascii=False),
        "UWAGI CAŁOŚCIOWE:\n" + json.dumps(plan.get("whole_text_notes", []), ensure_ascii=False),
        "ARTEFAKTY ZADAŃ:\n" + json.dumps(task_artifacts, ensure_ascii=False),
    ])


def _replace_adaptive_execution_steps(
    adaptive_plan: dict[str, object],
    plan: dict[str, object],
) -> None:
    steps = adaptive_plan.get("steps")
    if not isinstance(steps, list):
        return
    lifecycle_steps = [
        step
        for step in steps
        if isinstance(step, dict) and str(step.get("id") or "") != "layers"
    ]
    tasks = plan.get("execution_tasks")
    execution_steps: list[dict[str, object]] = []
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "").strip()
            if not task_id:
                continue
            execution_steps.append({
                "id": f"execution:{task_id}",
                "label": f"{task_id} | L{task.get('line_start')}-L{task.get('line_end')}",
                "purpose": str(task.get("purpose") or ""),
                "conclusion": "Wybrane przez Planistę na podstawie handoffu dokumentu.",
                "status": "planned",
            })
    if not execution_steps:
        execution_steps.append({
            "id": "no_execution_tasks",
            "label": "Pozostawić dokument bez ingerencji",
            "purpose": "Planista nie wskazał zakresu z bezsporną podstawą do lokalnej redakcji.",
            "conclusion": "Brak zadań zakresowych jest decyzją planu, nie pominiętym krokiem.",
            "status": "completed",
        })
    adaptive_plan["steps"] = [*lifecycle_steps, *execution_steps]


def _update_adaptive_execution_step(
    adaptive_plan: dict[str, object],
    *,
    task_id: str,
    status: str,
    conclusion: str,
) -> None:
    steps = adaptive_plan.get("steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and step.get("id") == f"execution:{task_id}":
            step["status"] = status
            step["conclusion"] = conclusion
            return


def _adaptive_plan_event(*, edit_id: str, adaptive_plan: dict[str, object]) -> dict[str, object]:
    return {
        "type": "editorial_adaptive_plan",
        "id": edit_id,
        "adaptive_plan": json.loads(json.dumps(adaptive_plan)),
    }


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
    process_id = str(uuid4())
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
    editorial_summary = _build_editorial_summary_fallback(
        title=title,
        cycles_completed=0,
        execution_log=execution_log,
    )
    workflow: dict[str, object] = {
        "process_id": process_id,
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
        max_tokens_override: int | None = None,
    ) -> str:
        role_max_tokens = max_tokens_override or max_tokens
        request = {
            "provider": provider,
            "model": model,
            "max_tokens": role_max_tokens,
            "system_prompt": system_prompt,
            "messages": messages,
        }
        try:
            response = _call_editorial_role(
                provider=provider,
                model=model,
                max_tokens=role_max_tokens,
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
            "process_id": process_id,
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
            "summary": editorial_summary,
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
        "process_id": process_id,
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
    yield _adaptive_plan_event(edit_id=edit_id, adaptive_plan=adaptive_plan)
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
    yield _adaptive_plan_event(edit_id=edit_id, adaptive_plan=adaptive_plan)
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
        (
            "KRÓTKI DOKUMENT DO INSPEKCJI:\n" + _numbered_editorial_text(current_text)
            if total_lines <= EDITORIAL_SHORT_DOCUMENT_PLANNER_LINES
            else ""
        ),
    ]).strip()
    planner_response = call_role(
        phase="planning",
        role="planner",
        system_prompt=EDITORIAL_PLANNER_INSTRUCTION,
        messages=[{"role": "user", "content": planner_context}],
    )
    plan = _normalize_editorial_plan(
        _parse_json_dict(planner_response),
        total_lines=total_lines,
    )
    _ensure_short_document_execution_task(plan, total_lines=total_lines)
    if not any(plan["document_handoff"].values()):
        plan["document_handoff"] = document_handoff
    planning_step["status"] = "completed"
    planning_step["conclusion"] = "Handoff został przekształcony w minimalny plan dalszej redakcji."
    _replace_adaptive_execution_steps(adaptive_plan, plan)
    adaptive_plan["status"] = "working" if plan["execution_tasks"] else "completed"
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
    if not plan["execution_tasks"]:
        yield notifier.notify(
            role="Planista",
            phase="task_selection",
            status="completed",
            message="Planista: nie wybrałem żadnego poprawnego zadania zakresowego.",
            purpose=(
                "Brak execution_tasks oznacza brak ingerencji w dokument. "
                "Sprawdź w logu odpowiedź Planisty oraz warstwy i handoff."
            ),
        )
    yield _adaptive_plan_event(edit_id=edit_id, adaptive_plan=adaptive_plan)
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
    document_revision = 0
    try:
        for cycle in range(1, max_cycles + 1):
            cycle_accepted_patches: list[dict[str, object]] = []
            cycle_rejected_patches: list[dict[str, object]] = []
            for task in plan["execution_tasks"]:
                assert isinstance(task, dict)
                task["status"] = "working"
                _update_adaptive_execution_step(
                    adaptive_plan,
                    task_id=str(task["id"]),
                    status="working",
                    conclusion="Trwa wykonanie wybranego zakresu i warstw redakcyjnych.",
                )
                yield _adaptive_plan_event(edit_id=edit_id, adaptive_plan=adaptive_plan)
                task_text = _task_text(
                    current_text,
                    int(task["line_start"]),
                    int(task["line_end"]),
                )
                task_context = _build_task_context(
                    title=title,
                    brief=brief,
                    cycle=cycle,
                    task=task,
                    document_handoff=plan["document_handoff"],
                    text=current_text,
                    clean_model_signatures=clean_model_signatures,
                )
                cycle_outputs: dict[str, str] = {}
                yield notifier.notify(
                    role="Orkiestrator",
                    phase="task_execution",
                    status="started",
                    message=f"Orkiestrator: uruchamiam {task['id']} dla L{task['line_start']}-L{task['line_end']}.",
                    line_start=int(task["line_start"]),
                    line_end=int(task["line_end"]),
                    purpose=str(task["purpose"]),
                )
                yield {
                    "type": "editorial_task",
                    "id": edit_id,
                    "task": {**task, "artifacts": list(task["artifacts"])},
                }

                for spec in _role_specs_for_layers(list(task["layers"])):
                    role_output = call_role(
                        phase="analysis",
                        role=spec["key"],
                        system_prompt=spec["instruction"],
                        messages=[{"role": "user", "content": _build_role_message(
                            context_block=task_context,
                            historical_outputs=historical_outputs,
                            cycle_outputs=cycle_outputs,
                        )}],
                    ).strip()
                    cycle_outputs[spec["key"]] = role_output
                    entry = {
                        "cycle": cycle,
                        "role": spec["key"],
                        "label": f"{spec['label']} | {task['id']} L{task['line_start']}-L{task['line_end']}",
                        "content": role_output,
                    }
                    transcript.append(entry)
                    historical_outputs.append(entry)
                    yield {"type": "editorial_role_output", **entry}

                patch_response = call_role(
                    phase="patch_proposal",
                    role="patch_rewriter",
                    system_prompt=PATCH_REWRITER_INSTRUCTION,
                    messages=[{"role": "user", "content": _build_role_message(
                        context_block=task_context,
                        historical_outputs=historical_outputs,
                        cycle_outputs=cycle_outputs,
                    )}],
                )
                proposed_patches = _patches_in_task(
                    _scope_patch_ids(
                        _build_patchset(_parse_json_object(patch_response, "patches")),
                        str(task["id"]),
                    ),
                    current_text=current_text,
                    task_text=task_text,
                )
                proposal_content = json.dumps({"patches": proposed_patches}, ensure_ascii=False, indent=2)
                proposal_entry = {
                    "cycle": cycle,
                    "role": "patch_rewriter",
                    "label": f"Rewriter patchy | {task['id']} L{task['line_start']}-L{task['line_end']}",
                    "content": proposal_content,
                }
                transcript.append(proposal_entry)
                historical_outputs.append(proposal_entry)
                yield {"type": "editorial_role_output", **proposal_entry}

                validation_response = call_role(
                    phase="patch_validation",
                    role="patch_validator",
                    system_prompt=PATCH_VALIDATOR_INSTRUCTION,
                    messages=[{"role": "user", "content": _build_patch_validation_message(
                        context_block=task_context,
                        historical_outputs=historical_outputs,
                        cycle_outputs=cycle_outputs,
                        plan=plan,
                        current_text=current_text,
                        patches=proposed_patches,
                    )}],
                )
                verdicts = _normalize_patch_decision_ids(
                    _parse_json_object(validation_response, "verdicts"),
                    proposed_patches,
                )
                candidate_text, provisionally_accepted, rejected_patches = _apply_accepted_patches(
                    current_text, proposed_patches, verdicts,
                )
                integrity_response = call_role(
                    phase="integrity_verification",
                    role="integrity_verifier",
                    system_prompt=EDITORIAL_INTEGRITY_VERIFIER_INSTRUCTION,
                    messages=[{"role": "user", "content": _build_integrity_verification_message(
                        plan=plan,
                        cycle_outputs=cycle_outputs,
                        before_text=current_text,
                        candidate_text=candidate_text,
                        accepted_patches=provisionally_accepted,
                    )}],
                )
                integrity_payload = _parse_json_dict(integrity_response)
                integrity_verdicts = _normalize_patch_decision_ids(
                    _parse_json_object(integrity_response, "verdicts"),
                    provisionally_accepted,
                )
                integrity_decisions = {
                    str(verdict.get("id") or ""): str(verdict.get("decision") or "").upper()
                    for verdict in integrity_verdicts
                }
                integrity_reasons = {
                    str(verdict.get("id") or ""): str(verdict.get("reason") or "").strip()
                    for verdict in integrity_verdicts
                }
                final_verdicts = [{
                    "id": patch["id"],
                    "decision": "ACCEPT" if integrity_decisions.get(str(patch["id"])) == "KEEP" else "REJECT",
                    "selected_variant_id": patch["selected_variant_id"],
                    "reason": integrity_reasons.get(str(patch["id"]))
                    or "Weryfikator integralności nie potwierdził wystarczającego zysku redakcyjnego.",
                } for patch in provisionally_accepted]
                current_text, accepted_patches, integrity_reverted_patches = _apply_accepted_patches(
                    current_text, provisionally_accepted, final_verdicts,
                )
                rejected_patches.extend(integrity_reverted_patches)
                cycle_accepted_patches.extend(accepted_patches)
                cycle_rejected_patches.extend(rejected_patches)
                document_revision += 1
                current_manifest = store_editorial_document(
                    editorial_id=edit_id,
                    version=document_revision,
                    text=current_text,
                )
                workflow["document_storage"] = {"source": source_manifest, "current": current_manifest}
                store_patch_decisions(
                    editorial_id=edit_id,
                    cycle=cycle,
                    accepted=accepted_patches,
                    rejected=rejected_patches,
                )
                task["status"] = "done"
                _update_adaptive_execution_step(
                    adaptive_plan,
                    task_id=str(task["id"]),
                    status="completed",
                    conclusion=(
                        f"Zastosowano {len(accepted_patches)} patchy; "
                        f"odrzucono {len(rejected_patches)} po walidacji i weryfikacji integralności."
                    ),
                )
                task["artifacts"].append({
                    "cycle": cycle,
                    "document_version": document_revision,
                    "proposed_patch_ids": [patch["id"] for patch in proposed_patches],
                    "accepted_patch_ids": [patch["id"] for patch in accepted_patches],
                    "rejected_patch_ids": [patch["id"] for patch in rejected_patches],
                    "integrity_assessment": integrity_payload.get("assessment", {}),
                })
                _append_execution_log(
                    execution_log,
                    "task_application",
                    status="completed",
                    cycle=cycle,
                    task_id=task["id"],
                    line_start=task["line_start"],
                    line_end=task["line_end"],
                    proposed_patches=proposed_patches,
                    accepted_patches=accepted_patches,
                    rejected_patches=rejected_patches,
                    integrity_assessment=integrity_payload.get("assessment", {}),
                )
                validation_content = json.dumps({
                    "task_id": task["id"],
                    "verdicts": verdicts,
                    "integrity_assessment": integrity_payload.get("assessment", {}),
                    "integrity_verdicts": integrity_verdicts,
                    "accepted": accepted_patches,
                    "rejected": rejected_patches,
                }, ensure_ascii=False, indent=2)
                validation_entry = {
                    "cycle": cycle,
                    "role": "patch_validator",
                    "label": f"Walidator patchy | {task['id']} L{task['line_start']}-L{task['line_end']}",
                    "content": validation_content,
                }
                integrity_entry = {
                    "cycle": cycle,
                    "role": "integrity_verifier",
                    "label": f"Weryfikator integralności | {task['id']} L{task['line_start']}-L{task['line_end']}",
                    "content": json.dumps(integrity_payload, ensure_ascii=False, indent=2),
                }
                transcript.extend((validation_entry, integrity_entry))
                historical_outputs.extend((validation_entry, integrity_entry))
                _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="running"))
                yield {"type": "editorial_role_output", **validation_entry}
                yield {"type": "editorial_role_output", **integrity_entry}
                yield notifier.notify(
                    role="Orkiestrator",
                    phase="task_execution",
                    status="completed",
                    message=f"Orkiestrator: zakończyłem {task['id']}.",
                    line_start=int(task["line_start"]),
                    line_end=int(task["line_end"]),
                    purpose="Zapisano partial efekt i mechanicznie złożono aktualną wersję dokumentu.",
                )
                yield {
                    "type": "editorial_task",
                    "id": edit_id,
                    "task": {**task, "artifacts": list(task["artifacts"])},
                }
                yield _adaptive_plan_event(edit_id=edit_id, adaptive_plan=adaptive_plan)

            synthesis_content = json.dumps(
                {
                    "accepted_patch_ids": [patch["id"] for patch in cycle_accepted_patches],
                    "rejected_patch_ids": [patch["id"] for patch in cycle_rejected_patches],
                    "method": "deterministyczne zastosowanie zatwierdzonych podmian z partial efektów zadań",
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
    adaptive_plan["status"] = "completed"
    yield _adaptive_plan_event(edit_id=edit_id, adaptive_plan=adaptive_plan)
    yield notifier.notify(
        role="Podsumowujący",
        phase="editorial_summary",
        status="started",
        message="Przygotowuję końcowe podsumowanie dla autora.",
        purpose="Zebrać decyzje redakcyjne bez ponownego analizowania całego dokumentu.",
    )
    try:
        editorial_summary = call_role(
            phase="editorial_summary",
            role="editorial_summarizer",
            system_prompt=EDITORIAL_SUMMARIZER_INSTRUCTION,
            messages=[{
                "role": "user",
                "content": _build_editorial_summary_message(
                    title=title,
                    brief=brief,
                    cycles_completed=cycles_completed,
                    plan=plan,
                ),
            }],
            max_tokens_override=min(max_tokens, 768),
        ).strip()
        if not editorial_summary:
            raise ValueError("Model nie zwrócił podsumowania redakcyjnego.")
        summary_entry = {
            "cycle": cycles_completed,
            "role": "editorial_summarizer",
            "label": "Podsumowanie procesu dla autora",
            "content": editorial_summary,
        }
        transcript.append(summary_entry)
        historical_outputs.append(summary_entry)
        yield {"type": "editorial_role_output", **summary_entry}
        yield notifier.notify(
            role="Podsumowujący",
            phase="editorial_summary",
            status="completed",
            message="Końcowe podsumowanie dla autora jest gotowe.",
            purpose="Przekazać zwięzły opis faktycznie wykonanej redakcji.",
        )
    except Exception as exc:
        editorial_summary = _build_editorial_summary_fallback(
            title=title,
            cycles_completed=cycles_completed,
            execution_log=execution_log,
        )
        yield notifier.notify(
            role="Podsumowujący",
            phase="editorial_summary",
            status="failed",
            message="Nie udało się przygotować podsumowania przez model; zapisano skrót techniczny.",
            purpose=str(exc),
        )
    _write_debate_snapshot(build_record(cycles_completed=cycles_completed, status="completed"))

    yield {
        "type": "editorial_end",
        "id": edit_id,
        "title": title,
        "final_text": current_text,
        "summary": editorial_summary,
        "cycles_completed": cycles_completed,
    }