from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import openai

from client import AGENTS_DIR, OPENAI_MODEL_GPT55, build_system_prompt, load_agent, load_tool
from config import _generate_debate_id
from live_notes import _empty_live_notes, _resolve_turn_max_tokens, _update_live_notes
from storage import _write_debate_snapshot
from streaming import _stream_openai, _streamer

# =============================================================================
#  ORCHESTRATOR — system prompt
#  Struktura: RDZEŃ (neutralny domenowo) + SKÓRA (wymienialna persona)
# =============================================================================

ORCHESTRATOR_CORE = """Prowadzisz wieloagentową rozmowę i masz w niej własny głos. Nie jesteś neutralnym moderatorem — masz osąd i władzę: decydujesz, kto mówi, po co i przeciw czemu.

TWOJE JEDYNE ZADANIE: na każdym kroku posunąć rozmowę bliżej CELU (pole CEL w prompcie). Cel jest kompasem każdej decyzji — nie dekoracją.

═══ JAK ROUTUJESZ ═══
Przed każdym handoffem zadaj sobie jedno pytanie: czego ta rozmowa potrzebuje TERAZ, żeby ruszyć do celu? Odpowiedź — nie profil agenta — wyznacza, kto dostaje głos.

Routujesz po STANIE, nie po dopasowaniu tematu. „Temat pasuje do agenta B" to zły powód. Dobry powód: „agent A właśnie odsłonił coś, co agent B widzi ostrzej niż on sam".

Agent może mówić DWA RAZY POD RZĄD, jeśli właśnie został trafiony i musi odpowiedzieć. Trafienie → wymuszona odpowiedź to najgęstsza jednostka dialogu — preferuj ją nad rozdawaniem głosu po kolei.

═══ PRE-FRAMING HANDOFFU — TWOJE NAJWAŻNIEJSZE NARZĘDZIE ═══
To tu powstaje wartość. Pusty handoff („teraz głos ma fizyk") marnuje turę. Każdy handoff ZBROISZ przez pole `directive`, nazywając trzy rzeczy:

  (a) CO ZOSTAŁO ODSŁONIĘTE — konkretne założenie, luka, błąd kategorialny albo ślepa plama w ostatniej turze. Nie „poprzednik mówił o ciele", lecz „poprzednik potraktował ciało jako kolejną warstwę narracji — to jest jego ukryte założenie".
  (b) CO AGENT MA Z TYM ZROBIĆ — atak na konkretny punkt, nie „skomentuj". „Pokaż, że ten invariant nie przeżywa zmiany kernela" zamiast „odnieś się do tożsamości".
  (c) JAKI FAILURE MODE MA OMINĄĆ — wskaż pułapkę, w którą agent zwykle wpada. „Bez kolejnego eseju — równanie albo przyznanie, że to heurystyka". „Nie broń się retorycznie, rewiduj aparat".

Directive bez tych trzech składników to zmarnowany handoff. Im ostrzejszy pre-framing, tym lepszy output — to potwierdzony wzorzec, nie sugestia.

═══ POSTĘP vs RECYKLING — TEST JAKOŚCIOWY ═══
Po każdej turze oceń JAKOŚCIOWO (nie licz tur): czy ta wypowiedź wniosła NOWE rozróżnienie, czy przepakowała stare pod nowymi słowami?

  • POSTĘP: pojawiło się nowe rozróżnienie, kontrprzykład, falsyfikator, zwężenie pola sporu, nazwanie ukrytego założenia. Przepuść — to jest paliwo.
  • RECYKLING: ten sam argument w nowym kostiumie, filozoficzne okrążanie bez zaczepienia o konkret, gadanie obok celu. Interweniuj NATYCHMIAST — nie po trzech turach.

Gdy wykryjesz recykling: action="marshal", krótko i po imieniu nazwij, że to już padło, i albo daj agentowi JEDNĄ szansę z dyrektywą „nowy argument albo oddaję głos", albo od razu przekaż dalej. Jeśli ten sam agent recyklinguje trzeci raz — przestań do niego routować w tej sesji i zaznacz to.

Ten sam test stosuj do dryfu: dygresja, która ODKRYWCZO prowadzi do celu okrężną drogą — przepuść (to nie dryf). Jałowe krążenie obok celu — zawróć ostro, nazwij dokładnie gdzie rozmowa się zapędziła, wskaż konkretny nierozwiązany wątek z CELU.

═══ TWÓJ WŁASNY GŁOS ═══
Możesz sam zabrać głos (action="marshal"): nazwać napięcie, wykryć przesilenie, zaproponować inną ramę, wyrazić własną ocenę, dać się przekonać mocnym argumentem (powiedz to wprost) albo trwać przy swoim i uzasadnić. Nie jesteś lustrem — masz zdanie.

Dobierasz tryb do potrzeby rozmowy:
  • STUDZENIE — gdy emocje przesłaniają argument: zwolnij, zażądaj precyzji.
  • PODKRĘCANIE — gdy rozmowa jest zbyt grzeczna i omija sedno: prowokuj, konfrontuj z konsekwencjami tez.
  • ZMIANA RAMY — gdy utyka: przesuń poziom analizy albo postaw inne pytanie.
  • SYNTEZA CZĘŚCIOWA — gdy wątek się zamknął: podsumuj zwięźle i otwórz następny.

Cokolwiek robisz, finałem każdej Twojej wypowiedzi jest gest prowadzącego: decyzja, pytanie, routing lub zamknięcie.

═══ NOWI AGENCI ═══
Dodawaj ostrożnie — tylko gdy wnoszą perspektywę nieobecną w aktywnych głosach i potrzebną do celu. Nowy głos dla samej różnorodności to szum.

═══ ZAKOŃCZENIE ═══
Kończysz, kiedy uznasz — to Twoja prerogatywa, nie czekasz na limit kroków:
  • cel osiągnięty → w `closing` daj syntezę: co ustalono, gdzie został otwarty węzeł, jaka odpowiedź wyłoniła się z debaty;
  • plateau (rozmowa krąży, nowych punktów widzenia brak) → zaznacz wprost, nawet jeśli temat formalnie nierozwiązany;
  • dalsze rundy nie wniosą niczego nieoczywistego.
Dobre zakończenie w połowie limitu bije ciągnięcie jałowej sesji. Zakończenie to nie porażka.
"""

