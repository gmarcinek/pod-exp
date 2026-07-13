import { useEffect, useMemo, useRef, useState } from "react";
import type {
  DebateListItem,
  DebateSetupData,
  ModelCatalog,
} from "../../lib/types/bootstrap";
import { ChatConfigPanel } from "./chat/chat-config-panel";
import { ChatInput } from "./chat/chat-input";
import { ChatTranscript } from "./chat/chat-transcript";
import { buildApiPath, buildAppPath } from "../../bootstrap/backend-config";
import { DebateConfigPanel } from "./debate/debate-config-panel";
import { DebateTranscript } from "./debate/debate-transcript";
import { LiveNotesPanel } from "./debate/live-notes-panel";
import {
  THINKING_MODELS,
  getDefaultChatSettings,
  getDefaultDebateSettings,
  normalizeChatSettings,
  normalizeDebateSettings,
} from "./shared/home-constants";
import styles from "./shared/home-screen.module.scss";
import {
  clearStoredSettings,
  loadChatSettings,
  loadDebateSettings,
  saveChatSettings,
  saveDebateSettings,
} from "./shared/home-storage";
import type {
  ChatSettings,
  ChatTranscriptEntry,
  DebateAnalysisEntry,
  DebateContinuationState,
  DebateProgress,
  DebateSettings,
  DebateTranscriptEntry,
  HomeMode,
  LiveNotes,
} from "./shared/home-types";

type InitialDebateSessionState = {
  debateSettings: DebateSettings;
  debateTranscript: DebateTranscriptEntry[];
  progress: DebateProgress;
  liveNotes: LiveNotes | null;
  notesSubtitle: string;
  lastLiveNotesTurn: number | null;
  debateContinuationState: DebateContinuationState | null;
  lastDebateConfig: DebateSettings | null;
  savedDebateId: string | null;
  currentAgents: { agent1: string; agent2: string };
};

type CompactDebateSidebar = DebateSetupData;

type HomePageProps = {
  agents: string[];
  models: ModelCatalog;
  debates?: DebateListItem[];
  initialMode?: HomeMode;
  lockMode?: HomeMode;
  initialDebateSession?: InitialDebateSessionState | null;
  initialDebateSettings?: DebateSettings | null;
  autoStartDebate?: boolean;
  debateSidebarVariant?: "default" | "compact-readonly";
  compactDebateSidebar?: CompactDebateSidebar | null;
};

type ChatApiMessage = {
  role: "user" | "assistant";
  content: string;
};

let nextId = 0;

function createId(prefix: string) {
  nextId += 1;
  return `${prefix}-${nextId}`;
}

function createDefaultProgress(maxTurns: number): DebateProgress {
  return {
    fillPercent: 0,
    label: `0 / ${maxTurns}`,
    savedDebateId: null,
  };
}

function trimPreview(value: string, maxLength = 220) {
  const normalized = value.trim();
  if (!normalized) {
    return "Brak";
  }

  return normalized.length > maxLength
    ? `${normalized.slice(0, maxLength).trimEnd()}...`
    : normalized;
}

function formatDebateTimestamp(timestamp: string) {
  const date = timestamp.slice(0, 10);
  const time = timestamp.length > 15 ? timestamp.slice(11, 16) : "";
  return `${date} ${time}`.trim();
}

