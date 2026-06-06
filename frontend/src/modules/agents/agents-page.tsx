import { useMemo, useState } from "react";
import { buildAppPath } from "../../bootstrap/backend-config";
import type { AgentSummary } from "../../lib/types/bootstrap";
import { AgentQuiz } from "./agent-quiz";
import styles from "./agents-page.module.scss";

type AgentsPageProps = {
  agents: AgentSummary[];
};

const PALETTE = [
  "#7c6af7",
  "#3db98c",
  "#e0b840",
  "#e07060",
  "#60a8e0",
  "#c060e0",
  "#e09040",
  "#60c0a8",
];

function agentColor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) & 0xffff;
  return PALETTE[hash % PALETTE.length];
}

function AgentCard({ agent }: { agent: AgentSummary }) {
  const [expanded, setExpanded] = useState(false);
  const color = agentColor(agent.name);

  return (
    <div
      className={`${styles.card} ${expanded ? styles.cardExpanded : ""}`}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className={styles.cardHead}>
        <span
          className={styles.shortTag}
          style={{ color, borderColor: color, background: `${color}18` }}
        >
          {agent.short_name}
        </span>
        <span className={styles.designation}>{agent.designation}</span>
      </div>
      {agent.federation_description && (
        <div className={styles.federationDesc}>
          {agent.federation_description}
        </div>
      )}
      {agent.temperament.length > 0 && (
        <div className={styles.temperament}>
          {agent.temperament.slice(0, 6).map((t) => (
            <span key={t} className={styles.tempTag}>
              {t}
            </span>
          ))}
        </div>
      )}
      {expanded && agent.narrative_identity && (
        <div className={styles.narrative}>{agent.narrative_identity}</div>
      )}
    </div>
  );
}

export function AgentsPage({ agents: initial }: AgentsPageProps) {
  const [agents, setAgents] = useState<AgentSummary[]>(initial);
  const [query, setQuery] = useState("");
  const [showQuiz, setShowQuiz] = useState(false);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return agents;
    return agents.filter(
      (a) =>
        a.designation.toLowerCase().includes(q) ||
        a.short_name.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        a.federation_description.toLowerCase().includes(q) ||
        a.temperament.some((t) => t.toLowerCase().includes(q)),
    );
  }, [agents, query]);

  function handleCreated(agent: AgentSummary) {
    setAgents((prev) => [agent, ...prev]);
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.logo}>POD-EXP</div>
        <div className={styles.subtitle}>Agenci epistemiczni</div>
        <div className={styles.headerRight}>
          <button
            type="button"
            className={styles.addBtn}
            onClick={() => setShowQuiz(true)}
          >
            + Nowy agent
          </button>
          <a href={buildAppPath("/")} className={styles.backLink}>
            ← Powrót
          </a>
        </div>
      </header>

      <main className={styles.content}>
        <div className={styles.searchRow}>
          <input
            className={styles.searchInput}
            placeholder="Szukaj agenta..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className={styles.count}>
            {filtered.length} / {agents.length} agentów
          </span>
        </div>

        <div className={styles.grid}>
          {filtered.map((agent) => (
            <AgentCard key={agent.name} agent={agent} />
          ))}
        </div>
      </main>

      {showQuiz && (
        <AgentQuiz
          onClose={() => setShowQuiz(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
