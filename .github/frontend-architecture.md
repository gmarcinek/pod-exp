# TASK-02 — Docelowa architektura frontendu

Status: approved

Decyzja implementacyjna: nowy frontend powstaje w React + Vite. Nie używamy Next.js, ponieważ repozytorium ma już działający backend Flask, istniejące trasy użytkowe i endpointy API, a wymaganiem jest migracja 1:1 obecnego UI przy zachowaniu Flask jako warstwy serwerowej.

## Cel

Zaprojektować katalog `/frontend` jako osobną aplikację SPA/MPA-hybrid renderowaną po stronie klienta, ale integrowaną z Flask jako backend-for-frontend dla routingu użytkowego, danych startowych i API. Architektura ma zachować 1:1 funkcjonalność i wygląd obecnych ekranów z `templates/*.html` oraz `static/*.js` / `static/*.css`, przy jednoczesnym rozbiciu kodu na moduły i podmoduły.

## Docelowa struktura `/frontend`

```text
/frontend
  /assets
    /fonts
    /icons
    /images
  /src
    /bootstrap
      main.tsx
      app-router.tsx
      app-shell.tsx
      backend-config.ts
      bootstrap-data.ts
    /assets
      /styles
      /images
      /icons
    /components
      /layout
      /navigation
      /forms
      /feedback
      /markdown
      /transcript
      /analysis
    /modules
      /home
        /chat
        /debate
        /shared
      /debates-archive
      /debate-view
      /analysis-common
    /lib
      api
      sse
      storage
      mappers
      types
    /routes
      home-route.tsx
      debates-route.tsx
      debate-view-route.tsx
  package.json
  vite.config.ts
  tsconfig.json
  index.html
```

## Rola katalogów

### `/frontend/assets`

Assety statyczne nieimportowane bezpośrednio przez komponenty, utrzymywane jako surowe zasoby builda i kopie 1:1 z obecnego UI, jeśli będą potrzebne do zachowania wyglądu. To miejsce dla fontów, ikon i obrazów, które Vite ma kopiować bezpośrednio do buildu.

### `/frontend/src`

Kod źródłowy Reacta i TypeScript. Cała logika UI, routingu, mapowania danych backendowych i renderowania ekranów trafia tutaj.

### `/frontend/package.json`

Kontrakt aplikacji frontendowej: zależności React + Vite, skrypty `dev`, `build`, `preview` oraz docelowo skrypt pomocniczy do integracji buildu z Flask. Ten plik potwierdza, że frontend jest osobnym pakietem narzędziowym, ale nadal podporządkowanym backendowi repo.

### `/frontend/src/bootstrap`

Warstwa uruchomieniowa aplikacji. Odpowiada za:

- start Reacta,
- inicjalizację routingu po stronie klienta,
- odczyt konfiguracji backendu Flask,
- odczyt danych startowych wstrzykniętych przez Flask,
- wybór właściwego modułu ekranu dla tras `/`, `/debates`, `/debates/:id`.

### `/frontend/src/assets`

Assety importowane przez kod źródłowy: style globalne, warianty layoutu, wspólne tokeny wizualne oraz zasoby używane bezpośrednio przez komponenty. To rozdział od `/frontend/assets`, który chroni porządek między zasobami bundlowanymi przez import i zasobami kopiowanymi 1:1.

### `/frontend/src/components`

Warstwa współdzielonych komponentów wielokrotnego użytku. Brak logiki ekranowej specyficznej dla tras; tylko elementy składane przez moduły.

### `/frontend/src/modules`

Warstwa funkcjonalna odpowiadająca 1:1 istniejącym widokom i współdzielonej logice obecnego UI. Każdy moduł posiada własne podmoduły, selektory danych, komponenty kontenerowe i adaptery do backendu.

## Moduły i podmoduły

### 1. Ekran główny chat/debate (`/`)

Źródło migracji: `templates/index.html`, `static/index.js`, `static/index.css`, część wspólna z `static/pod.css` i `static/analysis.js`.

Proponowany moduł: `/frontend/src/modules/home`

Podmoduły:

- `/chat`
  - `chat-page` — kontener trybu czatu.
  - `chat-config-panel` — wybór agenta, providera, modelu i thinking effort.
  - `chat-transcript` — render wiadomości użytkownika, agenta, błędów i tooli.
  - `chat-composer` — textarea, autosize, submit, skróty klawiaturowe.
  - `chat-session-store` — utrzymanie rozmowy w stanie klienta.
