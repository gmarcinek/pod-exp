import { useRef, useState } from "react";
import { buildApiPath, buildAppPath } from "../../bootstrap/backend-config";
import { LiveNotesPanel } from "../home/debate/live-notes-panel";
import type { LiveNotes } from "../home/shared/home-types";
import { FederationTranscript } from "./federation-transcript";
import type { FederationEntry } from "./federation-transcript";
import styles from "./federation-page.module.scss";

type FederationPageProps = {
  agents: string[];
  models: string[];
};

type ActiveAgent = {
  name: string;
  shortName: string;
  colorIndex: number;
};

const AGENT_COLORS = [
  "#7c6af7",
  "#3db98c",
  "#e0b840",
  "#e07060",
  "#60a8e0",
  "#c060e0",
  "#e09040",
];

let _nextId = 0;
function uid(prefix: string) {
  return `${prefix}-${++_nextId}`;
}

export function FederationPage({
  agents: _agents,
  models,
}: FederationPageProps) {
  const [topic, setTopic] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("topic") ?? "";
  });
  const [data, setData] = useState("");
  const [model, setModel] = useState(() => models[0] ?? "gpt-5.4");
  const [maxSteps, setMaxSteps] = useState(20);

  const [phase, setPhase] = useState<"setup" | "session">("setup");
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(20);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [liveNotes, setLiveNotes] = useState<LiveNotes | null>(null);
  const [lastNotesTurn, setLastNotesTurn] = useState<number | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [entries, setEntries] = useState<FederationEntry[]>([]);
  const [activeAgents, setActiveAgents] = useState<ActiveAgent[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const feedRef = useRef<HTMLDivElement | null>(null);
  const colorCounterRef = useRef(0);
  const agentColorMapRef = useRef<Map<string, number>>(new Map());

  function scrollFeed() {
    requestAnimationFrame(() => {
      if (feedRef.current)
        feedRef.current.scrollTop = feedRef.current.scrollHeight;
    });
  }

  function addEntry(entry: FederationEntry) {
    setEntries((prev) => [...prev, entry]);
    scrollFeed();
  }

  function updateLastTurn(
    agentName: string,
    updater: (e: FederationEntry) => FederationEntry,
  ) {
    setEntries((prev) => {
      const idx = [...prev]
        .map((e, i) => ({ e, i }))
        .reverse()
        .find(
          ({ e }) => e.type === "turn" && e.agent === agentName && !e.done,
        )?.i;
      if (idx === undefined) return prev;
      const next = [...prev];
      next[idx] = updater(next[idx]);
      return next;
    });
    scrollFeed();
  }

  function updateLastMarshal(updater: (e: FederationEntry) => FederationEntry) {
    setEntries((prev) => {
      const idx = [...prev]
        .map((e, i) => ({ e, i }))
        .reverse()
        .find(({ e }) => e.type === "marshal" && !e.done)?.i;
      if (idx === undefined) return prev;
      const next = [...prev];
      next[idx] = updater(next[idx]);
      return next;
    });
    scrollFeed();
  }

  function stop() {
    abortRef.current?.abort();
  }

  async function start() {
    if (running || !topic.trim()) return;
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    colorCounterRef.current = 0;
    agentColorMapRef.current = new Map();
    setRunning(true);
    setStep(0);
    setTotalSteps(maxSteps);
    setEntries([]);
    setActiveAgents([]);
    setLiveNotes(null);
    setLastNotesTurn(null);
    setSavedId(null);
    setPhase("session");

    try {
      const response = await fetch(buildApiPath("/api/federation"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          data,
          model,
          max_steps: maxSteps,
          max_tokens: maxTokens,
        }),
        signal: abortRef.current.signal,
      });
      if (!response.ok || !response.body)
        throw new Error(`HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            handleEvent(JSON.parse(line.slice(6)) as Record<string, unknown>);
          } catch {
            /* ignore */
          }
        }
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        addEntry({
          id: uid("err"),
          type: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      }
    } finally {
      setRunning(false);
    }
  }

  function getOrAssignColor(agentName: string, shortName: string): number {
    const existing = agentColorMapRef.current.get(agentName);
    if (existing !== undefined) return existing;
    const colorIndex = colorCounterRef.current++;
    agentColorMapRef.current.set(agentName, colorIndex);
    setActiveAgents((prev) =>
      prev.find((a) => a.name === agentName)
        ? prev
        : [...prev, { name: agentName, shortName, colorIndex }],
    );
    return colorIndex;
  }

  function handleEvent(event: Record<string, unknown>) {
    const type = String(event.type ?? "");
    const evStep = Number(event.step ?? 0);

    switch (type) {
      case "marshal_assessment":
        setStep(evStep);
        addEntry({
          id: uid("assessment"),
          type: "assessment",
          text: String(event.text ?? ""),
        });
        break;
      case "marshal_text_start":
        addEntry({
          id: uid("marshal"),
          type: "marshal",
          content: "",
          done: false,
        });
        break;
      case "marshal_text":
        updateLastMarshal((e) =>
          e.type === "marshal"
            ? { ...e, content: e.content + String(event.delta ?? "") }
            : e,
        );
        break;
      case "marshal_text_end":
        updateLastMarshal((e) =>
          e.type === "marshal" ? { ...e, done: true } : e,
        );
        break;
      case "agent_joined": {
        const agentName = String(event.agent ?? "");
        const shortName = String(event.short_name ?? agentName);
        const colorIndex = getOrAssignColor(agentName, shortName);
        addEntry({
          id: uid("joined"),
          type: "agent_joined",
          agent: agentName,
          shortName,
          designation: String(event.designation ?? ""),
          colorIndex,
        });
        break;
      }
      case "turn_start": {
        const agentName = String(event.agent ?? "");
        const shortName = String(event.short_name ?? agentName);
        setStep(evStep);
        const colorIndex = getOrAssignColor(agentName, shortName);
        addEntry({
          id: uid("turn"),
          type: "turn",
          agent: agentName,
          shortName,
          content: "",
          done: false,
          colorIndex,
        });
        break;
      }
      case "text":
        updateLastTurn(String(event.agent ?? ""), (e) =>
          e.type === "turn"
            ? { ...e, content: e.content + String(event.delta ?? "") }
            : e,
        );
        break;
      case "turn_end":
        setEntries((prev) => {
          const agentName = String(event.agent ?? "");
          const idx = [...prev]
            .map((e, i) => ({ e, i }))
            .reverse()
            .find(
              ({ e }) => e.type === "turn" && e.agent === agentName && !e.done,
            )?.i;
          if (idx === undefined) return prev;
          const next = [...prev];
          next[idx] = { ...next[idx], done: true } as FederationEntry;
          return next;
        });
        break;
      case "live_notes":
        setLiveNotes(event.data as LiveNotes);
        setLastNotesTurn(Number(event.turn ?? null));
        break;
      case "summary_start":
        addEntry({
          id: uid("summary"),
          type: "summary",
          content: "",
          done: false,
        });
        break;
      case "summary_text":
        setEntries((prev) => {
          const idx = [...prev]
            .map((e, i) => ({ e, i }))
            .reverse()
            .find(({ e }) => e.type === "summary" && !e.done)?.i;
          if (idx === undefined) return prev;
          const next = [...prev];
          const cur = next[idx];
          if (cur.type === "summary")
            next[idx] = {
              ...cur,
              content: cur.content + String(event.delta ?? ""),
            };
          return next;
        });
        scrollFeed();
        break;
      case "summary_done":
        setEntries((prev) => {
          const idx = [...prev]
            .map((e, i) => ({ e, i }))
            .reverse()
            .find(({ e }) => e.type === "summary" && !e.done)?.i;
          if (idx === undefined) return prev;
          const next = [...prev];
          next[idx] = { ...next[idx], done: true } as FederationEntry;
          return next;
        });
        break;
      case "federation_end":
        if (event.id) setSavedId(String(event.id));
        break;
      case "federation_start":
        if (event.total_steps) setTotalSteps(Number(event.total_steps));
        break;
      case "error":
        addEntry({
          id: uid("err"),
          type: "error",
          message: String(event.message ?? "Błąd"),
        });
        break;
      default:
        break;
    }
  }

  // ── Setup phase ───────────────────────────────────────────────────────────
  if (phase === "setup") {
    return (
      <div className={styles.setupShell}>
        <div className={styles.setupCard}>
          <div className={styles.setupBrand}>
            <span className={styles.setupLogo}>POD-EXP</span>
            <span className={styles.setupTitle}>Federacja epistemiczna</span>
            <p className={styles.setupSubtitle}>
              Marszałek dobiera agentów i prowadzi debatę, routując po stanie
              rozmowy — nie po etykietach.
            </p>
          </div>

          <div className={styles.setupForm}>
            <label className={styles.setupField}>
              <span className={styles.setupLabel}>Temat *</span>
              <textarea
                className={styles.setupTextarea}
                rows={2}
                placeholder="np. Czy wolna wola jest możliwa w deterministycznym wszechświecie?"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </label>

            <label className={styles.setupField}>
              <span className={styles.setupLabel}>
                Dane / kontekst (opcjonalnie)
              </span>
              <textarea
                className={styles.setupTextarea}
                rows={3}
                placeholder="Dodatkowe dokumenty, cytaty, badania..."
                value={data}
                onChange={(e) => setData(e.target.value)}
              />
            </label>

            <div className={styles.setupRow}>
              <label className={styles.setupFieldInline}>
                <span className={styles.setupLabel}>Model agentów</span>
                <select
                  className={styles.setupSelect}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.setupFieldInline}>
                <span className={styles.setupLabel}>Max tokens</span>
                <input
                  type="number"
                  className={styles.setupInput}
                  min={512}
                  max={32768}
                  step={512}
                  value={maxTokens}
                  onChange={(e) =>
                    setMaxTokens(Number.parseInt(e.target.value, 10) || 4096)
                  }
                />
              </label>

              <label className={styles.setupFieldInline}>
                <span className={styles.setupLabel}>Tury</span>
                <input
                  type="number"
                  className={styles.setupInput}
                  min={4}
                  max={40}
                  value={maxSteps}
                  onChange={(e) =>
                    setMaxSteps(Number.parseInt(e.target.value, 10) || 20)
                  }
                />
              </label>
            </div>
          </div>

          <button
            type="button"
            className={styles.setupStartBtn}
            disabled={!topic.trim()}
            onClick={() => void start()}
          >
            Uruchom federację →
          </button>

          <a className={styles.setupBackLink} href={buildAppPath("/")}>
            ← Wróć do głównej
          </a>
        </div>
      </div>
    );
  }

  // ── Session phase ─────────────────────────────────────────────────────────
  return (
    <div className={styles.sessionShell}>
      <header className={styles.topBar}>
        <div className={styles.topBarLeft}>
          <span className={styles.topBarLogo}>🏛</span>
          <span className={styles.topBarTopic} title={topic}>
            {topic}
          </span>
        </div>

        <div className={styles.topBarAgents}>
          {activeAgents.map((a) => (
            <span
              key={a.name}
              className={styles.topBarAgent}
              style={{
                color: AGENT_COLORS[a.colorIndex % AGENT_COLORS.length],
              }}
            >
              {a.shortName}
            </span>
          ))}
        </div>

        <div className={styles.topBarRight}>
          {running && (
            <span className={styles.topBarStep}>
              krok {step} / {totalSteps}
            </span>
          )}
          {!running && step > 0 && (
            <span className={styles.topBarDone}>✓ {step} kroków</span>
          )}
          {!running && step === 0 && (
            <span className={styles.topBarDone}>✓ zakończono</span>
          )}
          {running && (
            <button type="button" className={styles.stopBtn} onClick={stop}>
              STOP
            </button>
          )}
          {!running && savedId && (
            <a href={buildAppPath("/debates")} className={styles.archiveBtn}>
              ✓ Zapisano → Archiwum
            </a>
          )}
          {!running && (
            <button
              type="button"
              className={styles.newBtn}
              onClick={() => {
                setPhase("setup");
                setEntries([]);
                setActiveAgents([]);
                setLiveNotes(null);
                setLastNotesTurn(null);
                setStep(0);
                setSavedId(null);
              }}
            >
              Nowa sesja
            </button>
          )}
        </div>
      </header>

      <div className={styles.sessionBody}>
        <div className={styles.feed} ref={feedRef}>
          <FederationTranscript entries={entries} agentColors={AGENT_COLORS} />
          {running && <div className={styles.runningIndicator} />}
          {running && (
            <button type="button" className={styles.stopFloat} onClick={stop}>
              ■ STOP
            </button>
          )}
        </div>
        {liveNotes && (
          <aside className={styles.notesPanel}>
            <LiveNotesPanel
              subtitle={topic}
              liveNotes={liveNotes}
              lastTurn={lastNotesTurn}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
