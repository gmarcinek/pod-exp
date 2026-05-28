import { MarkdownContent } from "../../../components/markdown/markdown-content";
import { AnalysisCard } from "../../analysis-common/analysis-card";
import type { DebateTranscriptEntry, DebateTurnEntry } from "../shared/home-types";
import styles from "./debate-transcript.module.scss";

type DebateTranscriptProps = {
  entries: DebateTranscriptEntry[];
};

export function DebateTranscript({ entries }: DebateTranscriptProps) {
  const agent1 = entries.find((candidate): candidate is DebateTurnEntry => candidate.type === "turn" && candidate.slot === "s1")?.agent ?? "Agent 1";
  const agent2 = entries.find((candidate): candidate is DebateTurnEntry => candidate.type === "turn" && candidate.slot === "s2")?.agent ?? "Agent 2";

  if (entries.length === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyTitle}>POD-EXP</div>
        <div className={styles.emptySubtitle}>Wybierz agenta i zadaj pytanie</div>
      </div>
    );
  }

  return (
    <>
      {entries.map((entry) => {
        if (entry.type === "topic") {
          return (
            <div key={entry.id} className={styles.topicCard}>
              <div className={styles.topicKicker}>Temat debaty</div>
              <div className={styles.topicText}>{entry.topic}</div>
            </div>
          );
        }

        if (entry.type === "divider") {
          return (
            <div key={entry.id} className={styles.divider}>
              <span>{entry.label}</span>
            </div>
          );
        }

        if (entry.type === "error") {
          return (
            <div key={entry.id} className={`${styles.chatError} ${styles.entryFullWidth}`}>
              <div className={styles.chatErrorRole}>Błąd</div>
              <div className={styles.chatErrorBubble}>
                <p>{entry.message}</p>
              </div>
            </div>
          );
        }

        if (entry.type === "analysis") {
          return (
            <div key={entry.id} className={`${styles.debateEntry} ${styles.analyzer}`}>
              <div className={styles.entryHeader}>
                <span className={`${styles.agentTag} ${styles.agentTagAnalyzer}`}>{entry.title}</span>
              </div>
              <div className={`${styles.entryBubble} ${styles.analysisBubble}`}>
                {entry.jsonData ? (
                  <AnalysisCard data={entry.jsonData} agent1={agent1} agent2={agent2} />
                ) : (
                  <MarkdownContent content={entry.content} />
                )}
              </div>
            </div>
          );
        }

        return (
          <div key={entry.id} className={`${styles.debateEntry} ${entry.slot === "s1" ? styles.slotOne : styles.slotTwo}`}>
            <div className={styles.entryHeader}>
              <span className={`${styles.agentTag} ${entry.slot === "s1" ? styles.agentTagOne : styles.agentTagTwo}`}>{entry.agent}</span>
              <span className={styles.turnNumber}>
                {entry.turn} / {entry.total}
              </span>
            </div>

            {entry.thinking ? (
              <details className={styles.thinkingDetails} open>
                <summary>🧠 myśli...</summary>
                <div className={styles.thinkingBody}>{entry.thinking}</div>
              </details>
            ) : null}

            <div className={styles.entryBubble}>
              <MarkdownContent content={entry.content} />
            </div>
          </div>
        );
      })}
    </>
  );
}