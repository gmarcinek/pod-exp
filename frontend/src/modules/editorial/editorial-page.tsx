import { useEffect, useMemo, useRef, useState } from "react";
import { buildApiPath, buildAppPath } from "../../bootstrap/backend-config";
import type { ModelCatalog } from "../../lib/types/bootstrap";
import {
  receiveEditorialStatus,
  type EditorialStatusEvent,
} from "./editorial-status-receiver";
import styles from "./editorial-page.module.scss";

type EditorialPageProps = {
  models: ModelCatalog;
};

type EditorialEntry = {
  id: string;
  cycle: number;
  role: string;
  label: string;
  content: string;
};

type WorkflowLayer = {
  id: string;
  label: string;
  reason: string;
  status: "planned" | "working" | "verified";
};

type AdaptivePlanStep = {
  id: string;
  label: string;
  purpose: string;
  conclusion: string;
  status: "planned" | "working" | "completed";
};

type WorkflowSection = {
  id: string;
  paragraphStart: number;
  paragraphEnd: number;
  lineStart: number;
  lineEnd: number;
  readWindowLines: number;
  readingMode: string;
  readingPurpose: string;
  readingReason: string;
  readingTools: string[];
  handoffGoal: string;
  readingAudit: ReadingAudit | null;
  status: "planned" | "working" | "done";
};

type ReadingRange = {
  lineStart: number;
  lineEnd: number;
  reason?: string;
};

type ReadingFinding = {
  marker: string;
  text: string;
};

type ReadingAudit = {
  status: string;
  readRange: ReadingRange | null;
  skippedWithinRange: ReadingRange[];
  unreadAfter: ReadingRange[];
  findings: ReadingFinding[];
  openQuestions: string[];
};

type DocumentHandoff = {
  summary: string;
  continuity: string[];
  voice: string[];
  openQuestions: string[];
};

type WorkflowTask = {
  id: string;
  reason: string;
  status: "proposed" | "accepted" | "rejected";
};

type StreamEvent = Record<string, unknown>;

const MAX_TOKEN_OPTIONS = [
  { value: "2048", label: "2k" },
  { value: "4096", label: "4k" },
  { value: "8192", label: "8k" },
  { value: "12288", label: "12k" },
  { value: "32768", label: "32k" },
  { value: "max", label: "max" },
] as const;

let nextId = 0;

function uid() {
  nextId += 1;
  return `editorial-${nextId}`;
}

function parsePayload(content: string): Record<string, unknown> | null {
  try {
    const payload = JSON.parse(content) as unknown;
    return payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function parseReadingRange(value: unknown): ReadingRange | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const range = value as Record<string, unknown>;
  return typeof range.line_start === "number" &&
    typeof range.line_end === "number"
    ? {
        lineStart: range.line_start,
        lineEnd: range.line_end,
        reason: typeof range.reason === "string" ? range.reason : undefined,
      }
    : null;
}

function parseReadingAudit(value: unknown): ReadingAudit | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const audit = value as Record<string, unknown>;
  const ranges = (key: string) =>
    Array.isArray(audit[key])
      ? audit[key].flatMap((range) => {
          const parsed = parseReadingRange(range);
          return parsed ? [parsed] : [];
        })
      : [];
  const findings = Array.isArray(audit.findings)
    ? audit.findings.flatMap((finding) => {
        if (!finding || typeof finding !== "object" || Array.isArray(finding)) {
          return [];
        }
        const item = finding as Record<string, unknown>;
        return typeof item.marker === "string" && typeof item.text === "string"
          ? [{ marker: item.marker, text: item.text }]
          : [];
      })
    : [];
  return {
    status: typeof audit.status === "string" ? audit.status : "nieznany",
    readRange: parseReadingRange(audit.read_range),
    skippedWithinRange: ranges("skipped_within_range"),
    unreadAfter: ranges("unread_after"),
    findings,
    openQuestions: Array.isArray(audit.open_questions)
      ? audit.open_questions.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
  };
}

