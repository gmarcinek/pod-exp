import type { ChangeEvent } from "react";
import type { ModelCatalog } from "../../../lib/types/bootstrap";
import { THINKING_OPTIONS, getModelsForProvider } from "../shared/home-constants";
import type { ChatSettings } from "../shared/home-types";
import styles from "./chat-config-panel.module.scss";

type ChatConfigPanelProps = {
  agents: string[];
  models: ModelCatalog;
  settings: ChatSettings;
  showThinking: boolean;
  onChange: (value: ChatSettings) => void;
  onNewChat: () => void;
};

export function ChatConfigPanel({ agents, models, settings, showThinking, onChange, onNewChat }: ChatConfigPanelProps) {
  const providerModels = getModelsForProvider(models, settings.provider);

  function updateField<Key extends keyof ChatSettings>(key: Key, value: ChatSettings[Key]) {
    onChange({ ...settings, [key]: value });
  }

  function onProviderChange(event: ChangeEvent<HTMLInputElement>) {
    onChange({
      ...settings,
      provider: event.target.value as ChatSettings["provider"],
      model: models[event.target.value]?.[0] ?? "",
      thinking_effort: null,
    });
  }

  return (
    <div className={styles.stack}>
      <div className={styles.field}>
        <div className={styles.label}>Agent</div>
        <select value={settings.agent} onChange={(event) => updateField("agent", event.target.value)}>
          {agents.map((agent) => (
            <option key={agent} value={agent}>
              {agent}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <div className={styles.label}>Provider</div>
        <div className={styles.toggle}>
          <input id="p-openai" type="radio" name="provider" value="openai" checked={settings.provider === "openai"} onChange={onProviderChange} />
          <label htmlFor="p-openai">OpenAI</label>
          <input id="p-anthropic" type="radio" name="provider" value="anthropic" checked={settings.provider === "anthropic"} onChange={onProviderChange} />
          <label htmlFor="p-anthropic">Anthropic</label>
        </div>
      </div>

      <div className={styles.field}>
        <div className={styles.label}>Model</div>
        <select value={settings.model} onChange={(event) => updateField("model", event.target.value)}>
          {providerModels.map((model) => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </select>
      </div>

      {showThinking ? (
        <div className={styles.field}>
          <div className={styles.label}>Thinking effort</div>
          <select value={settings.thinking_effort ?? ""} onChange={(event) => updateField("thinking_effort", event.target.value || null)}>
            {THINKING_OPTIONS.map((option) => (
              <option key={option.value || "off"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <button type="button" className={styles.newButton} onClick={onNewChat}>
        ＋ Nowa rozmowa
      </button>
    </div>
  );
}