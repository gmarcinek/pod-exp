---
name: react-nextjs-frontend
description: "Use when: planujesz frontend w React lub Next.js, potrzebujesz podjąć decyzję między React + Vite a Next.js, projektujesz strukturę modułów UI, albo migrujesz istniejący HTML/CSS/vanilla JS do komponentów React."
---

# React i Next.js dla frontendu

Ten skill służy do planowania i realizacji prac frontendowych w projektach, w których trzeba rozstrzygnąć rolę Reacta i Next.js oraz zaplanować migrację istniejącego UI do architektury komponentowej.

## Kiedy używać React

Użyj samego Reacta, gdy:

- frontend ma być osobną aplikacją kliencką,
- backend i routing serwerowy są już obsługiwane przez inny framework,
- potrzebujesz przejąć istniejący interfejs HTML/CSS/JS etapami,
- priorytetem jest lekki bootstrap, jasny podział na komponenty i moduły oraz pełna kontrola nad bundlerem.

W praktyce taki wariant dobrze pasuje do aplikacji, w których serwer już wystawia API i widoki, a nowy frontend ma zostać dołączony bez przebudowy backendu.

## Kiedy używać Next.js

Użyj Next.js, gdy:

- projekt ma być oparty o React i jednocześnie potrzebuje własnego routingu aplikacyjnego,
- renderowanie po stronie serwera, server actions, route handlers i warstwa BFF mają być częścią tego samego projektu,
- chcesz budować frontend i backend webowy w jednym spójnym runtime,
- repo już posiada aplikację Next.js albo plan architektoniczny zakłada świadome przejście na Next.js.

Nie wybieraj Next.js wyłącznie dlatego, że projekt używa Reacta. To decyzja architektoniczna, a nie kosmetyczna.

## Nota decyzyjna dla tego repo

W tym repo **nowy frontend powstaje jako React + Vite w `/frontend`**, a nie jako Next.js.

Powód decyzji:

- backend działa we Flasku w `app.py`,
- routing serwerowy i endpointy pozostają po stronie Flask,
- obecny interfejs istnieje jako `templates/*.html` oraz `static/*.js` i `static/*.css`,
- repo nie zawiera obecnie projektu Next.js, więc jego wprowadzenie zwiększałoby zakres migracji ponad potrzeby zadania.

Przy kolejnych pracach frontendowych traktuj React + Vite jako domyślny kierunek implementacji, dopóki użytkownik nie zleci jawnej zmiany architektury.

## Planowanie struktury modułów

Dla tego repo zakładaj docelowo strukturę:

- `/frontend` jako osobny projekt aplikacji,
- `/frontend/src/bootstrap` dla punktu wejścia, konfiguracji routera, providerów i integracji z backendem Flask,
- `/frontend/src/assets` dla assetów importowanych przez kod aplikacji,
- `/frontend/src/components` dla współdzielonych, wielokrotnego użytku komponentów UI,
- `/frontend/src/modules` dla modułów ekranów i logiki domenowej,
- `/frontend/assets` dla assetów statycznych bundlowanych lub kopiowanych bezpośrednio.

Zasady podziału:

- `components` zawiera elementy współdzielone między ekranami,
- `modules` odwzorowuje konkretne obszary produktu i widoki,
- moduł może zawierać własne komponenty lokalne, hooki, style i adaptery danych,
- logika integracji z Flask API powinna być skupiona blisko bootstrapu lub w wydzielonych klientach modułowych, nie rozproszona po widokach.

## Migracja z HTML/CSS/vanilla JS do React

Przy migracji istniejącego UI stosuj następującą kolejność:

1. Zidentyfikuj obecne ekrany i ich granice na podstawie `templates/` oraz odpowiadających im plików w `static/`.
2. Rozdziel kod na: strukturę widoku, stan UI, efekty uboczne, komunikację z API i renderery danych.
3. Zamień sekcje interfejsu na komponenty React zaczynając od największych, stabilnych bloków widoku.
4. Przenieś współdzielone fragmenty do `src/components`, a logikę konkretnego ekranu do `src/modules/<nazwa-modulu>`.
5. Zachowaj istniejące zachowanie 1:1 przed wprowadzaniem ulepszeń architektonicznych.

Podczas migracji unikaj:

- przepisywania całego UI bez mapy odpowiedzialności,
- mieszania komponentów współdzielonych z logiką konkretnego ekranu,
- zmiany backendowych endpointów tylko po to, by dopasować je do frontendu,
- jednoczesnej zmiany technologii frontendu i backendu.

## Praktyczna heurystyka dla tego projektu

Jeżeli zadanie dotyczy nowego interfejsu w tym repo, domyślna ścieżka decyzyjna jest taka:

1. Zachowaj Flask jako backend i źródło routingu serwerowego.
2. Buduj nowy frontend w React + Vite w `/frontend`.
3. Rozbij UI na `bootstrap`, `components` i `modules`.
4. Migruj istniejące template i pliki static ekran po ekranie.
5. Traktuj Next.js jako opcję tylko przy osobnej, świadomie zaakceptowanej zmianie architektury.