from __future__ import annotations

import json
import re

from client import AGENTS_DIR, OPENAI_MODEL
from config import DEBATES_DIR
from debate_schema import _build_debate_config, _normalize_legacy_debate_mode


def _write_debate_snapshot(record: dict) -> None:
    DEBATES_DIR.mkdir(exist_ok=True)
    debate_id = str(record["id"])
    (DEBATES_DIR / f"{debate_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _list_agents() -> list[str]:
    return sorted(p.stem for p in AGENTS_DIR.glob("*.json") if not p.stem.startswith("_"))


def _load_debates_index() -> list[dict]:
    files = sorted(DEBATES_DIR.glob("*.json"), reverse=True) if DEBATES_DIR.exists() else []
    debates: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            record_type = str(data.get("type") or "debate")
            topic = str(data.get("topic") or "").strip()
            summary = str(data.get("summary") or "").strip()
            snippet_src = summary or topic
            snippet = (snippet_src[:200] + "…") if len(snippet_src) > 200 else snippet_src
            entry: dict = {
                "id": data["id"],
                "timestamp": data.get("timestamp", ""),
                "type": record_type,
                "topic": topic,
                "turns": len(data.get("transcript", [])),
                "snippet": snippet,
                "agent1": str(data.get("agent1") or ""),
                "agent2": str(data.get("agent2") or ""),
                "model1": str(data.get("model1") or data.get("model") or ""),
                "model2": str(data.get("model2") or ""),
                "agents": list(data.get("agents") or [
                    a for a in [data.get("agent1"), data.get("agent2")] if a
                ]),
            }
            debates.append(entry)
        except Exception:
            pass
    return debates


def _load_debate_record(debate_id: str) -> dict | None:
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", debate_id)
    path = DEBATES_DIR / f"{safe_id}.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(record.get("config"), dict):
        return record
    restored_config = _build_debate_config(
        agent1=str(record.get("agent1") or ""),
        agent2=str(record.get("agent2") or ""),
        provider1=str(record.get("provider1") or "openai"),
        provider2=str(record.get("provider2") or "openai"),
        model1=str(record.get("model1") or OPENAI_MODEL),
        model2=str(record.get("model2") or OPENAI_MODEL),
        thinking_effort1=record.get("thinking_effort1") or None,
        thinking_effort2=record.get("thinking_effort2") or None,
        max_tokens1=str(record.get("max_tokens1") or "4096"),
        max_tokens2=str(record.get("max_tokens2") or "4096"),
        topic=str(record.get("topic") or ""),
        debate_mode=_normalize_legacy_debate_mode(record.get("debate_mode")),
        debate_mode_custom=str(record.get("debate_mode_custom") or ""),
        max_turns=int(record.get("max_turns") or len(record.get("transcript") or [])),
    )
    return {**record, "config": restored_config}
