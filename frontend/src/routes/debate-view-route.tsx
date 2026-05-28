import type { DebateViewBootstrapData } from "../lib/types/bootstrap";
import type { DebateHistoryMessage, DebateRecord } from "../lib/types/bootstrap";
import { HomePage } from "../modules/home/home-page";
import { normalizeDebateSettings } from "../modules/home/shared/home-constants";
import type { DebateContinuationState, DebateProgress, DebateSettings, DebateTranscriptEntry, LiveNotes } from "../modules/home/shared/home-types";

type DebateViewRouteProps = {
  data: DebateViewBootstrapData;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readNumber(value: unknown): number | null {
  const parsed = Number.parseInt(String(value ?? ""), 10);

  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeHistory(history: DebateHistoryMessage[] | undefined): DebateHistoryMessage[] {
  return Array.isArray(history) ? history.map((entry) => ({ role: entry.role, content: entry.content })) : [];
}

function normalizeProvider(value: string | undefined): "openai" | "anthropic" | undefined {
  if (value === "openai" || value === "anthropic") {
    return value;
  }

  return undefined;
}

function normalizeLiveNotes(value: DebateRecord["live_notes"], transcriptLength: number): { liveNotes: LiveNotes | null; lastTurn: number | null } {
  if (!isRecord(value)) {
    return { liveNotes: null, lastTurn: null };
  }

  const entries = Array.isArray(value.entries)
    ? value.entries
        .filter(isRecord)
        .map((entry) => ({
          turn: readNumber(entry.turn) ?? 0,
          agent: typeof entry.agent === "string" ? entry.agent : undefined,
          note: typeof entry.note === "string" ? entry.note : undefined,
        }))
        .filter((entry) => entry.turn > 0)
    : [];

  const factCards = Array.isArray(value.fact_cards)
    ? value.fact_cards
        .filter(isRecord)
        .map((entry) => ({
          turn: readNumber(entry.turn) ?? 0,
          agent: typeof entry.agent === "string" ? entry.agent : undefined,
          request: typeof entry.request === "string" ? entry.request : undefined,
        }))
        .filter((entry) => entry.turn > 0)
    : [];

  const lastTurn = entries.length > 0 ? Math.max(...entries.map((entry) => entry.turn)) : transcriptLength > 0 ? transcriptLength : null;

  return {
    liveNotes: {
      entries,
      fact_cards: factCards,
      facts_error: typeof value.facts_error === "string" ? value.facts_error : undefined,
    },
    lastTurn,
  };
}

function buildDebateSettings(record: DebateRecord, agents: string[], models: DebateViewBootstrapData["models"]): DebateSettings {
  const config = isRecord(record.config) ? record.config : {};
  const configDebateMode = typeof config.debate_mode === "string" ? config.debate_mode : undefined;
  const configDebateModeCustom = typeof config.debate_mode_custom === "string" ? config.debate_mode_custom : undefined;

  return normalizeDebateSettings(
    {
      ...config,
      agent1: record.agent1,
      agent2: record.agent2,
      provider1: normalizeProvider(record.provider1),
      provider2: normalizeProvider(record.provider2),
      model1: record.model1,
      model2: record.model2,
      thinking_effort1: record.thinking_effort1,
      thinking_effort2: record.thinking_effort2,
      max_tokens1: record.max_tokens1,
      max_tokens2: record.max_tokens2,
      topic: record.topic,
      debate_mode: configDebateMode ?? record.debate_mode,
      debate_mode_custom: configDebateModeCustom ?? record.debate_mode_custom,
      max_turns: readNumber(config.max_turns) ?? record.transcript.length,
    },
    agents,
    models,
  );
}

function buildDebateTranscript(record: DebateRecord): DebateTranscriptEntry[] {
  const totalTurns = record.transcript.length;
  const entries: DebateTranscriptEntry[] = [];

  if (record.topic.trim()) {
    entries.push({ id: `topic-${record.id || "debate"}`, type: "topic", topic: record.topic });
  }

  record.transcript.forEach((entry, index) => {
    entries.push({
      id: `turn-${record.id || "debate"}-${index + 1}`,
      type: "turn",
      slot: entry.agent === record.agent1 ? "s1" : "s2",
      agent: entry.agent,
      turn: index + 1,
      total: totalTurns,
      thinking: entry.thinking ?? "",
      content: entry.content,
      renderContentAsMarkdown: true,
    });
  });

  if (record.analysis || record.analysis_json) {
    entries.push({ id: `analysis-divider-${record.id || "debate"}`, type: "divider", label: "ANALIZATOR" });
    entries.push({
      id: `analysis-${record.id || "debate"}`,
      type: "analysis",
      variant: "analyzer",
      title: "🔬 ANALIZATOR",
      content: record.analysis ?? "",
      renderContentAsMarkdown: !record.analysis_json,
      jsonData: record.analysis_json ?? undefined,
    });
  }

  if (record.summary) {
    entries.push({ id: `summary-divider-${record.id || "debate"}`, type: "divider", label: "SUMMARISER" });
    entries.push({
      id: `summary-${record.id || "debate"}`,
      type: "analysis",
      variant: "summariser",
      title: "🧩 SUMMARISER",
      content: record.summary,
      renderContentAsMarkdown: true,
    });
  }

  return entries;
}

function buildContinuationState(record: DebateRecord, liveNotes: LiveNotes | null): DebateContinuationState | null {
  if (!record.id) {
    return null;
  }

  return {
    history1: normalizeHistory(record.history1),
    history2: normalizeHistory(record.history2),
    transcript: record.transcript.map((entry) => ({ agent: entry.agent, content: entry.content, thinking: entry.thinking })),
    live_notes: liveNotes,
    turns_completed: record.transcript.length,
  };
}

function buildProgress(record: DebateRecord, settings: DebateSettings): DebateProgress {
  const completedTurns = record.transcript.length;
  const targetTurns = Math.max(settings.max_turns, completedTurns, 1);
  const completed = completedTurns >= targetTurns && completedTurns > 0;

  return {
    fillPercent: Math.min(100, (completedTurns / targetTurns) * 100),
    label: completed ? "Zapisano ✓" : `${completedTurns} / ${targetTurns}`,
    savedDebateId: record.id || null,
  };
}

export function DebateViewRoute({ data }: DebateViewRouteProps) {
  const debateSettings = buildDebateSettings(data.debate, data.agents, data.models);
  const { liveNotes, lastTurn } = normalizeLiveNotes(data.debate.live_notes, data.debate.transcript.length);
  const compactSetup = data.debate.setup ?? null;
  const shouldAutoStartDebate = data.debate.transcript.length === 0 && compactSetup !== null;

  return (
    <HomePage
      agents={data.agents}
      models={data.models}
      initialMode="debate"
      lockMode="debate"
      autoStartDebate={shouldAutoStartDebate}
      debateSidebarVariant={compactSetup ? "compact-readonly" : "default"}
      compactDebateSidebar={compactSetup}
      initialDebateSession={{
        debateSettings,
        debateTranscript: buildDebateTranscript(data.debate),
        progress: buildProgress(data.debate, debateSettings),
        liveNotes,
        notesSubtitle: data.debate.topic ? "Aktualizowane po każdej turze debaty" : "Po prawej pojawi się skrót sporu",
        lastLiveNotesTurn: lastTurn,
        debateContinuationState: buildContinuationState(data.debate, liveNotes),
        lastDebateConfig: debateSettings,
        savedDebateId: data.debate.id || null,
        currentAgents: {
          agent1: data.debate.agent1,
          agent2: data.debate.agent2,
        },
      }}
    />
  );
}