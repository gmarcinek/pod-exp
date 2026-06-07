import type { ChangeEvent } from "react";
import type { ModelCatalog } from "../../../lib/types/bootstrap";
import {
  DEBATE_MODE_OPTIONS,
  MAX_TOKEN_OPTIONS,
  THINKING_OPTIONS,
  THINKING_MODELS,
  getModelsForProvider,
} from "../shared/home-constants";
import type { DebateSettings } from "../shared/home-types";
import styles from "./debate-config-panel.module.scss";

type DebateConfigPanelProps = {
  agents: string[];
  models: ModelCatalog;
  settings: DebateSettings;
  canContinue: boolean;
  debateActive: boolean;
  onChange: (value: DebateSettings) => void;
  onStart: () => void;
  onContinue: () => void;
  onStop: () => void;
};

type AgentSlotProps = {
  slot: 1 | 2;
  title: string;
  accentClassName: string;
  agents: string[];
  models: ModelCatalog;
  settings: DebateSettings;
  onChange: (value: DebateSettings) => void;
};

function AgentSlot({
  slot,
  title,
  accentClassName,
  agents,
  models,
  settings,
  onChange,
}: AgentSlotProps) {
  const providerKey = slot === 1 ? "provider1" : "provider2";
  const modelKey = slot === 1 ? "model1" : "model2";
  const agentKey = slot === 1 ? "agent1" : "agent2";
  const thinkingKey = slot === 1 ? "thinking_effort1" : "thinking_effort2";
  const maxTokensKey = slot === 1 ? "max_tokens1" : "max_tokens2";
  const provider = settings[providerKey];
  const providerModels = getModelsForProvider(models, provider);
  const currentModel = settings[modelKey];

  function update<K extends keyof DebateSettings>(
    key: K,
    value: DebateSettings[K],
  ) {
    onChange({ ...settings, [key]: value });
  }

  function handleProviderChange(event: ChangeEvent<HTMLInputElement>) {
    const nextProvider = event.target
      .value as DebateSettings[typeof providerKey];
    onChange({
      ...settings,
      [providerKey]: nextProvider,
      [modelKey]: models[nextProvider]?.[0] ?? "",
      [thinkingKey]: null,
    });
  }

  return (
    <div className={`${styles.slot} ${accentClassName}`}>
      <div className={styles.slotTitle}>{title}</div>
      <div className={styles.slotGrid}>
        <select
          className={styles.slotSpan2}
          value={settings[agentKey]}
          onChange={(event) =>
            update(
              agentKey,
              event.target.value as DebateSettings[typeof agentKey],
            )
          }
        >
          {agents.map((agent) => (
            <option key={agent} value={agent}>
              {agent}
            </option>
          ))}
        </select>

        <div className={`${styles.toggle} ${styles.slotSpan2}`}>
          <input
            id={`d-p${slot}-oa`}
            type="radio"
            name={`prov${slot}`}
            value="openai"
            checked={provider === "openai"}
            onChange={handleProviderChange}
          />
          <label htmlFor={`d-p${slot}-oa`}>OpenAI</label>
          <input
            id={`d-p${slot}-an`}
            type="radio"
            name={`prov${slot}`}
            value="anthropic"
            checked={provider === "anthropic"}
            onChange={handleProviderChange}
          />
          <label htmlFor={`d-p${slot}-an`}>Anthropic</label>
          <input
            id={`d-p${slot}-ol`}
            type="radio"
            name={`prov${slot}`}
            value="ollama"
            checked={provider === "ollama"}
            onChange={handleProviderChange}
          />
          <label htmlFor={`d-p${slot}-ol`}>Ollama</label>
        </div>

        <select
          className={styles.slotSpan2}
          value={currentModel}
          onChange={(event) =>
            update(
              modelKey,
              event.target.value as DebateSettings[typeof modelKey],
            )
          }
        >
          {providerModels.map((model) => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </select>

        <select
          value={settings[thinkingKey] ?? ""}
          onChange={(event) =>
            update(
              thinkingKey,
              (event.target.value ||
                null) as DebateSettings[typeof thinkingKey],
            )
          }
          style={{
            display: THINKING_MODELS.has(currentModel) ? undefined : "none",
          }}
        >
          <option value="">thinking: off</option>
          {THINKING_OPTIONS.filter((option) => option.value).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select
          value={settings[maxTokensKey]}
          onChange={(event) =>
            update(
              maxTokensKey,
              event.target.value as DebateSettings[typeof maxTokensKey],
            )
          }
        >
          {MAX_TOKEN_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value === "4096"
                ? "4k"
                : value === "8192"
                  ? "8k"
                  : value === "12288"
                    ? "12k"
                    : value}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function DebateConfigPanel({
  agents,
  models,
  settings,
  canContinue,
  debateActive,
  onChange,
  onStart,
  onContinue,
  onStop,
}: DebateConfigPanelProps) {
  function update<K extends keyof DebateSettings>(
    key: K,
    value: DebateSettings[K],
  ) {
    onChange({ ...settings, [key]: value });
  }

  return (
    <div className={styles.stack}>
      <div className={styles.field}>
        <div className={styles.label}>Tryb rozmowy</div>
        <select
          value={settings.debate_mode}
          onChange={(event) => update("debate_mode", event.target.value)}
        >
          {DEBATE_MODE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {settings.debate_mode === "inne" ? (
          <input
            type="text"
            value={settings.debate_mode_custom}
            placeholder="Np. przesłuchanie, seminarium, konsultacja"
            onChange={(event) =>
              update("debate_mode_custom", event.target.value)
            }
          />
        ) : null}
      </div>

      <AgentSlot
        slot={1}
        title="⚔ Agent 1"
        accentClassName={styles.slotOne}
        agents={agents}
        models={models}
        settings={settings}
        onChange={onChange}
      />
      <AgentSlot
        slot={2}
        title="⚔ Agent 2"
        accentClassName={styles.slotTwo}
        agents={agents}
        models={models}
        settings={settings}
        onChange={onChange}
      />

      <div className={styles.field}>
        <div className={styles.label}>Temat debaty</div>
        <textarea
          rows={6}
          value={settings.topic}
          placeholder="Czym jest prawda?"
          onChange={(event) => update("topic", event.target.value)}
        />
      </div>

      <div className={styles.field}>
        <div className={styles.label}>Maks. wymian</div>
        <input
          type="number"
          min={2}
          max={32}
          value={settings.max_turns}
          onChange={(event) =>
            update("max_turns", Number.parseInt(event.target.value, 10) || 10)
          }
        />
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.startButton}
          disabled={debateActive}
          onClick={onStart}
        >
          ▶ Rozpocznij debatę
        </button>
        {canContinue ? (
          <button
            type="button"
            className={styles.continueButton}
            disabled={debateActive}
            onClick={onContinue}
          >
            ↻ Kontynuuj
          </button>
        ) : null}
        {debateActive ? (
          <button type="button" className={styles.stopButton} onClick={onStop}>
            ■ Zatrzymaj
          </button>
        ) : null}
      </div>
    </div>
  );
}