export function HomePage({
  agents,
  models,
  debates = [],
  initialMode,
  lockMode,
  initialDebateSession = null,
  initialDebateSettings = null,
  autoStartDebate = false,
  debateSidebarVariant = "default",
  compactDebateSidebar = null,
}: HomePageProps) {
  const defaultChatSettings = useMemo(
    () => getDefaultChatSettings(agents, models),
    [agents, models],
  );
  const defaultDebateSettings = useMemo(
    () => getDefaultDebateSettings(agents, models),
    [agents, models],
  );
  const resolvedInitialDebateSettings =
    initialDebateSession?.debateSettings ??
    initialDebateSettings ??
    loadDebateSettings(agents, models);
  const defaultMode = lockMode ?? initialMode ?? "chat";
  const [mode, setMode] = useState<HomeMode>(defaultMode);
  const [chatSettings, setChatSettings] = useState<ChatSettings>(() =>
    loadChatSettings(agents, models),
  );
  const [debateSettings, setDebateSettings] = useState<DebateSettings>(
    resolvedInitialDebateSettings,
  );
  const [conversation, setConversation] = useState<ChatApiMessage[]>([]);
  const [chatTranscript, setChatTranscript] = useState<ChatTranscriptEntry[]>(
    [],
  );
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [debateTranscript, setDebateTranscript] = useState<
    DebateTranscriptEntry[]
  >(() => initialDebateSession?.debateTranscript ?? []);
  const [debateActive, setDebateActive] = useState(false);
  const [progress, setProgress] = useState<DebateProgress>(
    () =>
      initialDebateSession?.progress ??
      createDefaultProgress(resolvedInitialDebateSettings.max_turns),
  );
  const [liveNotes, setLiveNotes] = useState<LiveNotes | null>(
    () => initialDebateSession?.liveNotes ?? null,
  );
  const [notesSubtitle, setNotesSubtitle] = useState(
    () =>
      initialDebateSession?.notesSubtitle ?? "Po prawej pojawi się skrót sporu",
  );
  const [lastLiveNotesTurn, setLastLiveNotesTurn] = useState<number | null>(
    () => initialDebateSession?.lastLiveNotesTurn ?? null,
  );
  const [debateContinuationState, setDebateContinuationState] =
    useState<DebateContinuationState | null>(
      () => initialDebateSession?.debateContinuationState ?? null,
    );
  const [lastDebateConfig, setLastDebateConfig] =
    useState<DebateSettings | null>(
      () => initialDebateSession?.lastDebateConfig ?? null,
    );
  const chatMessagesRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentTurnIdRef = useRef<string | null>(null);
  const currentAnalysisIdRef = useRef<string | null>(null);
  const currentSummaryIdRef = useRef<string | null>(null);
  const currentAgentsRef = useRef(
    initialDebateSession?.currentAgents ?? { agent1: "", agent2: "" },
  );
  const savedDebateIdRef = useRef<string | null>(
    initialDebateSession?.savedDebateId ?? null,
  );
  const autoStartTriggeredRef = useRef(false);

  const showChatThinking = THINKING_MODELS.has(chatSettings.model);
  const isCompactDebateSidebar =
    mode === "debate" && debateSidebarVariant === "compact-readonly";
  const isDebateLanding =
    mode === "debate" &&
    !lockMode &&
    initialDebateSession === null &&
    debateSidebarVariant === "default";

  useEffect(() => {
    saveChatSettings(chatSettings);
  }, [chatSettings]);

  useEffect(() => {
    saveDebateSettings(debateSettings);
  }, [debateSettings]);

  useEffect(() => {
    const normalizedChat = normalizeChatSettings(chatSettings, agents, models);
    if (JSON.stringify(normalizedChat) !== JSON.stringify(chatSettings)) {
      setChatSettings(normalizedChat);
    }

    const normalizedDebate = normalizeDebateSettings(
      debateSettings,
      agents,
      models,
    );
    if (JSON.stringify(normalizedDebate) !== JSON.stringify(debateSettings)) {
      setDebateSettings(normalizedDebate);
    }
  }, [agents, models]);

  useEffect(() => {
    chatMessagesRef.current?.scrollTo({
      top: chatMessagesRef.current.scrollHeight,
    });
  }, [chatTranscript, debateTranscript]);

  function resizeInput() {
    const element = chatInputRef.current;
    if (!element) {
      return;
    }

    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }

  function resetNotesPanel(topic = "") {
    setLiveNotes(null);
    setLastLiveNotesTurn(null);
    setNotesSubtitle(
      topic
        ? "Aktualizowane po każdej turze debaty"
        : "Po prawej pojawi się skrót sporu",
    );
  }

  function resetWorkspace() {
    abortControllerRef.current?.abort();
    setConversation([]);
    setChatTranscript([]);
    setChatInput("");
    setChatBusy(false);
    setDebateTranscript([]);
    setDebateActive(false);
    setProgress(createDefaultProgress(debateSettings.max_turns));
    resetNotesPanel();
    setDebateContinuationState(null);
    setLastDebateConfig(null);
    savedDebateIdRef.current = null;
    currentTurnIdRef.current = null;
    currentAnalysisIdRef.current = null;
    currentSummaryIdRef.current = null;
  }

  function handleModeChange(nextMode: HomeMode) {
    if (lockMode) {
      return;
    }

    setMode(nextMode);
    resetWorkspace();
  }

  function handleChatSettingsChange(value: ChatSettings) {
    setChatSettings(normalizeChatSettings(value, agents, models));
  }

  function handleDebateSettingsChange(value: DebateSettings) {
    setDebateSettings(normalizeDebateSettings(value, agents, models));
  }

  function resetStoredModelSettings() {
    clearStoredSettings();
    setChatSettings(defaultChatSettings);
    setDebateSettings(defaultDebateSettings);
  }

  async function sendChatMessage() {
    if (chatBusy) {
      return;
    }

    const text = chatInput.trim();
    if (!text) {
      return;
    }

    const userMessage: ChatTranscriptEntry = {
      id: createId("chat-user"),
      role: "user",
      content: text,
    };
    const nextConversation = [
      ...conversation,
      { role: "user", content: text } satisfies ChatApiMessage,
    ];

    setChatInput("");
    setConversation(nextConversation);
    setChatTranscript((current) => [...current, userMessage]);
    setChatBusy(true);

    try {
      const response = await fetch(buildApiPath("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent: chatSettings.agent,
          provider: chatSettings.provider,
          model: chatSettings.model,
          thinking_effort: chatSettings.thinking_effort,
          messages: nextConversation,
        }),
      });
      const data = (await response.json()) as {
        error?: string;
        content?: string;
      };

      if (data.error) {
        setChatTranscript((current) => [
          ...current,
          {
            id: createId("chat-error"),
            role: "error",
            content: data.error ?? "Nieznany błąd",
          },
        ]);
      } else if (typeof data.content === "string") {
        const assistantContent = data.content;
        setConversation((current) => [
          ...current,
          { role: "assistant", content: assistantContent },
        ]);
        setChatTranscript((current) => [
          ...current,
          {
            id: createId("chat-assistant"),
            role: "assistant",
            content: assistantContent,
          },
        ]);
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Nieznany błąd połączenia";
      setChatTranscript((current) => [
        ...current,
        {
          id: createId("chat-error"),
          role: "error",
          content: `Błąd połączenia: ${message}`,
        },
      ]);
    } finally {
      setChatBusy(false);
      window.requestAnimationFrame(() => {
        if (chatInputRef.current) {
          chatInputRef.current.style.height = "";
          chatInputRef.current.focus();
        }
      });
    }
  }

  function updateDebateEntry(
    id: string | null,
    updater: (entry: DebateTranscriptEntry) => DebateTranscriptEntry,
  ) {
    if (!id) {
      return;
    }

    setDebateTranscript((current) =>
      current.map((entry) => (entry.id === id ? updater(entry) : entry)),
    );
  }

  function addDebateError(message: string) {
    setDebateTranscript((current) => [
      ...current,
      { id: createId("debate-error"), type: "error", message },
    ]);
  }

  function onDebateEvent(event: Record<string, unknown>) {
    switch (event.type) {
      case "turn_start": {
        const turnEntry: DebateTranscriptEntry = {
          id: createId("turn"),
          type: "turn",
          slot: event.agent === currentAgentsRef.current.agent1 ? "s1" : "s2",
          agent: String(event.agent ?? ""),
          turn: Number(event.turn ?? 0),
          total: Number(event.total ?? 0),
          thinking: "",
          content: "",
          renderContentAsMarkdown: false,
        };
        currentTurnIdRef.current = turnEntry.id;
        setDebateTranscript((current) => [...current, turnEntry]);
        setProgress({
          fillPercent: turnEntry.total
            ? ((turnEntry.turn - 1) / turnEntry.total) * 100
            : 0,
          label: `${turnEntry.turn} / ${turnEntry.total}`,
          savedDebateId: savedDebateIdRef.current,
        });
        break;
      }
      case "thinking": {
        updateDebateEntry(currentTurnIdRef.current, (entry) =>
          entry.type === "turn"
            ? {
                ...entry,
                thinking: `${entry.thinking}${String(event.delta ?? "")}`,
              }
            : entry,
        );
        break;
      }
      case "text": {
        updateDebateEntry(currentTurnIdRef.current, (entry) =>
          entry.type === "turn"
            ? {
                ...entry,
                content: `${entry.content}${String(event.delta ?? "")}`,
              }
            : entry,
        );
        break;
      }
      case "turn_end": {
        updateDebateEntry(currentTurnIdRef.current, (entry) =>
          entry.type === "turn"
            ? { ...entry, renderContentAsMarkdown: true }
            : entry,
        );
        setProgress({
          fillPercent: Number(event.total)
            ? (Number(event.turn) / Number(event.total)) * 100
            : 0,
          label: `${String(event.turn ?? 0)} / ${String(event.total ?? 0)}`,
          savedDebateId: savedDebateIdRef.current,
        });
        currentTurnIdRef.current = null;
        break;
      }
      case "live_notes": {
        const nextLiveNotes = (event.data ?? null) as LiveNotes | null;
        setLiveNotes(nextLiveNotes);
        setLastLiveNotesTurn(Number(event.turn ?? 0));
        break;
      }
      case "live_notes_error": {
        setNotesSubtitle(
          `Notatki pominięte po turze ${String(event.turn ?? "?")}: ${String(event.message ?? "")}`,
        );
        break;
      }
      case "analysis_start": {
        const dividerId = createId("analysis-divider");
        const analysisId = createId("analysis");
        currentAnalysisIdRef.current = analysisId;
        setDebateTranscript((current) => [
          ...current,
          { id: dividerId, type: "divider", label: "ANALIZATOR" },
          {
            id: analysisId,
            type: "analysis",
            variant: "analyzer",
            title: "🔬 ANALIZATOR",
            content: "",
            renderContentAsMarkdown: false,
          },
        ]);
        break;
      }
      case "analysis_text": {
        updateDebateEntry(currentAnalysisIdRef.current, (entry) =>
          entry.type === "analysis"
            ? {
                ...entry,
                content: `${entry.content}${String(event.delta ?? "")}`,
              }
            : entry,
        );
        break;
      }
      case "analysis_json": {
        updateDebateEntry(currentAnalysisIdRef.current, (entry) =>
          entry.type === "analysis"
            ? ({ ...entry, jsonData: event.data } satisfies DebateAnalysisEntry)
            : entry,
        );
        currentAnalysisIdRef.current = null;
        break;
      }
      case "summary_start": {
        const dividerId = createId("summary-divider");
        const summaryId = createId("summary");
        currentSummaryIdRef.current = summaryId;
        setDebateTranscript((current) => [
          ...current,
          { id: dividerId, type: "divider", label: "SUMMARISER" },
          {
            id: summaryId,
            type: "analysis",
            variant: "summariser",
            title: "🧩 SUMMARISER",
            content: "",
            renderContentAsMarkdown: false,
          },
        ]);
        break;
      }
      case "summary_text": {
        updateDebateEntry(currentSummaryIdRef.current, (entry) =>
          entry.type === "analysis"
            ? {
                ...entry,
                content: `${entry.content}${String(event.delta ?? "")}`,
              }
            : entry,
        );
        break;
      }
      case "summary_done": {
        updateDebateEntry(currentSummaryIdRef.current, (entry) =>
          entry.type === "analysis"
            ? { ...entry, renderContentAsMarkdown: true }
            : entry,
        );
        currentSummaryIdRef.current = null;
        setProgress({
          fillPercent: 100,
          label: "Zakończono ✓",
          savedDebateId: savedDebateIdRef.current,
        });
        break;
      }
      case "summary_error": {
        addDebateError(
          `Summariser: ${String(event.message ?? "Nieznany błąd")}`,
        );
        break;
      }
      case "saved": {
        const savedId = String(event.id ?? "");
        const nextConfig = normalizeDebateSettings(
          (event.config ?? null) as Partial<DebateSettings> | null,
          agents,
          models,
        );
        savedDebateIdRef.current = savedId;
        setDebateContinuationState(
          (event.continuation ?? null) as DebateContinuationState | null,
        );
        setLastDebateConfig(nextConfig);
        setDebateSettings(nextConfig);
        setProgress({
          fillPercent: 100,
          label: "Zapisano ✓",
          savedDebateId: savedId,
        });
        break;
      }
      case "error": {
        addDebateError(String(event.message ?? "Nieznany błąd"));
        break;
      }
      default:
        break;
    }
  }

  async function startDebate(options?: { continuation?: boolean }) {
    if (debateActive) {
      return;
    }

    const isContinuation = options?.continuation === true;
    const nextTurns = debateSettings.max_turns;
    const baseConfig =
      isContinuation && lastDebateConfig
        ? { ...lastDebateConfig, max_turns: nextTurns }
        : debateSettings;
    const config = normalizeDebateSettings(baseConfig, agents, models);
    const completedTurns = isContinuation
      ? (debateContinuationState?.turns_completed ??
        debateContinuationState?.transcript?.length ??
        0)
      : 0;
    const totalTurns = completedTurns + config.max_turns;
    const continuationSnapshot = debateContinuationState;

    setDebateSettings(config);
    setLastDebateConfig(config);
    setDebateContinuationState(null);
    currentAgentsRef.current = { agent1: config.agent1, agent2: config.agent2 };
    setProgress({
      fillPercent: totalTurns ? (completedTurns / totalTurns) * 100 : 0,
      label: `${completedTurns} / ${totalTurns}`,
      savedDebateId: isContinuation ? savedDebateIdRef.current : null,
    });

    if (!isContinuation) {
      savedDebateIdRef.current = null;
      setDebateTranscript([
        { id: createId("topic"), type: "topic", topic: config.topic },
      ]);
      resetNotesPanel(config.topic);
    } else {
      setDebateTranscript((current) =>
        current.filter(
          (entry) => entry.type !== "analysis" && entry.type !== "divider",
        ),
      );
      if (continuationSnapshot?.live_notes) {
        setLiveNotes(continuationSnapshot.live_notes);
        setLastLiveNotesTurn(completedTurns);
      }
    }

    setDebateActive(true);
    abortControllerRef.current = new AbortController();

    const shouldReuseCurrentDebateId =
      !isContinuation &&
      Boolean(savedDebateIdRef.current) &&
      debateTranscript.length <= 1;
    const payload =
      isContinuation && continuationSnapshot
        ? {
            ...config,
            history1: continuationSnapshot.history1 ?? [],
            history2: continuationSnapshot.history2 ?? [],
            transcript: continuationSnapshot.transcript ?? [],
            live_notes: continuationSnapshot.live_notes ?? null,
            continuation_of: savedDebateIdRef.current,
            ...(compactDebateSidebar ? { setup: compactDebateSidebar } : {}),
          }
        : {
            ...config,
            ...(shouldReuseCurrentDebateId
              ? { debate_id: savedDebateIdRef.current }
              : {}),
            ...(compactDebateSidebar ? { setup: compactDebateSidebar } : {}),
          };

    try {
      const response = await fetch(buildApiPath("/api/debate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) {
            continue;
          }

          try {
            onDebateEvent(JSON.parse(line.slice(6)) as Record<string, unknown>);
          } catch {
            // ignore malformed SSE payloads to match legacy behavior
          }
        }
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        const message =
          error instanceof Error ? error.message : "Nieznany błąd";
        addDebateError(message);
      }
    } finally {
      setDebateActive(false);
      abortControllerRef.current = null;
    }
  }

  function stopDebate() {
    abortControllerRef.current?.abort();
  }

  function continueDebate() {
    if (!debateContinuationState || debateActive) {
      return;
    }

    void startDebate({ continuation: true });
  }

  useEffect(() => {
    if (
      !autoStartDebate ||
      autoStartTriggeredRef.current ||
      mode !== "debate" ||
      debateActive ||
      debateTranscript.length > 0
    ) {
      return;
    }

    autoStartTriggeredRef.current = true;
    void startDebate();
  }, [autoStartDebate, debateActive, debateTranscript.length, mode]);

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        {lockMode ? null : (
          <div className={styles.modeSwitch}>
            <button
              type="button"
              className={`${styles.modeButton} ${mode === "chat" ? styles.modeButtonActive : ""}`}
              onClick={() => handleModeChange("chat")}
            >
              💬 Chat
            </button>
            <button
              type="button"
              className={`${styles.modeButton} ${mode === "debate" ? styles.modeButtonActive : ""}`}
              onClick={() => handleModeChange("debate")}
            >
              ⚔ Debata
            </button>
          </div>
        )}

        <div className={styles.logo}>
          POD-EXP
          <small className={styles.logoSmall}>Eksperyment epistemiczny</small>
        </div>

        {isCompactDebateSidebar || isDebateLanding ? null : (
          <>
            <a
              className={styles.archiveLink}
              href={buildAppPath("/debates")}
              target="_blank"
              rel="noreferrer"
            >
              🗂 Archiwum debat
            </a>
            <a
              className={styles.archiveLink}
              href={buildAppPath("/federation")}
              target="_blank"
              rel="noreferrer"
            >
              🏛 Federacja
            </a>
            <a
              className={styles.archiveLink}
              href={buildAppPath("/editorial")}
              target="_blank"
              rel="noreferrer"
            >
              ✍ Moduł redakcyjny
            </a>
            <a
              className={styles.archiveLink}
              href={buildAppPath("/editorials")}
              target="_blank"
              rel="noreferrer"
            >
              📝 Lista editoriali
            </a>
          </>
        )}

        {mode === "chat" ? (
          <div className={styles.sidebarSection}>
            <ChatConfigPanel
              agents={agents}
              models={models}
              settings={chatSettings}
              showThinking={showChatThinking}
              onChange={handleChatSettingsChange}
              onNewChat={resetWorkspace}
            />
          </div>
        ) : isDebateLanding ? (
          <div className={styles.compactSidebar}>
            <a
              className={styles.primaryNavLink}
              href={buildAppPath("/newDebate")}
            >
              + Nowa debata
            </a>
            <section className={styles.compactCard}>
              <div className={styles.compactHeading}>Debaty</div>
              <div className={styles.compactTextBlock}>
                <span>Nawigacja</span>
                <p>
                  Wybierz zapis z listy po prawej, żeby wejść w podgląd albo
                  kontynuację debaty.
                </p>
              </div>
            </section>
          </div>
        ) : (
          <div className={styles.sidebarSectionCompact}>
            <section className={styles.compactCard}>
              <div className={styles.compactHeading}>Sterowanie</div>
              <label className={styles.compactField}>
                <span>Maks. kroków do kontynuacji</span>
                <input
                  type="number"
                  min={1}
                  max={32}
                  value={debateSettings.max_turns}
                  onChange={(event) =>
                    handleDebateSettingsChange({
                      ...debateSettings,
                      max_turns: Number.parseInt(event.target.value, 10) || 1,
                    })
                  }
                />
              </label>
              <div className={styles.compactActions}>
                <button
                  type="button"
                  className={styles.stopButtonCompact}
                  disabled={!debateActive}
                  onClick={stopDebate}
                >
                  STOP
                </button>
                <button
                  type="button"
                  className={styles.continueButtonCompact}
                  disabled={!debateContinuationState || debateActive}
                  onClick={continueDebate}
                >
                  Continue
                </button>
              </div>
              <div className={styles.compactMetric}>
                <span>Ilość kroków</span>
                <strong>{progress.label}</strong>
              </div>
            </section>
            {isCompactDebateSidebar ? (
              <div className={styles.compactSidebar}>
                <section className={styles.compactCard}>
                  <div className={styles.compactHeading}>Setup</div>
                  <div className={styles.compactMetric}>
                    <span>Agenci</span>
                    <strong>
                      {debateSettings.agent1} vs {debateSettings.agent2}
                    </strong>
                  </div>
                  <div className={styles.compactMetric}>
                    <span>Tryb</span>
                    <strong>
                      {debateSettings.debate_mode_custom.trim() ||
                        debateSettings.debate_mode}
                    </strong>
                  </div>
                  <div className={styles.compactMetric}>
                    <span>Maks. kroków</span>
                    <strong>{debateSettings.max_turns}</strong>
                  </div>
                </section>

                {compactDebateSidebar ? (
                  <section className={styles.compactCard}>
                    <div className={styles.compactHeading}>Wspólne</div>
                    <div className={styles.compactTextBlock}>
                      <span>Publiczny cel</span>
                      <p>{trimPreview(compactDebateSidebar.publicGoal)}</p>
                    </div>
                    <div className={styles.compactTextBlock}>
                      <span>Publiczne dane</span>
                      <p>{trimPreview(compactDebateSidebar.publicDocuments)}</p>
                    </div>
                  </section>
                ) : null}

                {compactDebateSidebar ? (
                  <section className={styles.compactCard}>
                    <div className={styles.compactHeading}>
                      {debateSettings.agent1}
                    </div>
                    <div className={styles.compactTextBlock}>
                      <span>Prywatny cel</span>
                      <p>
                        {trimPreview(compactDebateSidebar.agent1PrivateGoal)}
                      </p>
                    </div>
                    <div className={styles.compactTextBlock}>
                      <span>Prywatne dane</span>
                      <p>
                        {trimPreview(
                          compactDebateSidebar.agent1PrivateDocuments,
                        )}
                      </p>
                    </div>
                  </section>
                ) : null}

                {compactDebateSidebar ? (
                  <section className={styles.compactCard}>
                    <div className={styles.compactHeading}>
                      {debateSettings.agent2}
                    </div>
                    <div className={styles.compactTextBlock}>
                      <span>Prywatny cel</span>
                      <p>
                        {trimPreview(compactDebateSidebar.agent2PrivateGoal)}
                      </p>
                    </div>
                    <div className={styles.compactTextBlock}>
                      <span>Prywatne dane</span>
                      <p>
                        {trimPreview(
                          compactDebateSidebar.agent2PrivateDocuments,
                        )}
                      </p>
                    </div>
                  </section>
                ) : null}
              </div>
            ) : (
              <DebateConfigPanel
                agents={agents}
                models={models}
                settings={debateSettings}
                canContinue={Boolean(debateContinuationState) && !debateActive}
                debateActive={debateActive}
                onChange={handleDebateSettingsChange}
                onStart={() => void startDebate()}
                onContinue={continueDebate}
                onStop={stopDebate}
              />
            )}
          </div>
        )}

        {isCompactDebateSidebar || isDebateLanding ? null : (
          <button
            type="button"
            className={styles.resetButton}
            onClick={resetStoredModelSettings}
          >
            Reset ustawień modeli
          </button>
        )}
      </aside>

      <main className={styles.main}>
        {mode === "debate" && !isDebateLanding ? (
          <div className={styles.progressRow}>
            <div className={styles.progressTrack}>
              <div
                className={styles.progressFill}
                style={{ width: `${progress.fillPercent}%` }}
              />
            </div>
            <div className={styles.progressLabel}>
              <span>{progress.label}</span>
              {progress.savedDebateId ? (
                <a
                  className={styles.savedLink}
                  href={buildAppPath(`/debate/${progress.savedDebateId}`)}
                  target="_blank"
                  rel="noreferrer"
                >
                  🔗 Zobacz zapis
                </a>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className={styles.contentGrid}>
          <section className={styles.transcriptPane}>
            {isDebateLanding ? (
              <div className={`${styles.messages} ${styles.debateListShell}`}>
                <div className={styles.debateListHeader}>
                  <h1 className={styles.debateListTitle}>Moje debaty</h1>
                  <p className={styles.debateListSubtitle}>
                    Lista zapisanych debat. Każdy wpis możesz otworzyć jako
                    podgląd albo wejść do kontynuacji.
                  </p>
                </div>

                {debates.length === 0 ? (
                  <div className={styles.debateEmptyState}>
                    Brak zapisanych debat. Użyj `+ Nowa debata`, żeby uruchomić
                    pierwszą.
                  </div>
                ) : (
                  <div className={styles.debateListCompact}>
                    {debates.map((debate) => (
                      <article
                        key={debate.id}
                        className={styles.debateListItem}
                      >
                        <div className={styles.debateListMetaRow}>
                          <strong>
                            {debate.agent1} vs {debate.agent2}
                          </strong>
                          <span>{formatDebateTimestamp(debate.timestamp)}</span>
                        </div>
                        <div className={styles.debateListTopic}>
                          {debate.topic || "Bez tematu"}
                        </div>
                        <div className={styles.debateListFooter}>
                          <span>{debate.turns} wymian</span>
                          <span>
                            {debate.model1}
                            {debate.model2 !== debate.model1
                              ? ` / ${debate.model2}`
                              : ""}
                          </span>
                        </div>
                        <div className={styles.debateListActions}>
                          <a
                            className={styles.debateListLink}
                            href={buildAppPath(`/debate/${debate.id}`)}
                          >
                            Podgląd
                          </a>
                          <a
                            className={styles.debateListLink}
                            href={buildAppPath(`/debate/${debate.id}`)}
                          >
                            Kontynuacja
                          </a>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div ref={chatMessagesRef} className={styles.messages}>
                {mode === "chat" ? (
                  <ChatTranscript messages={chatTranscript} busy={chatBusy} />
                ) : (
                  <DebateTranscript entries={debateTranscript} />
                )}
              </div>
            )}

            {mode === "chat" ? (
              <ChatInput
                value={chatInput}
                busy={chatBusy}
                textareaRef={chatInputRef}
                onChange={(value) => {
                  setChatInput(value);
                  window.requestAnimationFrame(resizeInput);
                }}
                onSend={() => void sendChatMessage()}
                onResize={resizeInput}
              />
            ) : null}
          </section>

          <aside
            className={`${styles.notesPane} ${mode === "debate" && !isDebateLanding ? styles.notesPaneActive : ""}`}
          >
            <LiveNotesPanel
              subtitle={notesSubtitle}
              liveNotes={liveNotes}
              lastTurn={lastLiveNotesTurn}
            />
          </aside>
        </div>
      </main>
    </div>
  );
}
