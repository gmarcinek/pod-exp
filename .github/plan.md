# Plan realizacji

## Status: IN PROGRESS

## Zadania
- [x] TASK-01: Stworzyć skill Next.js i React — dodać artefakt w `.github/skills/` opisujący zasady pracy z Next.js i Reactem, z jawną notą decyzyjną, że w tym repo implementacja frontendu powstaje w React + Vite ze względu na istniejący Flask backend i brak obecnego projektu Next.js.
- [x] TASK-02: Ustalić architekturę nowego frontendu — opisać i zatwierdzić docelową strukturę `/frontend` z co najmniej `assets/`, `src/`, `package.json`, konfiguracją bundlera oraz podziałem `src/bootstrap`, `src/assets`, `src/components`, `src/modules`, tak aby moduły odpowiadały ekranom i współdzielonej logice obecnego UI. Artefakt: `.github/frontend-architecture.md`.
- [x] TASK-03: Zascaffoldować aplikację React w `/frontend` — utworzyć nowy projekt Vite + React z podstawową konfiguracją uruchamiania i builda, bez naruszania obecnego Flask + static/templates, oraz przygotować katalogi i minimalne pliki startowe zgodne z ustaloną strukturą modułów i podmodułów, w tym bazowy entrypoint Reacta, prosty `AppShell`, placeholder router i kontrakt bootstrap payload bez pełnej integracji ekranów i danych.
- [x] TASK-04: Rozwinąć właściwy bootstrap, routing i integrację danych frontendu — rozbudować minimalny scaffold z TASK-03 do docelowej warstwy startowej aplikacji, obejmującej rozstrzyganie widoków odpowiadających `/`, `/debates` i `/debates/:id`, wspólny layout aplikacji, wstrzykiwanie konfiguracji backendu Flask oraz zasilanie tras rzeczywistymi danymi początkowymi, a nie samo utworzenie pustych plików.
- [x] TASK-05: Przenieść współdzielone style i assety 1:1 — zmigrować `static/pod.css`, wspólne zmienne wizualne, typografię, układy i assety do `frontend/assets` i `frontend/src/assets`, tak aby zachować dotychczasowy wygląd bez regresji wizualnych.
- [x] TASK-06: Zmigrować ekran główny chat/debate do modułów React — rozbić obecny `templates/index.html` i `static/index.js` na moduły oraz podmoduły React dla konfiguracji czatu, konfiguracji debaty, transcriptu, notatek live, progresu, formularza wejściowego i persystencji ustawień w `localStorage`, zachowując 1:1 obecne zachowania.
- [x] TASK-07: Zmigrować ekran archiwum debat do Reacta — odwzorować `templates/debates.html` jako moduł listy debat z tym samym układem, danymi i stanami pustymi, korzystający z backendowych danych Flask bez zmiany funkcjonalności.
- [x] TASK-08: Zmigrować ekran widoku debaty i analizę do Reacta — przenieść `templates/debate_view.html`, `static/view.js`, `static/view.css` i `static/analysis.js` do modułów React dla transcriptu, sekcji analizatora, summarisera i rendererów kart analizy, zachowując 1:1 prezentację oraz logikę renderowania markdown i danych JSON.
- [x] TASK-09: Spiąć nowy frontend z API i serwowaniem Flask — dodać integrację builda Reacta z backendem, w tym pobieranie `/api/chat`, SSE dla `/api/debate`, zasilanie widoków danymi z Flask oraz serwowanie zbudowanych assetów i fallbacków tras bez psucia istniejących endpointów API.
- [x] TASK-10: Przełączyć renderowanie ekranów Flask na nowy frontend — zastąpić dotychczasowe template-based entrypointy nowym frontendem w sposób kontrolowany, tak aby trasy użytkowe korzystały z Reacta, a backend nadal pozostał źródłem danych i logiki serwerowej.
- [ ] TASK-11: Zweryfikować zgodność 1:1 funkcjonalną i wizualną — wykonać porównanie starego i nowego UI dla czatu, debaty, archiwum i widoku debaty, sprawdzić persystencję ustawień, streaming, analizę, markdown, nawigację i wygląd oraz usunąć wykryte regresje.

