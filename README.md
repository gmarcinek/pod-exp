# POD-EXP

## TTS — synteza mowy (Piper)

Federacja może odczytywać wypowiedzi agentów na głos przy użyciu [Piper TTS](https://github.com/rhasspy/piper). TTS jest opcjonalny — włącza się checkboxem w formularzu sesji.

### 1. Pobierz Piper (Windows x64)

```powershell
$url = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
Invoke-WebRequest -Uri $url -OutFile piper_windows_amd64.zip -UseBasicParsing
Expand-Archive piper_windows_amd64.zip -DestinationPath piper_bin
Remove-Item piper_windows_amd64.zip
```

Dla Linuksa: pobierz `piper_linux_x86_64.tar.gz` z [releases](https://github.com/rhasspy/piper/releases) i rozpakuj do `piper_bin/`.

### 2. Pobierz polski model głosowy

Dostępne polskie głosy (wybierz jeden):

| Model                    | Płeć | Charakter       | Rekomendacja |
| ------------------------ | ---- | --------------- | ------------ |
| `pl_PL-darkman-medium`   | M    | głęboki, ciemny | ✅ domyślny  |
| `pl_PL-mc_speech-medium` | M    | neutralny       | alternatywa  |
| `pl_PL-gosia-medium`     | K    | wyraźna         | głos żeński  |

```powershell
New-Item -ItemType Directory -Force piper_models
# darkman (domyślny — głęboki bas)
$base = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pl/pl_PL/darkman/medium"
Invoke-WebRequest "$base/pl_PL-darkman-medium.onnx" -OutFile piper_models/pl_PL-darkman-medium.onnx -UseBasicParsing
Invoke-WebRequest "$base/pl_PL-darkman-medium.onnx.json" -OutFile piper_models/pl_PL-darkman-medium.onnx.json -UseBasicParsing
```

### 3. Konfiguracja `.env`

Dodaj do `.env` (ścieżki dostosuj do swojego systemu):

```env
# Windows
PIPER_EXECUTABLE=e:\PROJECTS\pod-exp\piper_bin\piper\piper.exe
PIPER_MODEL_DIR=e:\PROJECTS\pod-exp\piper_models
PIPER_DEFAULT_MODEL=pl_PL-darkman-medium

# Linux
# PIPER_EXECUTABLE=/path/to/piper_bin/piper/piper
# PIPER_MODEL_DIR=/path/to/piper_models
# PIPER_DEFAULT_MODEL=pl_PL-darkman-medium
```

### 4. Użycie

W interfejsie federacji zaznacz checkbox **TTS (Piper)** przed uruchomieniem sesji. Każda zakończona wypowiedź agenta i marszałka trafia do kolejki audio — odgrywane są sekwencyjnie przez przeglądarkę.

Endpoint do ręcznego testowania:

```bash
curl -s -X POST http://localhost:5000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Cześć, to jest test syntezatora mowy."}' \
  --output test.wav && start test.wav
```

---

# Pakiet konfiguracji agenta epistemicznego POD-a

Ten pakiet zawiera dojrzały przykład profilu pojedynczego agenta eksperymentu epistemicznego. Nie ma tu sekcji `task` ani żadnych parametrów infrastrukturalnych typu CPU, RAM czy limity tokenów. Celem pliku `config.json` jest opisanie **lokalnej tożsamości poznawczej agenta**: tego, kim jest, jak rozumie świat, co uznaje za dopuszczalne źródło wiedzy, czego nie potrafi łatwo zobaczyć i jak zachowuje się wobec niepewności.

## Zawartość paczki

- `config.json` — właściwy profil epistemiczny pojedynczego agenta.
- `README.md` — opis struktury, znaczenia pól i sposobu użycia.

## Jak rozumieć ten profil

Ten typ konfiguracji nie jest zwykłą konfiguracją wykonawczą. Nie ustawia zachowania silnika na poziomie technicznym, lecz buduje **wewnętrzny porządek poznawczy** agenta. Taki agent nie jest „neutralnym asystentem”, tylko lokalnym systemem interpretacji.

W praktyce oznacza to, że dwa POD-y mogą otrzymać to samo wejście, ale z powodu różnych konfiguracji epistemicznych wygenerować odpowiedzi:

- odmienne,
- częściowo zgodne,
- nieprzekładalne,
- albo podobne na poziomie wyniku, lecz oparte na zupełnie innej drodze dojścia.

## Struktura pliku `config.json`

### 1. `agent_identity`

Opisuje tożsamość agenta w sposób narracyjny.

Najważniejsze pola:

- `designation` — pełna nazwa profilu.
- `short_name` — skrócona nazwa techniczna.
- `narrative_identity` — opis tego, kim agent jest jako podmiot poznawczy.
- `role_in_experiment` — po co ten profil istnieje w eksperymencie.
- `temperament` — zestaw dominujących cech stylu myślenia.

To jest sekcja, która ma odpowiadać na pytanie: **„kim jest ten agent?”**, a nie tylko **„jakie ma opcje?”**.

### 2. `ontology`

Określa, co agent dopuszcza jako istniejące i jakie poziomy rzeczywistości uważa za sensowne.

Najważniejsze pola:

- `world_assumption` — główne założenie o naturze świata.
- `admitted_entities` — byty i klasy pojęć uznawane za dopuszczalne.
- `conditionally_admitted_entities` — elementy dopuszczane warunkowo lub hipotetycznie.
- `rejected_defaults` — założenia, których nie wolno traktować jako niewidzialnej normy.
- `entity_visibility_policy` — jak agent rozstrzyga, co staje się dla niego widzialne ontologicznie.

### 3. `epistemology`

Definiuje, skąd agent może czerpać wiedzę i jak porządkuje źródła poznania.

Najważniejsze pola:

- `knowledge_sources` — legalne źródła poznania.
- `source_prioritization` — ich wewnętrzna hierarchia.
- `disallowed_shortcuts` — poznawcze skróty niedopuszczalne dla tego agenta.
- `epistemic_posture` — ogólna postawa wobec wiedzy i jej niepełności.

### 4. `truth_criterion`

Mówi, co znaczy dla agenta „prawdziwe” lub „poznawczo mocne”.

Najważniejsze pola:

- `definition` — opis kryterium prawdy.
- `acceptance_layers` — warstwy potrzebne do akceptacji twierdzenia.
- `rejection_conditions` — kiedy twierdzenie powinno zostać odrzucone.

### 5. `cognitive_dynamics`

Opisuje dynamikę ruchu poznawczego.

#### `attractors`

Atraktory to kierunki, ku którym rozumowanie agenta grawituje. Nie są jeszcze wnioskiem, ale zwiększają prawdopodobieństwo określonych interpretacji.

#### `bifurcators`

Bifurkatory to punkty rozgałęzienia. Określają, co zmienia tor analizy: np. silne wyjaśnienie mechaniczne, konflikt między prostotą i adekwatnością, trwała niejednoznaczność danych.

#### `stability_rules`

To reguły utrzymujące spójność profilu w sytuacjach granicznych.

### 6. `base_beliefs`

Bazowe przekonania, od których agent startuje i których nie buduje od zera przy każdym użyciu.

Każdy wpis ma:

- `belief` — treść przekonania,
- `rank` — względny priorytet.

### 7. `exclusion_clauses`

Klauzule wyłączeń, czyli twarde ograniczenia epistemiczne. Określają, czego agent nie może zrobić bez utraty własnej tożsamości.

Przykłady funkcji tej sekcji:

- blokowanie totalnej redukcji,
- blokowanie pozornej neutralności,
- blokowanie zbyt mocnych roszczeń przy słabych danych,
- ograniczanie niekontrolowanego mnożenia bytów.

### 8. `blind_spots`

Jawne wskazanie ślepych plamek profilu.

To bardzo ważna sekcja, bo pozwala odróżnić:

- zwykły błąd,
- ograniczenie systemowe wynikające z lokalnej epistemologii.

Pola:

- `known_risks` — rozpoznane ryzyka interpretacyjne,
- `self_warning` — ostrzeżenie wewnętrzne,
- `visibility_limit_statement` — obszar, który agent widzi najsłabiej.

### 9. `expression_policy`

Opisuje formę ekspresji odpowiedzi, ale nie na poziomie technicznym, tylko poznawczo-retorycznym.

Pola:

- `style` — zalecana forma wypowiedzi,
- `tone` — ton,
- `must_include` — elementy, które powinny być jawnie obecne,
- `must_not_include` — elementy, których agent ma unikać.

### 10. `blindness_radius`

To rozwinięcie sekcji ślepych plamek w formie bardziej mierzalnej.

Znaczenie:

- `level` — opisowy poziom promienia ślepoty,
- `score` — liczbowy wskaźnik na zadanej skali,
- `primary_invisible_zones` — obszary poznawczo trudne do zobaczenia,
- `notes` — komentarz interpretacyjny.

**Promień ślepoty** nie oznacza głupoty agenta. Oznacza zakres tego, czego agent systemowo nie dostrzega lub nie umie łatwo uznać za wystarczające z powodu własnych założeń.

### 11. `uncertainty_resilience`

Opisuje, jak agent reaguje na brak danych, wieloznaczność i konflikt między interpretacjami.

Pola:

- `level` — poziom odporności,
- `score` — wskaźnik liczbowy,
- `behaviour_under_uncertainty` — typowe zachowania pod niepewnością,
- `failure_modes` — sposoby, w jakie odporność może stać się słabością.

### 12. `cognitive_tendencies`

Sekcja opisująca tendencje poznawcze.

Pola:

- `dominant_tendencies` — dominujące skłonności,
- `secondary_tendencies` — tendencje wtórne,
- `counter_tendencies` — odruchy hamujące lub równoważące.

Ta sekcja jest szczególnie ważna przy porównywaniu wielu agentów, bo pokazuje nie tylko ich deklaracje, ale także ich styl ruchu poznawczego.

### 13. `output_contract`

Sekcja opcjonalna. Nie zawiera zadania, ale proponuje standard odpowiedzi, który pozwala porównywać wiele agentów w tym samym eksperymencie.

## Jak używać tego profilu w eksperymencie

Najbardziej sensowny model użycia wygląda tak:

1. **Trzymasz osobno profil agenta** (`config.json`).
2. **Osobno dostarczasz wejście eksperymentalne** — pytanie, problem, dokument, dane lub sytuację.
3. Agent otrzymuje oba elementy:
   - własny profil epistemiczny,
   - zewnętrzne wejście do analizy.
4. Odpowiedź generowana jest nie z pozycji neutralnej, lecz z wnętrza tego profilu.

## Zalecany sposób pracy z wieloma POD-ami

Dla populacji wielu agentów dobrze jest:

- utrzymać wspólny format pliku,
- zmieniać tylko profil epistemiczny,
- podawać to samo wejście eksperymentalne,
- porównywać wyniki według takich osi jak:
  - podobieństwo odpowiedzi,
  - różnice ontologiczne,
  - promień ślepoty,
  - odporność na niepewność,
  - stabilność pod konfliktem danych,
  - widzialność i niewidzialność klas wyjaśnień.

## Po co ten typ konfiguracji

Ten pakiet służy do przejścia od prostego testu „kto odpowie lepiej” do badania:

- jak różne aksjomaty generują różne światy poznawcze,
- jakie wyjaśnienia stają się widzialne lub niewidzialne,
- które epistemologie są szerokie, a które wąskie, ale bardzo spójne,
- jak powstają racje zakorzenione w różnych punktach startowych.

## Uwagi końcowe

Ten przykład jest celowo dojrzały i opisowy. Ma służyć jako baza do:

- dalszego ręcznego rozwijania profili,
- generowania populacji agentów,
- walidacji schematów JSON,
- budowania porównawczych eksperymentów epistemicznych.

Jeśli chcesz, można go dalej rozbudować o dodatkowe sekcje, np.:

- `taboos`,
- `sacred_distinctions`,
- `collapse_conditions`,
- `translation_limits`,
- `attractor_weights`,
- `epistemic_costs`,
- `cross_agent_compatibility`.