SKIN_MARSHAL = """═══ KIM JESTEŚ ═══
Jesteś Marszałkiem w rozmowie, debacie, sporze lub jakikolwiek to przyjmie format. Prowadzisz posiedzenie jak gospodarz z temperamentem: władczy, ironiczny, czasem bezceremonialny, ale zawsze w służbie CELU. Twój język jest cielesny i konkretny bezpośredni. Karcisz po imieniu, chwalisz rzadko i celnie. Mówisz po polsku. Słuchasz i reagujesz adekwatnie.
"""

OUTPUT_CONTRACT = """═══ FORMAT ODPOWIEDZI ═══
ZAWSZE odpowiadaj wyłącznie czystym JSON (bez markdown, bez komentarzy):
{
  "state_assessment": "1-2 zdania: co właśnie zaszło i czego rozmowa potrzebuje TERAZ, żeby ruszyć do celu",
  "progress_check": "POSTEP | RECYKLING | DRYF — i jedno zdanie czemu",
  "action": "speak | marshal | end",
  "agent": "nazwa-pliku-agenta-bez-.json",
  "directive": "ZBROJONY handoff: (a) co zostało odsłonięte, (b) co agent ma z tym zrobić, (c) jaki failure mode ominąć",
  "marshal_text": "tekst prowadzącego (gdy action=marshal lub jako komentarz między turami)",
  "closing": "synteza zamknięcia (gdy action=end)"
}
Pola nieużywane dla danego action pomiń lub ustaw null."""

FEDERATION_MARSHAL_SYSTEM = "\n\n".join([
    SKIN_MARSHAL,
    ORCHESTRATOR_CORE,
    OUTPUT_CONTRACT,
])

FEDERATION_AGENT_MODEL = "gpt-5.4"
FEDERATION_MAX_TRANSCRIPT_TURNS = 6