- `/debate`
  - `debate-page` — kontener trybu debaty.
  - `debate-config-panel` — konfiguracja agentów, providerów, modeli, thinking effort, tokenów, tematu, trybu debaty i liczby tur.
  - `debate-progress` — pasek progresu i etykieta tur.
  - `debate-transcript` — streaming i render bąbli debaty.
  - `debate-live-notes` — szybkie notatki i fiszki faktów.
  - `debate-stream-client` — klient SSE nad `fetch` POST do `/api/debate`.
  - `debate-continuation` — logika kontynuacji debaty i przycisku `Kontynuuj`.
- `/shared`
  - `mode-switch` — przełącznik Chat/Debata.
  - `home-sidebar-shell` — sidebar i sekcje konfiguracji.
  - `home-main-layout` — transcript pane, notes pane, input area.
  - `settings-persistence` — persystencja `localStorage` dla ustawień chat i debate.
  - `models-registry` — odwzorowanie list modeli i reguł `thinking`.

Zakres odpowiedzialności: pełne odwzorowanie obecnego zachowania strony głównej, w tym przełączanie trybów, zapamiętywanie ustawień, render markdown, live notes, analiza końcowa i obsługa kontynuacji debaty.

### 2. Archiwum debat (`/debates`)

Źródło migracji: `templates/debates.html`.

Proponowany moduł: `/frontend/src/modules/debates-archive`

Podmoduły:

- `archive-page` — kontener widoku.
- `archive-header` — nagłówek, branding i link powrotu.
- `debate-list` — lista kart debat.
- `debate-card` — pojedyncza karta z agentami, tematem, metadanymi i linkiem.
- `archive-empty-state` — pusty stan bez zapisanych debat.
- `archive-data-mapper` — mapowanie backendowego payloadu listy debat na model widoku.

Zakres odpowiedzialności: 1:1 układ archiwum, karty debat, stan pusty i linkowanie do widoku pojedynczej debaty.

### 3. Widok debaty (`/debates/:id`)

Źródło migracji: `templates/debate_view.html`, `static/view.js`, `static/view.css`, wspólny renderer `static/analysis.js`.

Proponowany moduł: `/frontend/src/modules/debate-view`

Podmoduły:

- `debate-view-page` — kontener widoku pojedynczej debaty.
- `debate-header` — agent pills, temat, nawigacja powrotna.
- `debate-meta-bar` — data, liczba wymian, modele, thinking effort.
- `debate-message-list` — sekwencyjny render transcriptu.
- `debate-message-card` — pojedyncza wypowiedź agenta.
- `thinking-panel` — sekcja `details/summary` dla myśli agenta.
- `analysis-section` — sekcja analizatora.
- `summary-section` — sekcja summariser.
- `debate-view-mapper` — mapowanie pełnego obiektu debaty do modelu widoku.

Zakres odpowiedzialności: identyczne renderowanie transcriptu, bloku analizatora i summarisera, wraz z markdownem i sekcjami warunkowymi.

### 4. Analiza / renderery wspólne

Źródło migracji: `static/analysis.js` oraz wspólne style i markdown renderer używane przez stronę główną i widok debaty.

Proponowany moduł: `/frontend/src/modules/analysis-common`

Podmoduły:

- `analysis-card-renderer` — główny renderer kart analizy JSON.
- `analysis-sections` — sekcje typu interaction pattern, collision points, trajectory, relation status.
- `analysis-badges` — pill, badge, xref i etykiety porównawcze.
- `markdown-renderer` — wspólna warstwa renderowania markdown dla wiadomości, analizy tekstowej i summary.
- `transcript-primitives` — wspólne komponenty bąbli, nagłówków wiadomości i układów slotów agentów.

Zakres odpowiedzialności: jeden wspólny zestaw rendererów i prymitywów dla analizy i transcriptu, bez duplikacji między stroną główną a widokiem debaty.

## Integracja z Flask

### Routing użytkowy

Flask pozostaje właścicielem tras użytkowych:

- `/`
- `/debates`
- `/debates/<debate_id>`

Docelowo każda z tych tras zwraca wspólny shell frontendu React, ale nadal jest rozstrzygana przez Flask. React przejmuje rendering właściwego modułu ekranu po stronie klienta, a Flask pozostaje źródłem routingu, danych startowych i błędów HTTP, np. `404` dla brakującej debaty.

