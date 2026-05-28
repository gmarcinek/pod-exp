import { useState } from "react";
import { buildApiPath, buildAppPath } from "../bootstrap/backend-config";
import type { DebateSetupData, NewDebateBootstrapData } from "../lib/types/bootstrap";
import { DEBATE_MODE_OPTIONS, MAX_TOKEN_OPTIONS, getModelsForProvider, normalizeDebateSettings } from "../modules/home/shared/home-constants";
import { loadDebateSettings, saveDebateSettings } from "../modules/home/shared/home-storage";
import type { DebateSettings } from "../modules/home/shared/home-types";
import screenStyles from "../modules/home/shared/home-screen.module.scss";
import styles from "./new-debate-route.module.scss";

type NewDebateRouteProps = {
  data: NewDebateBootstrapData;
};

type AgentCardProps = {
  slot: 1 | 2;
  title: string;
  agent: string;
  provider: DebateSettings["provider1"];
  model: string;
  maxTokens: DebateSettings["max_tokens1"];
  privateGoal: string;
  privateDocuments: string;
  agents: string[];
  availableModels: string[];
  onAgentChange: (agent: string) => void;
  onProviderChange: (provider: DebateSettings["provider1"]) => void;
  onModelChange: (model: string) => void;
  onMaxTokensChange: (maxTokens: DebateSettings["max_tokens1"]) => void;
  onPrivateGoalChange: (value: string) => void;
  onPrivateDocumentsChange: (value: string) => void;
};

function getAgentBadge(name: string) {
  const letters = name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return letters || "AI";
}

