import type { ModelCatalog } from "../../../lib/types/bootstrap";
import { STORAGE_KEYS, normalizeChatSettings, normalizeDebateSettings } from "./home-constants";
import type { ChatSettings, DebateSettings } from "./home-types";

function loadJson<T>(key: string) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function saveJson(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore storage write failures to match legacy behavior
  }
}

export function loadChatSettings(agents: string[], models: ModelCatalog): ChatSettings {
  return normalizeChatSettings(loadJson<Partial<ChatSettings>>(STORAGE_KEYS.chat), agents, models);
}

export function loadDebateSettings(agents: string[], models: ModelCatalog): DebateSettings {
  return normalizeDebateSettings(loadJson<Partial<DebateSettings>>(STORAGE_KEYS.debate), agents, models);
}

export function saveChatSettings(value: ChatSettings) {
  saveJson(STORAGE_KEYS.chat, value);
}

export function saveDebateSettings(value: DebateSettings) {
  saveJson(STORAGE_KEYS.debate, value);
}

export function clearStoredSettings() {
  try {
    window.localStorage.removeItem(STORAGE_KEYS.chat);
    window.localStorage.removeItem(STORAGE_KEYS.debate);
  } catch {
    // ignore storage clear failures to match legacy behavior
  }
}