To podejście minimalizuje ryzyko migracji, bo nie zmienia publicznych adresów i nie wymaga osobnego serwera aplikacyjnego Next.js.

### `/api/chat`

Frontend wykorzystuje istniejący endpoint `POST /api/chat` bez zmiany kontraktu. Warstwa `/frontend/src/lib/api` definiuje klienta wywołującego ten endpoint i normalizującego odpowiedź:

- request: `agent`, `provider`, `model`, `thinking_effort`, `messages`
- response sukcesu: `role`, `content`
- response błędu: `error`

Użycie: moduł `home/chat`.

### SSE z `/api/debate`

Frontend wykorzystuje istniejący `POST /api/debate`, który zwraca `text/event-stream`. To nie jest klasyczny `EventSource`, tylko klient SSE oparty na `fetch` + `ReadableStream`, bo request wymaga metody POST i payloadu JSON.

Warstwa `/frontend/src/lib/sse` oraz podmoduł `home/debate/debate-stream-client` odpowiadają za:

- wysłanie konfiguracji debaty,
- odczyt strumienia linii `data: ...`,
- parsowanie eventów JSON,
- mapowanie eventów na stan UI,
- obsługę abort/stop,
- obsługę continuation payloadu.

Użycie: moduł `home/debate`.

### Dane dla listy debat i pojedynczej debaty

Nie dodajemy nowych endpointów tylko po to, by zasilić React. Dla zachowania minimalnego zakresu backend Flask nadal przygotowuje dane route-level:

- `/debates` przekazuje listę debat jako payload startowy dla modułu `debates-archive`.
- `/debates/<debate_id>` przekazuje pełny obiekt debaty jako payload startowy dla modułu `debate-view`.
- `/` przekazuje dane startowe dla strony głównej, przede wszystkim listę agentów i mapę modeli.

Docelowy mechanizm bootstrapu:

- Flask renderuje lekki shell HTML.
- Shell wstrzykuje `window.__POD_EXP_BOOTSTRAP__` z polami `route`, `apiBaseUrl`, `agents`, `models`, `debates`, `debate` zależnie od trasy.
- React w `/frontend/src/bootstrap/bootstrap-data.ts` odczytuje payload i uruchamia odpowiedni moduł bez dodatkowego requestu inicjalnego.

To zachowuje obecny model danych i eliminuje zbędne podwójne pobieranie przy wejściu na `/debates` i `/debates/:id`.

### Strategia serwowania buildu frontendu przez Flask

Docelowa strategia produkcyjna:

1. Vite buduje frontend do `/frontend/dist` z hashowanymi assetami.
2. Flask serwuje pliki JS/CSS/obrazy z buildu jako statyczne assety.
3. Flask renderuje wspólny shell HTML dla tras użytkowych, wskazując właściwe pliki builda z manifestu Vite.
4. Endpointy API (`/api/agents`, `/api/chat`, `/api/debate`) pozostają bez zmian i nie są obsługiwane przez frontend router.

Decyzja wdrożeniowa:

- w development: frontend działa przez serwer Vite, ale korzysta z Flask jako backendu API,
- w production: Flask serwuje gotowy build Reacta,
- do czasu TASK-10 stare `templates/` i `static/` pozostają aktywne jako punkt odniesienia migracji.

## Granice odpowiedzialności

- Flask: routing użytkowy, dane startowe, API, streaming debaty, obsługa plików debat, błędy HTTP.
- React + Vite: rendering UI, lokalny stan ekranu, routing klienta wewnątrz shella, persystencja ustawień, konsumowanie API.
- Moduły frontendu: 1:1 odwzorowanie zachowań i wyglądu, bez zmiany backendowych kontraktów.

## Kryteria akceptacji dla TASK-02

- Architektura jawnie zakłada React + Vite, nie Next.js.
- Struktura `/frontend` zawiera co najmniej `assets`, `src`, `package.json`, `src/bootstrap`, `src/assets`, `src/components`, `src/modules`.
- Moduły odpowiadają istniejącym widokom: ekran główny chat/debate, archiwum debat, widok debaty, analiza/renderery wspólne.
- Integracja z Flask obejmuje routing użytkowy, `POST /api/chat`, SSE over `fetch` dla `POST /api/debate`, dane startowe dla listy debat i pojedynczej debaty oraz strategię serwowania buildu.
- Zakres zadania pozostaje dokumentacyjny i nie narusza obecnego działania aplikacji.