function AgentCard({
  slot,
  title,
  agent,
  provider,
  model,
  maxTokens,
  privateGoal,
  privateDocuments,
  agents,
  availableModels,
  onAgentChange,
  onProviderChange,
  onModelChange,
  onMaxTokensChange,
  onPrivateGoalChange,
  onPrivateDocumentsChange,
}: AgentCardProps) {
  return (
    <section className={styles.setupCard}>
      <div className={styles.cardEyebrow}>{title}</div>
      <div className={styles.agentHeader}>
        <div className={styles.agentBadge}>{getAgentBadge(agent)}</div>
        <div className={styles.agentName}>{agent}</div>
      </div>

      <div className={styles.agentForm}>
        <label className={styles.field}>
          <span className={styles.label}>Agent</span>
          <select value={agent} onChange={(event) => onAgentChange(event.target.value)}>
            {agents.map((agentOption) => (
              <option key={agentOption} value={agentOption}>
                {agentOption}
              </option>
            ))}
          </select>
        </label>

        <div className={styles.field}>
          <span className={styles.label}>Provider</span>
          <div className={styles.toggle}>
            <input id={`new-debate-provider-${slot}-openai`} type="radio" name={`new-debate-provider-${slot}`} value="openai" checked={provider === "openai"} onChange={() => onProviderChange("openai")} />
            <label htmlFor={`new-debate-provider-${slot}-openai`}>OpenAI</label>
            <input id={`new-debate-provider-${slot}-anthropic`} type="radio" name={`new-debate-provider-${slot}`} value="anthropic" checked={provider === "anthropic"} onChange={() => onProviderChange("anthropic")} />
            <label htmlFor={`new-debate-provider-${slot}-anthropic`}>Anthropic</label>
          </div>
        </div>

        <div className={styles.fieldRow}>
          <label className={styles.field}>
            <span className={styles.label}>Model</span>
            <select value={model} onChange={(event) => onModelChange(event.target.value)}>
              {availableModels.map((modelOption) => (
                <option key={modelOption} value={modelOption}>
                  {modelOption}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Max tokens</span>
            <select value={maxTokens} onChange={(event) => onMaxTokensChange(event.target.value as DebateSettings["max_tokens1"])}>
              {MAX_TOKEN_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className={styles.field}>
          <span className={styles.label}>Prywatny cel agenta</span>
          <textarea className={styles.textarea} value={privateGoal} onChange={(event) => onPrivateGoalChange(event.target.value)} rows={5} placeholder="Cel prywatny znany tylko temu agentowi na starcie" />
        </label>

        <label className={styles.field}>
          <span className={styles.label}>Prywatne dokumenty agenta</span>
          <textarea className={styles.textarea} value={privateDocuments} onChange={(event) => onPrivateDocumentsChange(event.target.value)} rows={8} placeholder="Dane wejściowe znane tylko temu agentowi na starcie" />
        </label>
      </div>
    </section>
  );
}

function buildPublicTopic(setup: DebateSetupData) {
  const goal = setup.publicGoal.trim();
  const documents = setup.publicDocuments.trim();

  if (goal && documents) {
    return `Cel wspólny:\n${goal}\n\nWspólne dokumenty:\n${documents}`;
  }

  if (goal) {
    return `Cel wspólny:\n${goal}`;
  }

  if (documents) {
    return `Wspólne dokumenty:\n${documents}`;
  }

  return "Przeprowadź debatę zgodnie z wybranym setupem.";
}

export function NewDebateRoute({ data }: NewDebateRouteProps) {
  const [settings, setSettings] = useState<DebateSettings>(() => loadDebateSettings(data.agents, data.models));
  const [sharedGoal, setSharedGoal] = useState("");
  const [sharedDocuments, setSharedDocuments] = useState("");
  const [agent1PrivateGoal, setAgent1PrivateGoal] = useState("");
  const [agent1PrivateDocuments, setAgent1PrivateDocuments] = useState("");
  const [agent2PrivateGoal, setAgent2PrivateGoal] = useState("");
  const [agent2PrivateDocuments, setAgent2PrivateDocuments] = useState("");
  const [startPending, setStartPending] = useState(false);
  const [startError, setStartError] = useState("");

  function updateSettings(nextValue: Partial<DebateSettings>) {
    setSettings((current) => {
      const normalized = normalizeDebateSettings({ ...current, ...nextValue }, data.agents, data.models);
      saveDebateSettings(normalized);
      return normalized;
    });
  }

  function updateProvider(slot: 1 | 2, provider: DebateSettings["provider1"]) {
    const modelKey = slot === 1 ? "model1" : "model2";
    const providerKey = slot === 1 ? "provider1" : "provider2";
    const thinkingKey = slot === 1 ? "thinking_effort1" : "thinking_effort2";
    const availableModels = getModelsForProvider(data.models, provider);

    updateSettings({
      [providerKey]: provider,
      [modelKey]: availableModels[0] ?? "",
      [thinkingKey]: null,
    } as Pick<DebateSettings, typeof providerKey | typeof modelKey | typeof thinkingKey>);
  }

  const leftModels = getModelsForProvider(data.models, settings.provider1);
  const rightModels = getModelsForProvider(data.models, settings.provider2);
  const archiveHref = buildAppPath("/debates");
  const homeHref = buildAppPath("/");

  async function handleStartDebate() {
    if (startPending) {
      return;
    }

    const setup: DebateSetupData = {
      publicGoal: sharedGoal,
      publicDocuments: sharedDocuments,
      agent1PrivateGoal,
      agent1PrivateDocuments,
      agent2PrivateGoal,
      agent2PrivateDocuments,
    };

    setStartPending(true);
    setStartError("");

    try {
      const response = await fetch(buildApiPath("/api/debates/start"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...settings,
          topic: buildPublicTopic(setup),
          setup,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { id?: string; error?: string };
      if (payload.error || !payload.id) {
        throw new Error(payload.error ?? "Nie udało się utworzyć debaty.");
      }

      window.location.assign(buildAppPath(`/debate/${payload.id}`));
    } catch (error) {
      setStartError(error instanceof Error ? error.message : "Nie udało się rozpocząć debaty.");
      setStartPending(false);
    }
  }

  return (
    <div className={screenStyles.shell}>
      <aside className={`${screenStyles.sidebar} ${styles.newDebateSidebar}`} aria-label="Konfiguracja nowej debaty">
        <div className={screenStyles.logo}>
          Nowa debata
          <span className={screenStyles.logoSmall}>Uproszczony widok przygotowania sporu</span>
        </div>

        <div className={screenStyles.sidebarSectionCompact}>
          <a className={screenStyles.archiveLink} href={homeHref}>
            Strona główna
          </a>
          <a className={screenStyles.archiveLink} href={archiveHref}>
            Archiwum debat
          </a>
        </div>

        <div className={screenStyles.sidebarSection}>
          <section className={styles.panelSection}>
            <div className={styles.sectionHeading}>Setup wspolny</div>

            <div className={styles.agentForm}>
              <label className={styles.field}>
                <span className={styles.label}>Tryb rozmowy</span>
                <select value={settings.debate_mode} onChange={(event) => updateSettings({ debate_mode: event.target.value })}>
                  {DEBATE_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Maks. wymian</span>
                <input type="number" min={2} max={32} value={settings.max_turns} onChange={(event) => updateSettings({ max_turns: Number.parseInt(event.target.value, 10) || 10 })} />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Wspolny cel</span>
                <textarea className={styles.textarea} value={sharedGoal} onChange={(event) => setSharedGoal(event.target.value)} rows={6} placeholder="Cel publiczny wspolny dla obu agentow" />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Wspolne dokumenty</span>
                <textarea className={styles.textarea} value={sharedDocuments} onChange={(event) => setSharedDocuments(event.target.value)} rows={9} placeholder="Publiczne dokumenty i dane dostepne dla obu agentow" />
              </label>

              <button type="button" className={styles.startButton} disabled={startPending} onClick={() => void handleStartDebate()}>
                {startPending ? "Tworzenie debaty..." : "▶ Rozpocznij debate"}
              </button>

              {startError ? <div className={styles.startError}>{startError}</div> : null}
            </div>
          </section>

          <section className={styles.panelSection}>
            <div className={styles.sidebarHint}>Start zapisuje nowa debate i przenosi od razu na zwykly adres `/debate/uuid`, bez osobnego route live.</div>
          </section>
        </div>
      </aside>

      <main className={screenStyles.main}>
        <div className={screenStyles.contentGrid}>
          <section className={`${screenStyles.transcriptPane} ${styles.stagePane}`} aria-label="Podgląd nowej debaty">
            <div className={styles.stageIntro}>
              <span className={styles.kicker}>Nowa debata</span>
              <h1 className={styles.title}>Ustawienia debaty agentów</h1>
              <p className={styles.subtitle}>Lewa i prawa kolumna opisują prywatny setup każdego agenta. Środkowa kolumna zawiera wiedzę wspólną, cel publiczny i start debaty.</p>
            </div>

            <div className={styles.agentGrid}>
              <AgentCard
                slot={1}
                title="Setup agenta 1"
                agent={settings.agent1}
                provider={settings.provider1}
                model={settings.model1}
                maxTokens={settings.max_tokens1}
                privateGoal={agent1PrivateGoal}
                privateDocuments={agent1PrivateDocuments}
                agents={data.agents}
                availableModels={leftModels}
                onAgentChange={(agent) => updateSettings({ agent1: agent })}
                onProviderChange={(provider) => updateProvider(1, provider)}
                onModelChange={(model) => updateSettings({ model1: model })}
                onMaxTokensChange={(maxTokens) => updateSettings({ max_tokens1: maxTokens })}
                onPrivateGoalChange={setAgent1PrivateGoal}
                onPrivateDocumentsChange={setAgent1PrivateDocuments}
              />

              <AgentCard
                slot={2}
                title="Setup agenta 2"
                agent={settings.agent2}
                provider={settings.provider2}
                model={settings.model2}
                maxTokens={settings.max_tokens2}
                privateGoal={agent2PrivateGoal}
                privateDocuments={agent2PrivateDocuments}
                agents={data.agents}
                availableModels={rightModels}
                onAgentChange={(agent) => updateSettings({ agent2: agent })}
                onProviderChange={(provider) => updateProvider(2, provider)}
                onModelChange={(model) => updateSettings({ model2: model })}
                onMaxTokensChange={(maxTokens) => updateSettings({ max_tokens2: maxTokens })}
                onPrivateGoalChange={setAgent2PrivateGoal}
                onPrivateDocumentsChange={setAgent2PrivateDocuments}
              />
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}