function statusLabel(
  status:
    | "planned"
    | "working"
    | "verified"
    | "done"
    | "completed"
    | "proposed"
    | "accepted"
    | "rejected",
) {
  const labels = {
    planned: "zaplanowano",
    working: "w toku",
    verified: "zweryfikowano",
    done: "ukończono",
    completed: "ukończono",
    proposed: "do decyzji",
    accepted: "zatwierdzono",
    rejected: "odrzucono",
  };
  return labels[status];
}

export function EditorialPage({ models: initialModels }: EditorialPageProps) {
  const [title, setTitle] = useState("Pakiet redakcyjny");
  const [brief, setBrief] = useState("");
  const [text, setText] = useState("");
  const [provider, setProvider] = useState("openai");
  const [models, setModels] = useState<ModelCatalog>(initialModels);
  const [model, setModel] = useState(() => initialModels.openai?.[0] ?? "");
  const [maxCycles, setMaxCycles] = useState(1);
  const [maxTokens, setMaxTokens] = useState("4096");
  const [cleanModelSignatures, setCleanModelSignatures] = useState(false);
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<EditorialEntry[]>([]);
  const [layers, setLayers] = useState<WorkflowLayer[]>([]);
  const [adaptivePlan, setAdaptivePlan] = useState<AdaptivePlanStep[]>([]);
  const [sections, setSections] = useState<WorkflowSection[]>([]);
  const [documentHandoff, setDocumentHandoff] =
    useState<DocumentHandoff | null>(null);
  const [toolStatuses, setToolStatuses] = useState<EditorialStatusEvent[]>([]);
  const [tasks, setTasks] = useState<WorkflowTask[]>([]);
  const [effects, setEffects] = useState<string[]>([]);
  const [showEffects, setShowEffects] = useState(false);
  const [currentCycle, setCurrentCycle] = useState(0);
  const [totalCycles, setTotalCycles] = useState(0);
  const [finalText, setFinalText] = useState("");
  const [savedId, setSavedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const providerModels = useMemo(
    () => models[provider] ?? [],
    [models, provider],
  );

  useEffect(() => {
    fetch(buildApiPath("/api/bootstrap/editorial"))
      .then((response) => response.json())
      .then((payload) => {
        const catalog = payload?.initialData?.models;
        if (catalog && typeof catalog === "object" && !Array.isArray(catalog)) {
          setModels(catalog as ModelCatalog);
        }
      })
      .catch(() => {
        /* use bootstrap fallback */
      });
  }, []);

  useEffect(() => {
    if (!providerModels.includes(model)) {
      setModel(providerModels[0] ?? "");
    }
  }, [model, providerModels]);

  function resetSession() {
    setEntries([]);
    setLayers([]);
    setAdaptivePlan([]);
    setSections([]);
    setDocumentHandoff(null);
    setToolStatuses([]);
    setTasks([]);
    setEffects([]);
    setShowEffects(false);
    setCurrentCycle(0);
    setTotalCycles(0);
    setFinalText("");
    setSavedId(null);
    setError(null);
  }

  function stop() {
    abortRef.current?.abort();
  }

  async function start() {
    if (running || !text.trim()) {
      return;
    }

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    resetSession();
    setRunning(true);

    try {
      const response = await fetch(buildApiPath("/api/editorial"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          title,
          brief,
          text,
          provider,
          model,
          max_cycles: maxCycles,
          max_tokens: maxTokens,
          clean_model_signatures: cleanModelSignatures,
        }),
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
            handleEvent(JSON.parse(line.slice(6)) as StreamEvent);
          } catch {
            /* ignore malformed event */
          }
        }
      }
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      setRunning(false);
    }
  }

  function handleEvent(event: StreamEvent) {
    const type = typeof event.type === "string" ? event.type : "";
    const statusEvent = receiveEditorialStatus(event);

    if (statusEvent) {
      setToolStatuses((previous) => [...previous, statusEvent].slice(-40));
      return;
    }

    if (type === "editorial_start") {
      setSavedId(typeof event.id === "string" ? event.id : null);
      setTotalCycles(
        typeof event.total_cycles === "number" ? event.total_cycles : 0,
      );
      return;
    }

    if (type === "editorial_adaptive_plan") {
      const rawPlan = event.adaptive_plan;
      const rawSteps =
        rawPlan && typeof rawPlan === "object" && !Array.isArray(rawPlan)
          ? (rawPlan as Record<string, unknown>).steps
          : [];
      setAdaptivePlan(
        Array.isArray(rawSteps)
          ? rawSteps.flatMap((step) => {
              if (!step || typeof step !== "object" || Array.isArray(step)) {
                return [];
              }
              const item = step as Record<string, unknown>;
              const id = typeof item.id === "string" ? item.id : "";
              const status = item.status;
              return id &&
                ["planned", "working", "completed"].includes(String(status))
                ? [
                    {
                      id,
                      label: typeof item.label === "string" ? item.label : id,
                      purpose:
                        typeof item.purpose === "string" ? item.purpose : "",
                      conclusion:
                        typeof item.conclusion === "string"
                          ? item.conclusion
                          : "",
                      status: status as AdaptivePlanStep["status"],
                    },
                  ]
                : [];
            })
          : [],
      );
      return;
    }

    if (type === "editorial_workflow_plan") {
      const plan = event.plan;
      const planRecord =
        plan && typeof plan === "object" && !Array.isArray(plan)
          ? (plan as Record<string, unknown>)
          : null;
      const rawLayers = planRecord?.layers ?? [];
      const rawSections = Array.isArray(event.sections) ? event.sections : [];
      const rawHandoff = planRecord?.document_handoff;
      if (
        rawHandoff &&
        typeof rawHandoff === "object" &&
        !Array.isArray(rawHandoff)
      ) {
        const handoff = rawHandoff as Record<string, unknown>;
        const notes = (key: string) =>
          Array.isArray(handoff[key])
            ? handoff[key].filter(
                (item): item is string => typeof item === "string",
              )
            : [];
        setDocumentHandoff({
          summary: typeof handoff.summary === "string" ? handoff.summary : "",
          continuity: notes("continuity"),
          voice: notes("voice"),
          openQuestions: notes("open_questions"),
        });
      }
      setLayers(
        Array.isArray(rawLayers)
          ? rawLayers.flatMap((layer) => {
              if (!layer || typeof layer !== "object" || Array.isArray(layer)) {
                return [];
              }
              const item = layer as Record<string, unknown>;
              const id = typeof item.id === "string" ? item.id : "";
              return id
                ? [
                    {
                      id,
                      label: typeof item.label === "string" ? item.label : id,
                      reason:
                        typeof item.reason === "string" ? item.reason : "",
                      status: "planned" as const,
                    },
                  ]
                : [];
            })
          : [],
      );
      setSections(
        rawSections.flatMap((section) => {
          if (
            !section ||
            typeof section !== "object" ||
            Array.isArray(section)
          ) {
            return [];
          }
          const item = section as Record<string, unknown>;
          const id = typeof item.id === "string" ? item.id : "";
          return id
            ? [
                {
                  id,
                  paragraphStart:
                    typeof item.paragraph_start === "number"
                      ? item.paragraph_start
                      : 0,
                  paragraphEnd:
                    typeof item.paragraph_end === "number"
                      ? item.paragraph_end
                      : 0,
                  lineStart:
                    typeof item.line_start === "number" ? item.line_start : 0,
                  lineEnd:
                    typeof item.line_end === "number" ? item.line_end : 0,
                  readWindowLines:
                    typeof item.read_window_lines === "number"
                      ? item.read_window_lines
                      : 0,
                  readingMode:
                    typeof item.reading_mode === "string"
                      ? item.reading_mode
                      : "",
                  readingPurpose:
                    typeof item.reading_purpose === "string"
                      ? item.reading_purpose
                      : "",
                  readingReason:
                    typeof item.reading_reason === "string"
                      ? item.reading_reason
                      : "",
                  readingTools: Array.isArray(item.reading_tools)
                    ? item.reading_tools.filter(
                        (tool): tool is string => typeof tool === "string",
                      )
                    : [],
                  handoffGoal:
                    typeof item.handoff_goal === "string"
                      ? item.handoff_goal
                      : "",
                  readingAudit: parseReadingAudit(item.reading_audit),
                  status: "planned" as const,
                },
              ]
            : [];
        }),
      );
      return;
    }

    if (type === "editorial_role_output") {
      const cycle = typeof event.cycle === "number" ? event.cycle : 0;
      setCurrentCycle(cycle);
      setEntries((prev) => [
        ...prev,
        {
          id: uid(),
          cycle,
          role: typeof event.role === "string" ? event.role : "",
          label: typeof event.label === "string" ? event.label : "Rola",
          content: typeof event.content === "string" ? event.content : "",
        },
      ]);
      if (
        cycle > 0 &&
        ["marker", "coherence_guard", "critic"].includes(String(event.role))
      ) {
        setLayers((prev) =>
          prev.map((layer) => ({ ...layer, status: "working" })),
        );
        setSections((prev) =>
          prev.map((section) => ({ ...section, status: "working" })),
        );
      }
      const content = typeof event.content === "string" ? event.content : "";
      const payload = parsePayload(content);
      if (event.role === "patch_rewriter" && Array.isArray(payload?.patches)) {
        setTasks(
          payload.patches.flatMap((patch) => {
            if (!patch || typeof patch !== "object" || Array.isArray(patch)) {
              return [];
            }
            const item = patch as Record<string, unknown>;
            return typeof item.id === "string"
              ? [
                  {
                    id: item.id,
                    reason: typeof item.reason === "string" ? item.reason : "",
                    status: "proposed" as const,
                  },
                ]
              : [];
          }),
        );
      }
      if (event.role === "patch_validator" && payload) {
        const accepted = new Set(
          Array.isArray(payload.accepted)
            ? payload.accepted.flatMap((patch) =>
                patch &&
                typeof patch === "object" &&
                !Array.isArray(patch) &&
                typeof (patch as Record<string, unknown>).id === "string"
                  ? [(patch as Record<string, unknown>).id as string]
                  : [],
              )
            : [],
        );
        const rejected = new Set(
          Array.isArray(payload.rejected)
            ? payload.rejected.flatMap((patch) =>
                patch &&
                typeof patch === "object" &&
                !Array.isArray(patch) &&
                typeof (patch as Record<string, unknown>).id === "string"
                  ? [(patch as Record<string, unknown>).id as string]
                  : [],
              )
            : [],
        );
        setTasks((prev) =>
          prev.map((task) => ({
            ...task,
            status: accepted.has(task.id)
              ? "accepted"
              : rejected.has(task.id)
                ? "rejected"
                : task.status,
          })),
        );
        setLayers((prev) =>
          prev.map((layer) => ({ ...layer, status: "verified" })),
        );
        setSections((prev) =>
          prev.map((section) => ({ ...section, status: "done" })),
        );
        setEffects([
          `Zatwierdzono: ${accepted.size}`,
          `Odrzucono: ${rejected.size}`,
        ]);
      }
      return;
    }

    if (type === "editorial_draft") {
      setCurrentCycle(
        typeof event.cycle === "number" ? event.cycle : currentCycle,
      );
      setFinalText(typeof event.text === "string" ? event.text : "");
      return;
    }

    if (type === "editorial_end") {
      setSavedId(typeof event.id === "string" ? event.id : savedId);
      setFinalText(
        typeof event.final_text === "string" ? event.final_text : "",
      );
      return;
    }

    if (type === "error") {
      setError(
        typeof event.message === "string" ? event.message : "Nieznany błąd.",
      );
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <section className={styles.hero}>
          <p className={styles.eyebrow}>Author x Editorial Loop</p>
          <h1 className={styles.title}>
            Moduł redakcyjny dla tekstów i iteracji wydawniczych
          </h1>
          <p className={styles.copy}>
            Najpierw tekst przechodzi diagnozę, potem rewriter proponuje
            wyłącznie lokalne podmiany cytatów. Walidator zatwierdza je albo
            odrzuca względem briefu i oryginału, a syntezator stosuje tylko
            zaakceptowane patche. Nie powstaje nowa wersja tekstu pisana od zera
            przez model.
          </p>
        </section>

        <div className={styles.layout}>
          <section className={styles.panel}>
            <div className={styles.form}>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="editorial-title">
                  Nazwa sesji
                </label>
                <input
                  id="editorial-title"
                  className={styles.input}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="editorial-brief">
                  Dodatkowe wytyczne autora
                </label>
                <textarea
                  id="editorial-brief"
                  className={styles.textarea}
                  value={brief}
                  onChange={(event) => setBrief(event.target.value)}
                  placeholder="Opcjonalnie: cel tego przejścia, ograniczenie lub pytanie do autora. Zasady zachowania głosu i faktów są już wbudowane w workflow."
                />
              </div>

              <div className={styles.row}>
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="editorial-provider">
                    Provider
                  </label>
                  <select
                    id="editorial-provider"
                    className={styles.select}
                    value={provider}
                    onChange={(event) => setProvider(event.target.value)}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="ollama">Ollama</option>
                  </select>
                </div>

                <div className={styles.field}>
                  <label className={styles.label} htmlFor="editorial-model">
                    Model
                  </label>
                  <select
                    id="editorial-model"
                    className={styles.select}
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                  >
                    {providerModels.map((entry) => (
                      <option key={entry} value={entry}>
                        {entry}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className={styles.row}>
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="editorial-cycles">
                    Liczba iteracji
                  </label>
                  <input
                    id="editorial-cycles"
                    className={styles.input}
                    type="number"
                    min={1}
                    max={5}
                    value={maxCycles}
                    onChange={(event) =>
                      setMaxCycles(Number(event.target.value) || 1)
                    }
                  />
                </div>

                <div className={styles.field}>
                  <label className={styles.label} htmlFor="editorial-tokens">
                    Max tokens
                  </label>
                  <select
                    id="editorial-tokens"
                    className={styles.select}
                    value={maxTokens}
                    onChange={(event) => setMaxTokens(event.target.value)}
                  >
                    {MAX_TOKEN_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <label className={styles.checkboxField}>
                <input
                  checked={cleanModelSignatures}
                  className={styles.checkbox}
                  onChange={(event) =>
                    setCleanModelSignatures(event.target.checked)
                  }
                  type="checkbox"
                />
                <span>
                  Czyść niechciane sygnatury modelowe
                  <small>
                    Pozwala usuwać gotowe formuły i sztuczne domknięcia, nadal
                    wyłącznie przez zatwierdzone patche lokalne.
                  </small>
                </span>
              </label>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="editorial-text">
                  Tekst źródłowy
                </label>
                <textarea
                  id="editorial-text"
                  className={`${styles.textarea} ${styles.textInput}`}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Wklej roboczy tekst, esej, rozdział albo wybrany fragment do obróbki."
                />
              </div>

              <div className={styles.actions}>
                <button
                  className={styles.button}
                  disabled={running || !text.trim()}
                  onClick={() => void start()}
                >
                  {running ? "Pętla pracuje..." : "Uruchom cykl"}
                </button>
                <button
                  className={styles.ghostButton}
                  disabled={!running}
                  onClick={stop}
                >
                  Zatrzymaj
                </button>
                <a
                  className={styles.ghostButton}
                  href={buildAppPath("/editorials")}
                >
                  Lista editoriali
                </a>
                <a className={styles.ghostButton} href={buildAppPath("/")}>
                  Powrót
                </a>
              </div>
            </div>
          </section>

          <section className={styles.panel}>
            <div className={styles.workspace}>
              <div className={styles.statusBar}>
                <div className={styles.statusPill}>
                  Iteracja: {currentCycle} / {totalCycles || maxCycles}
                </div>
                <div className={styles.statusPill}>Provider: {provider}</div>
                <div className={styles.statusPill}>
                  Model: {model || "brak"}
                </div>
                {savedId ? (
                  <div className={styles.statusPill}>Zapis: {savedId}</div>
                ) : null}
              </div>

              {error ? <p className={styles.error}>{error}</p> : null}

              {savedId && finalText ? (
                <div className={styles.resultActions}>
                  <span className={styles.entryLabel}>Wyniki</span>
                  <div className={styles.exportActions}>
                    <a
                      className={styles.ghostButton}
                      href={buildApiPath(
                        `/api/editorials/${savedId}/export/html`,
                      )}
                    >
                      Pobierz HTML
                    </a>
                    <a
                      className={styles.ghostButton}
                      href={buildApiPath(
                        `/api/editorials/${savedId}/export/docx`,
                      )}
                    >
                      Pobierz Word
                    </a>
                  </div>
                </div>
              ) : null}

              <section className={styles.workflowBoard}>
                <div className={styles.boardHeader}>
                  <span className={styles.entryLabel}>Przebieg redakcji</span>
                  <span>
                    {layers.length ? "plan adaptacyjny" : "oczekiwanie na plan"}
                  </span>
                </div>

                <div className={styles.workflowGroup}>
                  <h2>Plan adaptacyjny</h2>
                  <ul className={styles.workflowList} aria-live="polite">
                    {adaptivePlan.map((step, index) => (
                      <li key={step.id} className={styles.workflowItem}>
                        <div>
                          <strong>
                            {index + 1}. {step.label}
                          </strong>
                          {step.purpose ? (
                            <small>Cel: {step.purpose}</small>
                          ) : null}
                          {step.conclusion ? (
                            <small>Wniosek: {step.conclusion}</small>
                          ) : null}
                        </div>
                        <span
                          aria-label={statusLabel(step.status)}
                          className={`${styles.planCheckbox} ${step.status === "completed" ? styles.planCheckboxCompleted : ""} ${step.status === "working" ? styles.pendingStatus : ""}`}
                        >
                          {step.status === "completed" ? "✅" : "⬜"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className={styles.workflowGroup}>
                  <h2>Warstwy</h2>
                  <ul className={styles.workflowList}>
                    {layers.map((layer) => (
                      <li key={layer.id} className={styles.workflowItem}>
                        <div>
                          <strong>{layer.label}</strong>
                          {layer.reason ? <small>{layer.reason}</small> : null}
                        </div>
                        <span
                          className={`${styles[`status${layer.status[0].toUpperCase()}${layer.status.slice(1)}`]} ${layer.status === "planned" ? styles.pendingStatus : ""}`}
                        >
                          {statusLabel(layer.status)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className={styles.workflowGroup}>
                  <h2>Status narzędzi</h2>
                  <ul
                    className={`${styles.effectList} ${styles.toolStatusList}`}
                    aria-live="polite"
                  >
                    {toolStatuses.map((status, index) => (
                      <li key={`${status.timestamp}-${status.phase}-${index}`}>
                        <strong>{status.message}</strong>
                        {status.purpose ? (
                          <small>{status.purpose}</small>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className={styles.workflowGroup}>
                  <h2>Scenariusze</h2>
                  <ul className={styles.workflowList}>
                    {sections.map((section) => (
                      <li key={section.id} className={styles.workflowItem}>
                        <div>
                          <strong>{section.id}</strong>
                          <small>
                            Linie L{section.lineStart}-L{section.lineEnd};
                            akapity {section.paragraphStart}-
                            {section.paragraphEnd}
                          </small>
                          <small>
                            Czytanie: {section.readingMode || "nieokreślone"} (
                            {section.readWindowLines} linii) przez{" "}
                            {section.readingTools.join(", ") ||
                              "brak narzędzia"}
                          </small>
                          {section.readingPurpose ? (
                            <small>Cel: {section.readingPurpose}</small>
                          ) : null}
                          {section.readingReason ? (
                            <small>Powód: {section.readingReason}</small>
                          ) : null}
                          {section.handoffGoal ? (
                            <small>Handoff: {section.handoffGoal}</small>
                          ) : null}
                          {section.readingAudit ? (
                            <small>
                              Status czytania: {section.readingAudit.status};
                              przeczytano{" "}
                              {section.readingAudit.readRange
                                ? `L${section.readingAudit.readRange.lineStart}-L${section.readingAudit.readRange.lineEnd}`
                                : "brak zakresu"}
                              .
                              {section.readingAudit.skippedWithinRange.length
                                ? ` Pominięto w zakresie: ${section.readingAudit.skippedWithinRange.map((range) => `L${range.lineStart}-L${range.lineEnd}`).join(", ")}.`
                                : " W zakresie nie pominięto linii."}
                            </small>
                          ) : null}
                          {section.readingAudit?.unreadAfter.length ? (
                            <small>
                              Poza tym odczytem:{" "}
                              {section.readingAudit.unreadAfter
                                .map(
                                  (range) =>
                                    `L${range.lineStart}-L${range.lineEnd} (${range.reason})`,
                                )
                                .join(" | ")}
                            </small>
                          ) : null}
                          {section.readingAudit?.findings.map((finding) => (
                            <small key={`${finding.marker}-${finding.text}`}>
                              {finding.text} {finding.marker}
                            </small>
                          ))}
                          {section.readingAudit?.openQuestions.map(
                            (question) => (
                              <small key={question}>{question}</small>
                            ),
                          )}
                        </div>
                        <span
                          className={
                            styles[
                              `status${section.status[0].toUpperCase()}${section.status.slice(1)}`
                            ]
                          }
                        >
                          {statusLabel(section.status)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className={styles.workflowGroup}>
                  <h2>Lista wykonawcza</h2>
                  <ul className={styles.workflowList}>
                    {tasks.map((task) => (
                      <li key={task.id} className={styles.workflowItem}>
                        <div>
                          <strong>{task.id}</strong>
                          {task.reason ? <small>{task.reason}</small> : null}
                        </div>
                        <span
                          className={
                            styles[
                              `status${task.status[0].toUpperCase()}${task.status.slice(1)}`
                            ]
                          }
                        >
                          {statusLabel(task.status)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className={styles.workflowGroup}>
                  <h2>Efekty</h2>
                  <ul className={styles.effectList}>
                    {effects.map((effect) => (
                      <li key={effect}>{effect}</li>
                    ))}
                  </ul>
                </div>

                <button
                  className={styles.ghostButton}
                  onClick={() => setShowEffects((visible) => !visible)}
                  type="button"
                >
                  {showEffects ? "Ukryj efekty" : "Pokaż efekty"}
                </button>
              </section>

              {showEffects ? (
                <div className={styles.entries}>
                  <article className={styles.entry}>
                    <div className={styles.entryMeta}>
                      <span className={styles.entryLabel}>Handoff całości</span>
                      <span>kontekst dla kolejnych ról</span>
                    </div>
                    {documentHandoff ? (
                      <div className={styles.handoff}>
                        {documentHandoff.summary ? (
                          <p>{documentHandoff.summary}</p>
                        ) : null}
                        {documentHandoff.continuity.length ? (
                          <small>
                            Ciągłość: {documentHandoff.continuity.join(" | ")}
                          </small>
                        ) : null}
                        {documentHandoff.voice.length ? (
                          <small>
                            Głos: {documentHandoff.voice.join(" | ")}
                          </small>
                        ) : null}
                        {documentHandoff.openQuestions.length ? (
                          <small>
                            Otwarte: {documentHandoff.openQuestions.join(" | ")}
                          </small>
                        ) : null}
                      </div>
                    ) : (
                      <p
                        className={`${styles.emptyState} ${styles.pendingText}`}
                        aria-live="polite"
                      >
                        Rozpoznawanie całości: handoff w przygotowaniu.
                      </p>
                    )}
                  </article>
                  {entries.map((entry) => (
                    <article key={entry.id} className={styles.entry}>
                      <div className={styles.entryMeta}>
                        <span className={styles.entryLabel}>{entry.label}</span>
                        <span>Iteracja {entry.cycle}</span>
                      </div>
                      <pre className={styles.entryContent}>{entry.content}</pre>
                    </article>
                  ))}
                </div>
              ) : null}

              <div className={`${styles.entry} ${styles.finalCard}`}>
                <div className={styles.entryMeta}>
                  <span className={styles.entryLabel}>
                    Aktualna wersja tekstu
                  </span>
                  <span>
                    {finalText ? "po iteracji" : "czeka na uruchomienie"}
                  </span>
                </div>
                <pre className={styles.finalText}>
                  {finalText ||
                    "Tutaj pojawi się wynik po przejściu przez role wydawnicze."}
                </pre>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
