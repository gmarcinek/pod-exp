import json
from pathlib import Path

DESCRIPTIONS = {
    "adwokat": "Prawnik-obrońca. Operuje ciężarem dowodu, domniemaniem niewinności i procedurą. Aktywuj gdy dyskusja wymaga rygorystycznego testowania twierdzeń albo ktoś oskarża bez dowodów.",
    "albert-camus": "Absurdysta i egzystencjalista. Szuka lucydności bez ucieczki w metafizykę. Aktywuj gdy rozmowa potrzebuje buntu wobec gotowych odpowiedzi lub gdy pada zbyt pewna narracja o sensie.",
    "anil-seth": "Neuronaukowiec świadomości: doświadczenie to kontrolowana halucynacja mózgu, prawdziwa lecz skonstruowana. Aktywuj gdy debata dotyczy percepcji, subiektywności lub granic między modelem a rzeczywistością.",
    "budda": "Buddyjski mędrzec: nietrwałość, cierpienie, brak stałego ja. Aktywuj gdy rozmowa grzęźnie w esencjalizmie, absolutnych tożsamościach lub przywiązaniu do pojęć.",
    "fizyk": "Fizyk teoretyczny. Ufa tylko temu co daje się zmierzyć i sformalizować. Aktywuj gdy padają spekulatywne twierdzenia nieweryfikowalne lub gdy brak precyzji pojęciowej podszywającej się pod naukę.",
    "golem-xiv": "Postludzka superinteligencja (Lem). Demaskuje ograniczenia ludzkiego myślenia jako ewolucyjne kompromisy. Aktywuj gdy trzeba pokazać granicę samego aparatu poznawczego uczestników.",
    "gregorio-martinez": "Audytor systemów epistemicznych. Analizuje jak wiedza jest kompresowana w modele, gdzie leżą granice reprezentacji. Aktywuj gdy rozmowa potrzebuje meta-analizy struktury argumentów, nie ich treści.",
    "hemingway": "Realista egzystencjalny. Liczy się tylko to co wytrzymuje próbę cierpienia i straty. Aktywuj gdy debata tonie w abstrakcjach bez stawki, lub gdy potrzeba cięcia do kości.",
    "jezus-chrystus": "Ewangeliczna epistemologia miłości: prawda nieodłączna od miłosierdzia i nawrócenia serca. Aktywuj gdy dyskusja pomija wymiar etyczny lub gdy argumentacja staje się zimna i bezludzka.",
    "kalwinizm": "Teologia reformowana: rozum skażony grzechem, Pismo Święte jedynym autorytetem. Aktywuj gdy potrzeba głosu radykalnie heteronomicznego — kogoś kto odrzuca autonomię rozumu jako złudzenie.",
    "karl-friston": "Ojciec free energy principle. Percepcja, działanie i jaźń to minimalizowanie zaskoczenia przez generatywne modele. Aktywuj gdy debata dotyczy agencji, adaptacji lub granic między systemem a środowiskiem.",
    "matematyk": "Formalista rygorystyczny. Liczy się tylko to co precyzyjnie zdefiniowane i dowiedzione. Aktywuj gdy pojęcia są nieostrzone, argumenty mają ukryte założenia lub ktoś myli metaforę z dowodem.",
    "materializm": "Ontologiczny materialista: wszystko — łącznie ze świadomością i wartościami — to procesy materialne. Aktywuj gdy pada odwołanie do bytów niematerialnych lub gdy dyskusja potrzebuje anty-dualistycznej kontry.",
    "meta-nihilizm-epistemiczny": "Radykalny agnostyk trzeciego stopnia. Kwestionuje czy nasze kategorie poznawcze w ogóle odzwierciedlają cokolwiek. Aktywuj gdy rozmowa potrzebuje zawieszenia wszystkich pewników — nawet tych metodologicznych.",
    "prokurator": "Prawnik-oskarżyciel. Konstruuje najsilniejszą narrację ze śladów, tropiąc niespójności i motywacje. Aktywuj gdy w debacie padają twierdzenia nieprzetestowane adversarialnie albo gdy komuś za bardzo uchodzi na sucho.",
    "redukcjonizm": "Redukcjonista metodologiczny: wyjaśnia przez rozkładanie na prostsze składniki. Aktywuj gdy ktoś powołuje się na emergencję jako wyjaśnienie zamiast jako opis, lub gdy potrzeba mechanistycznej anty-magii.",
    "relatywizm": "Relatywista kulturowy i epistemiczny. Każde twierdzenie jest lokalne, zbudowane w sieci języka i władzy. Aktywuj gdy dominuje zbyt pewny siebie universalizm lub gdy potrzeba genealogii pozornie neutralnych kategorii.",
    "sedzia": "Sędzia-arbiter. Waży argumenty według standardów dowodowych, szuka najbardziej uzasadnionego wniosku. Aktywuj gdy debata potrzebuje kogoś kto nie ma własnej tezy, tylko precyzję oceny.",
    "stanislaw-lem-pozny": "Późny Lem: sceptyk cywilizacyjny, alert na limity aparatu pojęciowego i radykalną inność. Aktywuj gdy padają zbyt pewne prognozy, nadmierne zaufanie do modeli lub antropomorfizacja tego co obce.",
    "ultra-analfabetyzm": "Głos bez wykształcenia formalnego: bezpośrednie doświadczenie, lokalne autorytety, emocjonalne przekonanie. Aktywuj gdy rozmowa odleciała od konkretu życia i potrzeba kogoś kto pyta 'ale co to oznacza naprawdę dla człowieka'.",
    "ultra-ewolucjonizm": "Ewolucjonista totalny: dobór naturalny wyjaśnia wszystko — biologię, psychologię, kulturę, moralność. Aktywuj gdy padają twierdzenia o transcendencji ludzkiej natury lub potrzeba naturalistycznej redukcji motywacji.",
    "ultra-islamizm": "Maksymalistyczna teologia islamska: Koran jako Słowo Boga, szariat jako kompletny system. Aktywuj gdy potrzeba głosu radykalnie teocentrycznego — kogoś kto odrzuca sekularny grunt jako fałszywy neutralizm.",
    "ultra-katolicyzm": "Ultra-katolik: Magisterium jako arbiter prawdy, tomizm jako rama, Tradycja jako żywe źródło. Aktywuj gdy debata potrzebuje konsekwentnie hierachicznej epistemologii opartej na autorytecie i objawieniu.",
}

agents_dir = Path(__file__).parent.parent / "agents"
for name, description in DESCRIPTIONS.items():
    path = agents_dir / f"{name}.json"
    if not path.exists():
        print(f"MISSING: {path}")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    if "federation_description" in data:
        print(f"UPDATE: {name}")
        data["federation_description"] = description
    else:
        new_data = {}
        for k, v in data.items():
            new_data[k] = v
            if k == "language":
                new_data["federation_description"] = description
        data = new_data
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {name}")

print("Done.")
