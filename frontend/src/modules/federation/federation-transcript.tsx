import { MarkdownContent } from "../../components/markdown/markdown-content";
import styles from "./federation-transcript.module.scss";

export type FederationAssessmentEntry = {
  id: string;
  type: "assessment";
  text: string;
};

export type FederationMarshalEntry = {
  id: string;
  type: "marshal";
  content: string;
  done: boolean;
};

export type FederationAgentJoinedEntry = {
  id: string;
  type: "agent_joined";
  agent: string;
  shortName: string;
  designation: string;
  colorIndex: number;
};

export type FederationTurnEntry = {
  id: string;
  type: "turn";
  agent: string;
  shortName: string;
  content: string;
  done: boolean;
  colorIndex: number;
};

export type FederationErrorEntry = {
  id: string;
  type: "error";
  message: string;
};

export type FederationSummaryEntry = {
  id: string;
  type: "summary";
  content: string;
  done: boolean;
};

export type FederationEntry =
  | FederationAssessmentEntry
  | FederationMarshalEntry
  | FederationAgentJoinedEntry
  | FederationTurnEntry
  | FederationSummaryEntry
  | FederationErrorEntry;

// Stable color palette for agents
const DEFAULT_COLORS = [
  {
    tag: "#7c6af7",
    border: "rgba(124,106,247,.3)",
    bg: "rgba(124,106,247,.08)",
  },
  { tag: "#3db98c", border: "rgba(61,185,140,.3)", bg: "rgba(61,185,140,.08)" },
  { tag: "#e0b840", border: "rgba(224,184,64,.3)", bg: "rgba(224,184,64,.08)" },
  { tag: "#e07060", border: "rgba(224,112,96,.3)", bg: "rgba(224,112,96,.08)" },
  { tag: "#60a8e0", border: "rgba(96,168,224,.3)", bg: "rgba(96,168,224,.08)" },
  { tag: "#c060e0", border: "rgba(192,96,224,.3)", bg: "rgba(192,96,224,.08)" },
  { tag: "#e09040", border: "rgba(224,144,64,.3)", bg: "rgba(224,144,64,.08)" },
];

function buildColorEntry(hex: string) {
  // parse hex to rgba components for bg/border
  const r = Number.parseInt(hex.slice(1, 3), 16);
  const g = Number.parseInt(hex.slice(3, 5), 16);
  const b = Number.parseInt(hex.slice(5, 7), 16);
  return {
    tag: hex,
    border: `rgba(${r},${g},${b},.3)`,
    bg: `rgba(${r},${g},${b},.08)`,
  };
}

function getColor(colorIndex: number, agentColors?: string[]) {
  if (agentColors) {
    const hex = agentColors[colorIndex % agentColors.length];
    return buildColorEntry(hex);
  }
  return DEFAULT_COLORS[colorIndex % DEFAULT_COLORS.length];
}

type FederationTranscriptProps = {
  entries: FederationEntry[];
  agentColors?: string[];
};

export function FederationTranscript({
  entries,
  agentColors,
}: FederationTranscriptProps) {
  return (
    <div className={styles.root}>
      {entries.map((entry) => {
        if (entry.type === "assessment") {
          return (
            <div key={entry.id} className={styles.assessment}>
              <span className={styles.assessmentIcon}>🎙</span>
              <span className={styles.assessmentText}>{entry.text}</span>
            </div>
          );
        }

        if (entry.type === "marshal") {
          return (
            <div key={entry.id} className={styles.marshal}>
              <div className={styles.marshalHeader}>
                <span className={styles.marshalTag}>MARSZAŁEK</span>
              </div>
              <div className={styles.marshalBubble}>
                {entry.done ? (
                  <MarkdownContent content={entry.content} />
                ) : (
                  <span className={styles.streamingText}>{entry.content}</span>
                )}
              </div>
            </div>
          );
        }

        if (entry.type === "agent_joined") {
          const color = getColor(entry.colorIndex, agentColors);
          return (
            <div key={entry.id} className={styles.agentJoined}>
              <span
                className={styles.agentJoinedTag}
                style={{
                  color: color.tag,
                  borderColor: color.border,
                  background: color.bg,
                }}
              >
                + {entry.shortName}
              </span>
              <span className={styles.agentJoinedLabel}>
                {entry.designation}
              </span>
            </div>
          );
        }

        if (entry.type === "turn") {
          const color = getColor(entry.colorIndex, agentColors);
          return (
            <div key={entry.id} className={styles.turn}>
              <div className={styles.turnHeader}>
                <span
                  className={styles.agentTag}
                  style={{
                    color: color.tag,
                    borderColor: color.border,
                    background: color.bg,
                  }}
                >
                  {entry.shortName}
                </span>
              </div>
              <div
                className={styles.turnBubble}
                style={{ borderColor: color.border }}
              >
                {entry.done ? (
                  <MarkdownContent content={entry.content} />
                ) : (
                  <span className={styles.streamingText}>{entry.content}</span>
                )}
              </div>
            </div>
          );
        }

        if (entry.type === "error") {
          return (
            <div key={entry.id} className={styles.error}>
              <span className={styles.errorIcon}>⚠</span>
              {entry.message}
            </div>
          );
        }

        if (entry.type === "summary") {
          return (
            <div key={entry.id} className={styles.summary}>
              <div className={styles.summaryHeader}>
                <span className={styles.summaryTag}>🧩 PODSUMOWANIE</span>
              </div>
              <div className={styles.summaryBubble}>
                {entry.done ? (
                  <MarkdownContent content={entry.content} />
                ) : (
                  <span className={styles.streamingText}>{entry.content}</span>
                )}
              </div>
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}
