import { MarkdownContent } from "../../components/markdown/markdown-content";
import { buildAppPath } from "../../bootstrap/backend-config";
import { AnalysisCard } from "../analysis-common/analysis-card";
import type { DebateRecord, DebateTranscriptEntry } from "../../lib/types/bootstrap";
import styles from "./debate-view-page.module.scss";

type DebateViewPageProps = {
  debate: DebateRecord;
};

function formatUtcDate(timestamp: string) {
  return timestamp ? timestamp.slice(0, 10) || "—" : "—";
}

function formatUtcTime(timestamp: string) {
  return timestamp.length > 15 ? `${timestamp.slice(11, 16)} UTC` : "";
}

function slotForEntry(entry: DebateTranscriptEntry, agent1: string) {
  return entry.agent === agent1 ? "s1" : "s2";
}

function renderThinking(text?: string) {
  if (!text?.trim()) {
    return null;
  }

  return (
    <details className="think">
      <summary>🧠 myśli agenta</summary>
      <div className="think-body">{text}</div>
    </details>
  );
}

export function DebateViewPage({ debate }: DebateViewPageProps) {
  const hasDebate = Boolean(debate.id);
  const exchangeCount = debate.transcript.length;

  return (
    <section className={styles.page}>
      {!hasDebate ? (
        <div className={styles.emptyState}>Brak danych debaty w payloadzie startowym.</div>
      ) : (
        <>
          <header className={styles.header}>
            <div className={styles.logo}>POD-EXP</div>
            <div className={styles.agents}>
              <span className="agent-pill a1">{debate.agent1}</span>
              <span className="vs">VS</span>
              <span className="agent-pill a2">{debate.agent2}</span>
            </div>
            <div className={styles.topic}>„{debate.topic || ""}"</div>
            <a href={buildAppPath("/debates")} className={styles.backLink}>
              ← Archiwum
            </a>
          </header>

          <div className={styles.metaBar}>
            <span>
              📅 <b>{formatUtcDate(debate.timestamp)}</b> {formatUtcTime(debate.timestamp)}
            </span>
            <span>
              💬 <b>{exchangeCount}</b> wymian
            </span>
            <span>
              🤖 A1: <b>{debate.model1 || "—"}</b>
              {debate.thinking_effort1 ? ` · thinking: ${debate.thinking_effort1}` : ""}
            </span>
            <span>
              🤖 A2: <b>{debate.model2 || "—"}</b>
              {debate.thinking_effort2 ? ` · thinking: ${debate.thinking_effort2}` : ""}
            </span>
          </div>

          <div className={styles.messages}>
            {debate.transcript.map((entry, index) => {
              const slot = slotForEntry(entry, debate.agent1);

              return (
                <article key={`${entry.agent}-${index}`} className={`dmsg ${slot}`}>
                  <div className="dmsg-hdr">
                    <span className={`agent-tag ${slot}`}>{entry.agent}</span>
                    <span className="turn-num">
                      {index + 1} / {exchangeCount}
                    </span>
                  </div>
                  {renderThinking(entry.thinking)}
                  <div className="dmsg-bubble">
                    <MarkdownContent content={entry.content || ""} />
                  </div>
                </article>
              );
            })}

            {debate.analysis || debate.analysis_json ? (
              <>
                <div className="adivider">
                  <span>ANALIZATOR</span>
                </div>
                <article className="dmsg analyzer">
                  <div className="dmsg-hdr">
                    <span className="agent-tag atag">🔬 ANALIZATOR</span>
                  </div>
                  {renderThinking(debate.analysis_thinking)}
                  {debate.analysis_json ? (
                    <AnalysisCard data={debate.analysis_json} agent1={debate.agent1} agent2={debate.agent2} />
                  ) : (
                    <div className="dmsg-bubble">
                      <MarkdownContent content={debate.analysis || ""} />
                    </div>
                  )}
                </article>
              </>
            ) : null}

            {debate.summary ? (
              <>
                <div className="adivider">
                  <span>SUMMARISER</span>
                </div>
                <article className="dmsg analyzer">
                  <div className="dmsg-hdr">
                    <span className="agent-tag atag">🧩 SUMMARISER</span>
                  </div>
                  {renderThinking(debate.summary_thinking)}
                  <div className="dmsg-bubble">
                    <MarkdownContent content={debate.summary} />
                  </div>
                </article>
              </>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}