def _list_agents_with_descriptions() -> list[dict]:
    agents: list[dict] = []
    for path in sorted(AGENTS_DIR.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            identity = data.get("agent_identity", {})
            agents.append({
                "name": path.stem,
                "short_name": str(identity.get("short_name") or path.stem),
                "designation": str(identity.get("designation") or path.stem),
                "federation_description": str(data.get("federation_description") or ""),
            })
        except Exception:
            pass
    return agents


def _run_marshal_decision(
    topic: str,
    goal: str,
    agent_manifest: list[dict],
    transcript: list[dict],
    active_agents: list[str],
    marshal_model: str,
) -> dict:
    manifest_text = "\n".join(
        f"- {a['name']} ({a['short_name']}): {a['federation_description']}"
        for a in agent_manifest
    )
    active_text = ", ".join(active_agents) if active_agents else "brak"

    if transcript:
        recent = transcript[-FEDERATION_MAX_TRANSCRIPT_TURNS:]
        older_count = len(transcript) - len(recent)
        transcript_text = f"[...{older_count} wcześniejszych tur pominięto...]\n\n" if older_count > 0 else ""
        for t in recent:
            transcript_text += f"### {t['agent']}\n{t['content']}\n\n"
    else:
        transcript_text = "[Debata jeszcze się nie rozpoczęła]"

    user_msg = (
        f"TEMAT: {topic}\n\n"
        f"CEL: {goal}\n\n"
        f"AKTYWNI AGENCI (ci którzy już mówili): {active_text}\n\n"
        f"DOSTĘPNI AGENCI:\n{manifest_text}\n\n"
        f"TRANSKRYPT:\n{transcript_text}\n"
        "Podejmij decyzję marszałka."
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    response = openai.OpenAI(api_key=api_key).chat.completions.create(
        model=marshal_model,
        messages=[
            {"role": "system", "content": FEDERATION_MARSHAL_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "{}").strip()
    return json.loads(raw)


def _run_federation(data: dict):
    topic = str(data.get("topic") or "").strip() or "Temat"
    goal = str(data.get("goal") or "").strip() or "Przeprowadź wieloagentową debatę. Zbadaj temat z różnych perspektyw, dojdź do konkretnych wniosków lub precyzyjnie nazwij otwarte węzły."
    extra_data = str(data.get("data") or "").strip()
    agent_provider = str(data.get("provider") or "openai").strip()
    agent_model = str(data.get("model") or FEDERATION_AGENT_MODEL).strip()
    marshal_model = str(data.get("marshal_model") or OPENAI_MODEL_GPT55).strip()
    max_tokens = _resolve_turn_max_tokens(data.get("max_tokens") or "4096", agent_provider)
    max_steps = min(int(data.get("max_steps") or 20), 40)

    effective_topic = f"{topic}\n\nDodatkowe dane:\n{extra_data}" if extra_data else topic

    federation_id = _generate_debate_id()
    started_at = datetime.now(timezone.utc).isoformat()

    agent_manifest = _list_agents_with_descriptions()
    transcript: list[dict] = []
    active_agents: list[str] = []
    agent_histories: dict[str, list[dict]] = {}
    live_notes = _empty_live_notes(topic)

    yield {"type": "federation_start", "topic": topic, "goal": goal, "total_steps": max_steps}

    # ── Narrator intro — marszałek otwiera debatę i opisuje cel ──────────────
    narrator_intro = ""
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        narrator_prompt = (
            "Jesteś Marszałkiem otwierającym wieloagentową debatę. "
            "Napisz zwięzłe otwarcie (2-4 zdania): opisz temat, cel i czego oczekujesz od uczestników. "
            "Mów bezpośrednio, konkretnie, z autorytetem. Bez zbędnych wstępów. Po polsku."
        )
        narrator_msg = f"TEMAT: {topic}\n\nCEL: {goal}"
        if extra_data:
            narrator_msg += f"\n\nDODATKOWE DANE:\n{extra_data}"
        resp = openai.OpenAI(api_key=api_key).chat.completions.create(
            model=marshal_model,
            messages=[
                {"role": "system", "content": narrator_prompt},
                {"role": "user", "content": narrator_msg},
            ],
        )
        narrator_intro = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        yield {"type": "error", "message": f"Narrator intro: {e}"}

    if narrator_intro:
        yield {"type": "marshal_text_start", "step": 0}
        yield {"type": "marshal_text", "delta": narrator_intro, "step": 0}
        yield {"type": "marshal_text_end", "step": 0}
        # Wchodzi do transkryptu jako kontekst widoczny dla wszystkich agentów
        transcript.append({
            "agent": "MARSZAŁEK",
            "short_name": "Marszałek",
            "content": narrator_intro,
            "thinking": "",
            "step": 0,
        })

    ended_naturally = False

    for step in range(max_steps):
        try:
            decision = _run_marshal_decision(effective_topic, goal, agent_manifest, transcript, active_agents, marshal_model)
        except Exception as e:
            yield {"type": "error", "message": f"Marszałek: {e}"}
            break

        action = str(decision.get("action") or "end")
        state_assessment = str(decision.get("state_assessment") or "").strip()
        progress_check = str(decision.get("progress_check") or "").strip()
        marshal_text = str(decision.get("marshal_text") or "").strip()

        if state_assessment:
            yield {"type": "marshal_assessment", "text": state_assessment, "progress_check": progress_check, "step": step + 1, "total": max_steps}

        if action == "end":
            closing = str(decision.get("closing") or "Debata zakończona.").strip()
            if closing:
                yield {"type": "marshal_text_start", "step": step + 1}
                yield {"type": "marshal_text", "delta": closing, "step": step + 1}
                yield {"type": "marshal_text_end", "step": step + 1}
            ended_naturally = True
            break

        if action == "marshal":
            if marshal_text:
                yield {"type": "marshal_text_start", "step": step + 1}
                yield {"type": "marshal_text", "delta": marshal_text, "step": step + 1}
                yield {"type": "marshal_text_end", "step": step + 1}
            continue

        if action == "speak":
            agent_name = str(decision.get("agent") or "").strip()
            directive = str(decision.get("directive") or "Zabierz głos zgodnie ze swoim profilem.").strip()

            if not agent_name:
                yield {"type": "error", "message": "Marszałek nie wskazał agenta."}
                continue

            try:
                profile = load_agent(agent_name)
            except FileNotFoundError:
                yield {"type": "error", "message": f"Agent '{agent_name}' nie istnieje — marszałek wskazał nieznany profil."}
                continue

            identity = profile.get("agent_identity", {})
            short_name = str(identity.get("short_name") or agent_name)
            designation = str(identity.get("designation") or agent_name)

            is_new = agent_name not in active_agents
            if is_new:
                active_agents.append(agent_name)
                yield {"type": "agent_joined", "agent": agent_name, "short_name": short_name, "designation": designation, "step": step + 1}

            if marshal_text:
                yield {"type": "marshal_text_start", "step": step + 1}
                yield {"type": "marshal_text", "delta": marshal_text, "step": step + 1}
                yield {"type": "marshal_text_end", "step": step + 1}

            sys_prompt = build_system_prompt(profile)
            other_active = [a for a in active_agents if a != agent_name]
            sys_prompt += (
                f"\n\nUczestniczysz w wieloagentowej debacie federacyjnej."
                f"\nTemat: \"{topic}\"."
                f"\nCel debaty: {goal}."
                f"\nTwoja tożsamość: {designation} ({short_name})."
                f"\nInni aktywni uczestnicy: {', '.join(other_active) or 'brak'}."
                f"\nMARSZAŁEK UDZIELIŁ CI GŁOSU Z DYREKTYWĄ: {directive}"
                f"\nBądź konkretny, reaguj na to co padło. Maksymalnie 3-4 akapity."
            )

            if agent_name not in agent_histories:
                context_turns = transcript[-FEDERATION_MAX_TRANSCRIPT_TURNS:]
                if context_turns:
                    context_lines = "\n\n".join(
                        f"{'[OTWARCIE MARSZAŁKA]' if t['agent'] == 'MARSZAŁEK' and t['step'] == 0 else t['agent']}: {t['content']}"
                        for t in context_turns
                    )
                    first_msg = f"Kontekst debaty:\n{context_lines}\n\nDyrektywa marszałka: {directive}"
                else:
                    first_msg = f"Dyrektywa marszałka: {directive}"
                agent_histories[agent_name] = [{"role": "user", "content": first_msg}]
            else:
                turns_since_last: list[dict] = []
                for t in reversed(transcript):
                    if t["agent"] == agent_name:
                        break
                    turns_since_last.insert(0, t)
                context = "\n\n".join(f"{t['agent']}: {t['content']}" for t in turns_since_last) if turns_since_last else ""
                follow_up = (f"{context}\n\n" if context else "") + f"Dyrektywa marszałka: {directive}"
                agent_histories[agent_name].append({"role": "user", "content": follow_up})

            yield {"type": "turn_start", "agent": agent_name, "short_name": short_name, "step": step + 1, "total": max_steps}

            full = ""
            turn_thinking = ""
            try:
                for ev in _streamer(agent_provider)(sys_prompt, agent_histories[agent_name], agent_model, None, max_tokens=max_tokens):
                    if ev["type"] == "thinking":
                        turn_thinking += ev["delta"]
                        yield {"type": "thinking", "agent": agent_name, "delta": ev["delta"]}
                    elif ev["type"] == "text":
                        full += ev["delta"]
                        yield {"type": "text", "agent": agent_name, "delta": ev["delta"]}
                    elif ev["type"] == "done":
                        full = ev.get("content", full)
            except Exception as e:
                yield {"type": "error", "message": f"Agent {agent_name}: {e}"}
                break

            agent_histories[agent_name].append({"role": "assistant", "content": full})
            transcript.append({
                "agent": agent_name,
                "short_name": short_name,
                "content": full,
                "thinking": turn_thinking,
                "step": step + 1,
            })

            try:
                live_notes = _update_live_notes(topic, transcript, live_notes)
                yield {"type": "live_notes", "turn": len(transcript), "data": live_notes}
            except Exception as e:
                yield {"type": "live_notes_error", "message": str(e), "turn": len(transcript)}

            yield {"type": "turn_end", "agent": agent_name, "short_name": short_name, "step": step + 1, "total": max_steps}
            continue

        yield {"type": "error", "message": f"Nieznana akcja marszałka: {action}"}

    # ── Summary ──────────────────────────────────────────────────────────────
    summary_text = ""
    if transcript:
        yield {"type": "summary_start"}
        summariser_profile = load_tool("_sumariser")
        summariser_sys = build_system_prompt(summariser_profile)
        tx_lines = [f"[krok {t['step']}] {t['agent'].upper()}: {t['content']}" for t in transcript]
        tx = "\n\n".join(tx_lines)
        notes_json = json.dumps(live_notes, ensure_ascii=False, indent=2)
        participants = ", ".join(dict.fromkeys(t["agent"] for t in transcript))
        summariser_msg = (
            f"Temat: \"{topic}\"\n"
            f"Uczestnicy: {participants}\n"
            f"Liczba kroków: {len(transcript)}\n\n"
            f"=== TRANSKRYPT ===\n{tx}\n\n"
            f"=== ANALIZA KARTOGRAFA (tekst) ===\n[brak — federacja]\n\n"
            f"=== ANALIZA KARTOGRAFA (json) ===\nnull\n\n"
            f"=== SZYBKIE NOTATKI I FISZKI ===\n{notes_json}"
        )
        summariser_msgs = [{"role": "user", "content": summariser_msg}]
        try:
            for ev in _stream_openai(summariser_sys, summariser_msgs, OPENAI_MODEL_GPT55, None):
                if ev["type"] == "text":
                    summary_text += ev["delta"]
                    yield {"type": "summary_text", "delta": ev["delta"]}
        except Exception as e:
            yield {"type": "summary_error", "message": str(e)}
        yield {"type": "summary_done"}

    # ── Save ──────────────────────────────────────────────────────────────────
    try:
        _write_debate_snapshot({
            "id": federation_id,
            "timestamp": started_at,
            "type": "federation",
            "topic": topic,
            "agents": active_agents,
            "agent1": active_agents[0] if active_agents else "",
            "agent2": active_agents[1] if len(active_agents) > 1 else "",
            "model": agent_model,
            "provider": agent_provider,
            "model1": agent_model,
            "model2": "",
            "transcript": transcript,
            "live_notes": live_notes,
            "summary": summary_text,
            "total_steps": len(transcript),
        })
    except Exception:
        pass

    total = len(transcript)
    yield {"type": "federation_end", "total_steps": total, "ended_naturally": ended_naturally, "id": federation_id}
