import type { ModelCatalog } from "../../../lib/types/bootstrap";
import type { ChatProvider, ChatSettings, DebateSettings } from "./home-types";

export const THINKING_MODELS = new Set(["gpt-5.4", "gpt-5.4-mini", "gpt-5.5", "gpt-5.5-mini"]);

export const STORAGE_KEYS = {
  chat: "pod-exp.chat-settings",
  debate: "pod-exp.debate-settings",
} as const;

export const DEBATE_MODE_OPTIONS = [
  { value: "dialog", label: "Dialog" },
  { value: "rozmowa", label: "Rozmowa" },
  { value: "debata", label: "Debata" },
  { value: "spor", label: "Spór" },
  { value: "klotnia", label: "Kłótnia" },
  { value: "terapia", label: "Terapia" },
  { value: "konsultacja", label: "Konsultacja" },
  { value: "wspolne_dociekanie", label: "Wspólne dociekanie" },
  { value: "burza_rozwiazan", label: "Burza rozwiązań" },
  { value: "mentoring", label: "Mentoring" },
  { value: "pojednanie", label: "Pojednanie" },
  { value: "negocjacje", label: "Negocjacje" },
  { value: "mediacja", label: "Mediacja" },
  { value: "rozprawa", label: "Rozprawa" },
  { value: "burza_mozgow", label: "Burza mózgów" },
  { value: "inne", label: "Inne" },
] as const;

export const MAX_TOKEN_OPTIONS = ["512", "1024", "2048", "4096", "8192", "12288", "32768", "max"];

export const THINKING_OPTIONS = [
  { value: "", label: "— wyłączony —" },
  { value: "auto", label: "auto" },
  { value: "medium", label: "medium" },
  { value: "high", label: "high" },
  { value: "low", label: "low" },
] as const;

function getProviderModels(models: ModelCatalog, provider: ChatProvider) {
  return models[provider] ?? [];
}

function getAvailableProvider(models: ModelCatalog, requested: string | undefined): ChatProvider {
  if (requested === "anthropic" && models.anthropic) {
    return "anthropic";
  }

  if (requested === "openai" && models.openai) {
    return "openai";
  }

  return models.openai ? "openai" : "anthropic";
}

function getModelOrFallback(models: ModelCatalog, provider: ChatProvider, requested: string | undefined) {
  const options = getProviderModels(models, provider);

  if (requested && options.includes(requested)) {
    return requested;
  }

  return options[0] ?? "";
}

function normalizeThinking(model: string, thinking: string | null | undefined) {
  if (!thinking || !THINKING_MODELS.has(model)) {
    return null;
  }

  return thinking;
}

export function getDefaultChatSettings(agents: string[], models: ModelCatalog): ChatSettings {
  const provider = getAvailableProvider(models, "openai");
  const defaultModel = getModelOrFallback(models, provider, undefined);

  return {
    agent: agents[0] ?? "",
    provider,
    model: defaultModel,
    thinking_effort: normalizeThinking(defaultModel, null),
  };
}

export function normalizeChatSettings(value: Partial<ChatSettings> | null | undefined, agents: string[], models: ModelCatalog) {
  const fallback = getDefaultChatSettings(agents, models);
  const provider = getAvailableProvider(models, value?.provider);
  const model = getModelOrFallback(models, provider, value?.model);

  return {
    agent: value?.agent && agents.includes(value.agent) ? value.agent : fallback.agent,
    provider,
    model,
    thinking_effort: normalizeThinking(model, value?.thinking_effort ?? fallback.thinking_effort),
  } satisfies ChatSettings;
}

export function getDefaultDebateSettings(agents: string[], models: ModelCatalog): DebateSettings {
  const provider1 = getAvailableProvider(models, "openai");
  const provider2 = getAvailableProvider(models, "openai");
  const agent1 = agents[0] ?? "";
  const agent2 = agents[1] ?? agents[0] ?? "";
  const model1 = getModelOrFallback(models, provider1, undefined);
  const model2 = getModelOrFallback(models, provider2, undefined);

  return {
    agent1,
    agent2,
    provider1,
    provider2,
    model1,
    model2,
    thinking_effort1: normalizeThinking(model1, null),
    thinking_effort2: normalizeThinking(model2, null),
    max_tokens1: "4096",
    max_tokens2: "4096",
    topic: "Czym jest prawda?",
    debate_mode: "dialog",
    debate_mode_custom: "",
    max_turns: 10,
  };
}

export function normalizeDebateSettings(value: Partial<DebateSettings> | null | undefined, agents: string[], models: ModelCatalog) {
  const fallback = getDefaultDebateSettings(agents, models);
  const provider1 = getAvailableProvider(models, value?.provider1);
  const provider2 = getAvailableProvider(models, value?.provider2);
  const model1 = getModelOrFallback(models, provider1, value?.model1);
  const model2 = getModelOrFallback(models, provider2, value?.model2);
  const maxTurns = Number.parseInt(String(value?.max_turns ?? fallback.max_turns), 10);

  return {
    agent1: value?.agent1 && agents.includes(value.agent1) ? value.agent1 : fallback.agent1,
    agent2: value?.agent2 && agents.includes(value.agent2) ? value.agent2 : fallback.agent2,
    provider1,
    provider2,
    model1,
    model2,
    thinking_effort1: normalizeThinking(model1, value?.thinking_effort1 ?? fallback.thinking_effort1),
    thinking_effort2: normalizeThinking(model2, value?.thinking_effort2 ?? fallback.thinking_effort2),
    max_tokens1: value?.max_tokens1 && MAX_TOKEN_OPTIONS.includes(String(value.max_tokens1)) ? String(value.max_tokens1) : fallback.max_tokens1,
    max_tokens2: value?.max_tokens2 && MAX_TOKEN_OPTIONS.includes(String(value.max_tokens2)) ? String(value.max_tokens2) : fallback.max_tokens2,
    topic: typeof value?.topic === "string" && value.topic.trim() ? value.topic.trim() : fallback.topic,
    debate_mode: typeof value?.debate_mode === "string" && value.debate_mode ? value.debate_mode : fallback.debate_mode,
    debate_mode_custom: typeof value?.debate_mode_custom === "string" ? value.debate_mode_custom : fallback.debate_mode_custom,
    max_turns: Number.isFinite(maxTurns) ? Math.min(Math.max(maxTurns, 2), 32) : fallback.max_turns,
  } satisfies DebateSettings;
}

export function getModelsForProvider(models: ModelCatalog, provider: ChatProvider) {
  return getProviderModels(models, provider);
}