## Mini-plan: Pełny prompt z profilu JSON
- [x] TASK-12: Domknąć budowę system promptu do pełnego JSON profilu as is — usunąć z `build_system_prompt(profile)` w `client.py` wszelki tekstowy wrapper i zwracać wyłącznie pełny serializowany JSON profilu, bez ręcznego składania sekcji i bez unifikacji DTO na tym etapie, tak aby ten sam mechanizm działał zarówno dla agentów z `agents/*.json`, jak i tooli z `tools/*.json`.
- [x] TASK-13: Dodać lekki, repozytoryjny check na profilu `meta-nihilizm-epistemiczny` i ścieżce toola — wprowadzić mały wykonywalny artefakt w repo, np. skrypt lub dedykowaną komendę check, który realnie uruchamia `build_system_prompt(profile)` i potwierdza, że prompt zawiera pełny JSON przykładowego profilu `meta-nihilizm-epistemiczny` bez ręcznego mapowania sekcji oraz że ten sam mechanizm działa także dla profilu ładowanego z `tools/*.json`.
- [x] TASK-14: Zweryfikować slice backendowy kompilacją i wykonywalnym checkiem promptu — uruchomić `python -m py_compile client.py app.py` oraz nowy repozytoryjny skrypt/command z TASK-13 dla przykładowego agenta i toola, aby potwierdzić poprawność prostego promptu JSON po zmianach wykonywalnym checkiem, a nie tylko helperem w kodzie.

## Mini-plan: Persystencja debat i nowe trasy debaty
- [x] TASK-15: Zmienić identyfikację i persystencję debaty po stronie backendu — przebudować generowanie ID nowej debaty w `app.py` na format `timestamp_{short_uuid}` oraz zapisywać ten sam plik JSON po każdym zakończonym streamie odpowiedzi, tak aby snapshot debaty i jej ustawień był utrwalany inkrementalnie zamiast dopiero na końcu `_run_debate()`.
- [x] TASK-16: Dodać backendowe ładowanie i bootstrap dla `/debate/<id>` oraz `/newDebate` w dev i prod — rozszerzyć Flask routes i bootstrap payload builders tak, aby singular route `/debate/<id>` ładowała debatę z JSON wraz z ustawieniami, `/newDebate` zwracało osobny placeholder bootstrap, a odpowiadające endpointy działały symetrycznie dla renderu produkcyjnego i dev preview/bootstrap.
- [x] TASK-17: Domknąć frontendowy ekran sesji debaty dla `/debate/<id>` na bazie JSON bootstrapu — doprowadzić mapowanie ustawień zapisanej debaty do stanu `debate-view` do zgodności z JSON bootstrapem, w tym brać `debate_mode` i `debate_mode_custom` z `config`, znormalizować ustawienia z walidacją `debate_mode` względem dozwolonych wartości oraz po stronie backendu przy backfillu `config` dla legacy debat normalizować `debate_mode` do kanonicznej wartości enum zamiast display label, tak aby odtworzenie sesji debaty było poprawne; `/newDebate` pozostaje na tym etapie pustą stroną.
- [ ] TASK-18: Zamienić pusty `/newDebate` na prosty ekran startu debaty i zweryfikować pełny flow w dev/prod — na `/newDebate` wykorzystać ogólny layout debaty, ale bez wertykalnego centrowania, z przewijalnym widokiem pokazującym całość, formularzem ułożonym w jednej kolumnie z polami tekstowymi jedno pod drugim o szerokości około 800px oraz przyciskiem `Rozpocznij debatę` obok formularza; kliknięcie ma uruchamiać debatę i kierować na stronę rozpoczynającej się sesji z ustawieniami z formularza `/newDebate` i danymi z tych pól, a na stronie live debaty sidebar ma być zredukowany do skróconego, read-only setupu oraz przycisków `STOP`, `Continue` i informacji o liczbie kroków; w ramach domknięcia zadania trzeba też zapewnić pełne wsparcie dev/preview dla nowego route live debaty oraz stabilne odczytanie draftu live debaty bez ryzyka wyczyszczenia go przez `React.StrictMode` przy mount; następnie sprawdzić lokalnie, że `/debate/<id>` nadal poprawnie odtwarza debatę z JSON-a, a nowy flow `/newDebate` działa w obu trybach.

## Zależności
- TASK-02 wymaga TASK-01
- TASK-03 wymaga TASK-02
- TASK-04 wymaga TASK-03
- TASK-05 wymaga TASK-03
- TASK-06 wymaga TASK-04
- TASK-06 wymaga TASK-05
- TASK-07 wymaga TASK-04
- TASK-07 wymaga TASK-05
- TASK-08 wymaga TASK-04
- TASK-08 wymaga TASK-05
- TASK-09 wymaga TASK-06
- TASK-09 wymaga TASK-07
- TASK-09 wymaga TASK-08
- TASK-10 wymaga TASK-09
- TASK-11 wymaga TASK-10
- TASK-13 wymaga TASK-12
- TASK-14 wymaga TASK-13
- TASK-16 wymaga TASK-15
- TASK-17 wymaga TASK-16
- TASK-18 wymaga TASK-17