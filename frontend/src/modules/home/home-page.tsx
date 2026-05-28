import { useEffect, useMemo, useRef, useState } from "react";
import type { ModelCatalog } from "../../lib/types/bootstrap";
import { ChatConfigPanel } from "./chat/chat-config-panel";
import { ChatInput } from "./chat/chat-input";
import { ChatTranscript } from "./chat/chat-transcript";
import { buildApiPath, buildAppPath } from "../../bootstrap/backend-config";
import { DebateConfigPanel } from "./debate/debate-config-panel";
import { DebateTranscript } from "./debate/debate-transcript";
import { LiveNotesPanel } from "./debate/live-notes-panel";
import { THINKING_MODELS, getDefaultChatSettings, getDefaultDebateSettings, normalizeChatSettings, normalizeDebateSettings } from "./shared/home-constants";
import styles from "./shared/home-screen.module.scss";
import { clearStoredSettings, loadChatSettings, loadDebateSettings, saveChatSettings, saveDebateSettings } from "./shared/home-storage";
import type { ChatSettings, ChatTranscriptEntry, DebateAnalysisEntry, DebateContinuationState, DebateProgress, DebateSettings, DebateTranscriptEntry, HomeMode, LiveNotes } from "./shared/home-types";

type HomePageProps = {
  agents: string[];
  models: ModelCatalog;
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

export function HomePage({ agents, models }: HomePageProps) {
  const defaultChatSettings = useMemo(() => getDefaultChatSettings(agents, models), [agents, models]);
  const defaultDebateSettings = useMemo(() => getDefaultDebateSettings(agents, models), [agents, models]);
  const [mode, setMode] = useState<HomeMode>("chat");
  const [chatSettings, setChatSettings] = useState<ChatSettings>(() => loadChatSettings(agents, models));
  const [debateSettings, setDebateSettings] = useState<DebateSettings>(() => loadDebateSettings(agents, models));
  const [conversation, setConversation] = useState<ChatApiMessage[]>([]);
  const [chatTranscript, setChatTranscript] = useState<ChatTranscriptEntry[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [debateTranscript, setDebateTranscript] = useState<DebateTranscriptEntry[]>([]);
  const [debateActive, setDebateActive] = useState(false);
  const [progress, setProgress] = useState<DebateProgress>(() => createDefaultProgress(defaultDebateSettings.max_turns));
  const [liveNotes, setLiveNotes] = useState<LiveNotes | null>(null);
  const [notesSubtitle, setNotesSubtitle] = useState("Po prawej pojawi się skrót sporu");
  const [lastLiveNotesTurn, setLastLiveNotesTurn] = useState<number | null>(null);
  const [debateContinuationState, setDebateContinuationState] = useState<DebateContinuationState | null>(null);
  const [lastDebateConfig, setLastDebateConfig] = useState<DebateSettings | null>(null);
  const chatMessagesRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentTurnIdRef = useRef<string | null>(null);
  const currentAnalysisIdRef = useRef<string | null>(null);
  const currentSummaryIdRef = useRef<string | null>(null);
  const currentAgentsRef = useRef({ agent1: "", agent2: "" });
  const savedDebateIdRef = useRef<string | null>(null);

  const showChatThinking = THINKING_MODELS.has(chatSettings.model);

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

    const normalizedDebate = normalizeDebateSettings(debateSettings, agents, models);
    if (JSON.stringify(normalizedDebate) !== JSON.stringify(debateSettings)) {
      setDebateSettings(normalizedDebate);
    }
  }, [agents, models]);

  useEffect(() => {
    chatMessagesRef.current?.scrollTo({ top: chatMessagesRef.current.scrollHeight });
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
    setNotesSubtitle(topic ? "Aktualizowane po każdej turze debaty" : "Po prawej pojawi się skrót sporu");
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
    const nextConversation = [...conversation, { role: "user", content: text } satisfies ChatApiMessage];

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
      const data = (await response.json()) as { error?: string; content?: string };

      if (data.error) {
        setChatTranscript((current) => [...current, { id: createId("chat-error"), role: "error", content: data.error ?? "Nieznany błąd" }]);
      } else if (typeof data.content === "string") {
        const assistantContent = data.content;
        setConversation((current) => [...current, { role: "assistant", content: assistantContent }]);
        setChatTranscript((current) => [...current, { id: createId("chat-assistant"), role: "assistant", content: assistantContent }]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nieznany błąd połączenia";
      setChatTranscript((current) => [...current, { id: createId("chat-error"), role: "error", content: `Błąd połączenia: ${message}` }]);
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

  function updateDebateEntry(id: string | null, updater: (entry: DebateTranscriptEntry) => DebateTranscriptEntry) {
    if (!id) {
      return;
    }

    setDebateTranscript((current) => current.map((entry) => (entry.id === id ? updater(entry) : entry)));
  }

  function addDebateError(message: string) {
    setDebateTranscript((current) => [...current, { id: createId("debate-error"), type: "error", message }]);
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
          fillPercent: turnEntry.total ? ((turnEntry.turn - 1) / turnEntry.total) * 100 : 0,
          label: `${turnEntry.turn} / ${turnEntry.total}`,
          savedDebateId: savedDebateIdRef.current,
        });
        break;
      }
      case "thinking": {
        updateDebateEntry(currentTurnIdRef.current, (entry) =>
          entry.type === "turn" ? { ...entry, thinking: `${entry.thinking}${String(event.delta ?? "")}` } : entry,
        );
        break;
      }
      case "text": {
        updateDebateEntry(currentTurnIdRef.current, (entry) =>
          entry.type === "turn" ? { ...entry, content: `${entry.content}${String(event.delta ?? "")}` } : entry,
        );
        break;
      }
      case "turn_end": {
        updateDebateEntry(currentTurnIdRef.current, (entry) =>
          entry.type === "turn" ? { ...entry, renderContentAsMarkdown: true } : entry,
        );
        setProgress({
          fillPercent: Number(event.total) ? (Number(event.turn) / Number(event.total)) * 100 : 0,
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
        setNotesSubtitle(`Notatki pominięte po turze ${String(event.turn ?? "?")}: ${String(event.message ?? "")}`);
        break;
      }
      case "analysis_start": {
        const dividerId = createId("analysis-divider");
        const analysisId = createId("analysis");
        currentAnalysisIdRef.current = analysisId;
        setDebateTranscript((current) => [
          ...current,
          { id: dividerId, type: "divider", label: "ANALIZATOR" },
          { id: analysisId, type: "analysis", variant: "analyzer", title: "🔬 ANALIZATOR", content: "", renderContentAsMarkdown: false },
        ]);
        break;
      }
      case "analysis_text": {
        updateDebateEntry(currentAnalysisIdRef.current, (entry) =>
          entry.type === "analysis" ? { ...entry, content: `${entry.content}${String(event.delta ?? "")}` } : entry,
        );
        break;
      }
      case "analysis_json": {
        updateDebateEntry(currentAnalysisIdRef.current, (entry) =>
          entry.type === "analysis" ? ({ ...entry, jsonData: event.data } satisfies DebateAnalysisEntry) : entry,
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
          { id: summaryId, type: "analysis", variant: "summariser", title: "🧩 SUMMARISER", content: "", renderContentAsMarkdown: false },
        ]);
        break;
      }
      case "summary_text": {
        updateDebateEntry(currentSummaryIdRef.current, (entry) =>
          entry.type === "analysis" ? { ...entry, content: `${entry.content}${String(event.delta ?? "")}` } : entry,
        );
        break;
      }
      case "summary_done": {
        updateDebateEntry(currentSummaryIdRef.current, (entry) =>
          entry.type === "analysis" ? { ...entry, renderContentAsMarkdown: true } : entry,
        );
        currentSummaryIdRef.current = null;
        setProgress({ fillPercent: 100, label: "Zakończono ✓", savedDebateId: savedDebateIdRef.current });
        break;
      }
      case "summary_error": {
        addDebateError(`Summariser: ${String(event.message ?? "Nieznany błąd")}`);
        break;
      }
      case "saved": {
        const savedId = String(event.id ?? "");
        const nextConfig = normalizeDebateSettings((event.config ?? null) as Partial<DebateSettings> | null, agents, models);
        savedDebateIdRef.current = savedId;
        setDebateContinuationState((event.continuation ?? null) as DebateContinuationState | null);
        setLastDebateConfig(nextConfig);
        setDebateSettings(nextConfig);
        setProgress({ fillPercent: 100, label: "Zapisano ✓", savedDebateId: savedId });
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
    const baseConfig = isContinuation && lastDebateConfig ? { ...lastDebateConfig, max_turns: nextTurns } : debateSettings;
    const config = normalizeDebateSettings(baseConfig, agents, models);
    const completedTurns = isContinuation ? debateContinuationState?.turns_completed ?? debateContinuationState?.transcript?.length ?? 0 : 0;
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
      setDebateTranscript([{ id: createId("topic"), type: "topic", topic: config.topic }]);
      resetNotesPanel(config.topic);
    } else {
      setDebateTranscript((current) => current.filter((entry) => entry.type !== "analysis" && entry.type !== "divider"));
      if (continuationSnapshot?.live_notes) {
        setLiveNotes(continuationSnapshot.live_notes);
        setLastLiveNotesTurn(completedTurns);
      }
    }

    setDebateActive(true);
    abortControllerRef.current = new AbortController();

    const payload = isContinuation && continuationSnapshot
      ? {
          ...config,
          history1: continuationSnapshot.history1 ?? [],
          history2: continuationSnapshot.history2 ?? [],
          transcript: continuationSnapshot.transcript ?? [],
          live_notes: continuationSnapshot.live_notes ?? null,
          continuation_of: savedDebateIdRef.current,
        }
      : config;

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
        const message = error instanceof Error ? error.message : "Nieznany błąd";
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

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.modeSwitch}>
          <button type="button" className={`${styles.modeButton} ${mode === "chat" ? styles.modeButtonActive : ""}`} onClick={() => handleModeChange("chat")}>
            💬 Chat
          </button>
          <button type="button" className={`${styles.modeButton} ${mode === "debate" ? styles.modeButtonActive : ""}`} onClick={() => handleModeChange("debate")}>
            ⚔ Debata
          </button>
        </div>

        <div className={styles.logo}>
          POD-EXP
          <small className={styles.logoSmall}>Eksperyment epistemiczny</small>
        </div>

        <a className={styles.archiveLink} href={buildAppPath("/debates")} target="_blank" rel="noreferrer">
          🗂 Archiwum debat
        </a>

        {mode === "chat" ? (
          <div className={styles.sidebarSection}>
            <ChatConfigPanel agents={agents} models={models} settings={chatSettings} showThinking={showChatThinking} onChange={handleChatSettingsChange} onNewChat={resetWorkspace} />
          </div>
        ) : (
          <div className={styles.sidebarSectionCompact}>
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
          </div>
        )}

        <button type="button" className={styles.resetButton} onClick={resetStoredModelSettings}>
          Reset ustawień modeli
        </button>
      </aside>

      <main className={styles.main}>
        {mode === "debate" ? (
          <div className={styles.progressRow}>
            <div className={styles.progressTrack}>
              <div className={styles.progressFill} style={{ width: `${progress.fillPercent}%` }} />
            </div>
            <div className={styles.progressLabel}>
              <span>{progress.label}</span>
              {progress.savedDebateId ? (
                <a className={styles.savedLink} href={buildAppPath(`/debates/${progress.savedDebateId}`)} target="_blank" rel="noreferrer">
                  🔗 Zobacz zapis
                </a>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className={styles.contentGrid}>
          <section className={styles.transcriptPane}>
            <div ref={chatMessagesRef} className={styles.messages}>
              {mode === "chat" ? <ChatTranscript messages={chatTranscript} busy={chatBusy} /> : <DebateTranscript entries={debateTranscript} />}
            </div>

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

          <aside className={`${styles.notesPane} ${mode === "debate" ? styles.notesPaneActive : ""}`}>
            <LiveNotesPanel subtitle={notesSubtitle} liveNotes={liveNotes} lastTurn={lastLiveNotesTurn} />
          </aside>
        </div>
      </main>
    </div>
  );
}