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
- [x] TASK-12: Rozszerzyć składanie system promptu o pełny profil JSON — przebudować `build_system_prompt(profile)` w `client.py` tak, aby zawsze uwzględniał wszystkie istotne pola obecnego schematu profilu agenta, w tym brakujące sekcje opisane w README i realnych plikach `agents/*.json`, oraz poprawić odczyt `exclusion_clauses` z poziomu top-level zamiast z `cognitive_dynamics`.
- [ ] TASK-13: Dodać lekki check kompletności promptu — wprowadzić mały, lokalny check dla `build_system_prompt(profile)` na przykładowym profilu/agencie, który potwierdzi obecność reprezentacji kluczowych sekcji schematu w promptcie oraz zabezpieczy przed pominięciem top-level `exclusion_clauses`.
- [ ] TASK-14: Zweryfikować slice backendowy kompilacją i checkiem promptu — uruchomić `python -m py_compile client.py app.py` oraz lekki check budowy promptu dla przykładowego agenta, aby potwierdzić poprawność składania promptu po zmianach.

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