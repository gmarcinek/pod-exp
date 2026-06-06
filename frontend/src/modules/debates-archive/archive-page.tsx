import type { DebateListItem } from "../../lib/types/bootstrap";
import { buildAppPath } from "../../bootstrap/backend-config";
import styles from "./archive-page.module.scss";

type ArchivePageProps = {
  debates: DebateListItem[];
};

function formatTimestamp(timestamp: string) {
  const date = timestamp.slice(0, 10);
  const time = timestamp.length > 15 ? timestamp.slice(11, 16) : "";

  return `${date} \u00a0 ${time} UTC`;
}

const FEDERATION_COLORS = [
  "#7c6af7",
  "#3db98c",
  "#e0b840",
  "#e07060",
  "#60a8e0",
  "#c060e0",
  "#e09040",
];

function DebateCard({ debate }: { debate: DebateListItem }) {
  const isFederation = debate.type === "federation";
  const href = isFederation
    ? buildAppPath(`/federation/${debate.id}`)
    : buildAppPath(`/debate/${debate.id}`);

  if (isFederation) {
    const agents = debate.agents ?? [];
    return (
      <a
        href={href}
        className={`${styles.debateCard} ${styles.federationCard}`}
      >
        <div className={styles.cardTop}>
          <div className={styles.federationWrap}>
            <span className={styles.federationBadge}>🏛 FEDERACJA</span>
            <div className={styles.federationAgents}>
              {agents.map((a, i) => (
                <span
                  key={a}
                  className={styles.federationPill}
                  style={{
                    color: FEDERATION_COLORS[i % FEDERATION_COLORS.length],
                    borderColor:
                      FEDERATION_COLORS[i % FEDERATION_COLORS.length],
                  }}
                >
                  {a}
                </span>
              ))}
            </div>
          </div>
          <div className={styles.cardMeta}>
            {formatTimestamp(debate.timestamp)}
          </div>
        </div>
        <div className={styles.cardTopic}>„{debate.topic}"</div>
        {debate.snippet && (
          <div className={styles.cardSnippet}>{debate.snippet}</div>
        )}
        <div className={styles.cardFooter}>
          <span>💬 {debate.turns} kroków</span>
          {debate.model1 && <span>🤖 {debate.model1}</span>}
        </div>
      </a>
    );
  }

  return (
    <a href={href} className={styles.debateCard}>
      <div className={styles.cardTop}>
        <div className={styles.vsWrap}>
          <span className={`${styles.agentPill} ${styles.agentPillA1}`}>
            {debate.agent1}
          </span>
          <span className={styles.vs}>VS</span>
          <span className={`${styles.agentPill} ${styles.agentPillA2}`}>
            {debate.agent2}
          </span>
        </div>
        <div className={styles.cardMeta}>
          {formatTimestamp(debate.timestamp)}
        </div>
      </div>
      <div className={styles.cardTopic}>„{debate.topic}"</div>
      {debate.snippet && (
        <div className={styles.cardSnippet}>{debate.snippet}</div>
      )}
      <div className={styles.cardFooter}>
        <span>💬 {debate.turns} wymian</span>
        <span>🤖 {debate.model1}</span>
        {debate.model2 !== debate.model1 ? (
          <span>🤖 {debate.model2}</span>
        ) : null}
      </div>
    </a>
  );
}

export function ArchivePage({ debates }: ArchivePageProps) {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.logo}>POD-EXP</div>
        <div className={styles.subtitle}>Archiwum debat epistemicznych</div>
        <a href={buildAppPath("/")} className={styles.backLink}>
          ← Powrót do chatu
        </a>
      </header>

      <main className={styles.content}>
        <h1 className={styles.title}>Odbyte debaty</h1>
        <p className={styles.pageSubtitle}>
          Kliknij debatę, żeby odtworzyć sesję i kontynuować ją z zapisanych
          ustawień.
        </p>

        {debates.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>🗂</div>
            <p>
              Brak zapisanych debat.
              <br />
              Uruchom pierwszą debatę w trybie ⚔ Debata.
            </p>
          </div>
        ) : (
          <div className={styles.debateList}>
            {debates.map((debate) => (
              <DebateCard key={debate.id} debate={debate} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
