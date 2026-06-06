import { useMemo } from "react";
import { buildAppPath } from "../../bootstrap/backend-config";
import { LiveNotesPanel } from "../home/debate/live-notes-panel";
import type { LiveNotes } from "../home/shared/home-types";
import { FederationTranscript } from "./federation-transcript";
import type { FederationEntry } from "./federation-transcript";
import type { FederationViewRecord } from "../../lib/types/bootstrap";
import styles from "./federation-view-page.module.scss";

type FederationViewPageProps = {
  record: FederationViewRecord;
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

function formatTimestamp(ts: string) {
  const date = ts.slice(0, 10);
  const time = ts.length > 15 ? ts.slice(11, 16) : "";
  return `${date}${time ? `  ${time} UTC` : ""}`;
}

export function FederationViewPage({ record }: FederationViewPageProps) {
  const { topic, timestamp, agents, model, transcript, live_notes, summary, total_steps, id } = record;

  const { entries, agentColorMap } = useMemo(() => {
    const colorMap = new Map<string, number>();
    let counter = 0;
    const result: FederationEntry[] = [];

    for (const turn of transcript) {
      if (!colorMap.has(turn.agent)) {
        colorMap.set(turn.agent, counter++);
      }
      const colorIndex = colorMap.get(turn.agent)!;
      result.push({
        id: `t-${result.length}`,
        type: "turn",
        agent: turn.agent,
        shortName: turn.short_name || turn.agent,
        content: turn.content,
        done: true,
        colorIndex,
      });
    }

    if (summary) {
      result.push({
        id: "summary-0",
        type: "summary",
        content: summary,
        done: true,
      });
    }

    return { entries: result, agentColorMap: colorMap };
  }, [transcript, summary]);

  const agentColors = useMemo(() => {
    const colors: string[] = [];
    agentColorMap.forEach((idx) => {
      colors[idx] = AGENT_COLORS[idx % AGENT_COLORS.length];
    });
    return colors;
  }, [agentColorMap]);

  const liveNotes = live_notes as LiveNotes | null;
  const lastTurn = transcript.length > 0 ? transcript.length : null;

  const runAgainHref = buildAppPath(`/federation?topic=${encodeURIComponent(topic)}`);

  return (
    <div className={styles.shell}>
      <div className={styles.topbar}>
        <div className={styles.topbarLeft}>
          <span className={styles.badge}>🏛 FEDERACJA</span>
          <span className={styles.topicText}>„{topic}"</span>
        </div>
        <div className={styles.topbarRight}>
          <span className={styles.meta}>{formatTimestamp(timestamp)}</span>
          <span className={styles.meta}>🤖 {model}</span>
          <span className={styles.meta}>💬 {total_steps} kroków</span>
          <a href={buildAppPath("/debates")} className={styles.archiveLink}>
            ← Archiwum
          </a>
          <a href={runAgainHref} className={styles.runAgainBtn}>
            ▶ Uruchom ponownie
          </a>
        </div>
      </div>

      {agents.length > 0 && (
        <div className={styles.agentPills}>
          {agents.map((a, i) => (
            <span
              key={a}
              className={styles.agentPill}
              style={{ color: AGENT_COLORS[i % AGENT_COLORS.length], borderColor: AGENT_COLORS[i % AGENT_COLORS.length] }}
            >
              {a}
            </span>
          ))}
        </div>
      )}

      <div className={styles.body}>
        <div className={styles.feed}>
          <FederationTranscript entries={entries} agentColors={agentColors} />
        </div>
        {liveNotes && (
          <div className={styles.notesPanel}>
            <LiveNotesPanel
              liveNotes={liveNotes}
              lastTurn={lastTurn}
              subtitle={topic}
            />
          </div>
        )}
      </div>
    </div>
  );
}
