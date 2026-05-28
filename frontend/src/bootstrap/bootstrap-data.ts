import type {
  BootstrapPayload,
  BootstrapRoute,
  DebateAnalysisData,
  DebateListItem,
  DebateRecord,
  DebateTranscriptEntry,
  DebatesBootstrapData,
  DebateViewBootstrapData,
  HomeBootstrapData,
  ModelCatalog,
} from "../lib/types/bootstrap";

export type { BootstrapPayload, BootstrapRoute } from "../lib/types/bootstrap";

declare global {
  interface Window {
    __POD_EXP_BOOTSTRAP__?: unknown;
  }
}

const defaultPayload: BootstrapPayload = {
  route: "home",
  apiBaseUrl: "",
  appBasePath: "",
  initialData: {
    agents: [],
    models: {},
  },
};

const defaultHomeData: HomeBootstrapData = {
  agents: [],
  models: {},
};

const defaultDebatesData: DebatesBootstrapData = {
  debates: [],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function readOptionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function readAnalysisData(value: unknown): DebateAnalysisData | null | undefined {
  if (value === undefined) {
    return undefined;
  }

  return isRecord(value) ? value : null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function isModelCatalog(value: unknown): value is ModelCatalog {
  if (!isRecord(value)) {
    return false;
  }

  return Object.values(value).every(isStringArray);
}

function isDebateListItem(value: unknown): value is DebateListItem {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.timestamp === "string" &&
    typeof value.agent1 === "string" &&
    typeof value.agent2 === "string" &&
    typeof value.topic === "string" &&
    typeof value.turns === "number" &&
    typeof value.model1 === "string" &&
    typeof value.model2 === "string"
  );
}

function isTranscriptEntry(value: unknown): value is DebateTranscriptEntry {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.agent === "string" &&
    typeof value.content === "string" &&
    (value.thinking === undefined || typeof value.thinking === "string")
  );
}

function isDebateRecord(value: unknown): value is DebateRecord {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.timestamp === "string" &&
    typeof value.agent1 === "string" &&
    typeof value.agent2 === "string" &&
    typeof value.model1 === "string" &&
    typeof value.model2 === "string" &&
    typeof value.topic === "string" &&
    Array.isArray(value.transcript) &&
    value.transcript.every(isTranscriptEntry)
  );
}

function parseRoute(value: unknown): BootstrapRoute {
  if (value === "home" || value === "debates" || value === "debate-view") {
    return value;
  }

  return defaultPayload.route;
}

function normalizePathname(pathname: string): string {
  const withoutSuffix = pathname.split("?")[0]?.split("#")[0] ?? "";
  const normalized = withoutSuffix.startsWith("/") ? withoutSuffix : `/${withoutSuffix}`;

  if (!normalized || normalized === "/") {
    return "/";
  }

  return normalized.replace(/\/+$/, "");
}

function stripAppBasePath(pathname: string, appBasePath = ""): string {
  const normalizedPathname = normalizePathname(pathname);
  const normalizedBasePath = normalizePathname(appBasePath);

  if (normalizedBasePath === "/") {
    return normalizedPathname;
  }

  if (normalizedPathname === normalizedBasePath) {
    return "/";
  }

  if (normalizedPathname.startsWith(`${normalizedBasePath}/`)) {
    return normalizedPathname.slice(normalizedBasePath.length) || "/";
  }

  return normalizedPathname;
}

function parseApiBaseUrl(value: unknown): string {
  return typeof value === "string" ? value : defaultPayload.apiBaseUrl;
}

function parseAppBasePath(value: unknown): string {
  return typeof value === "string" ? value : defaultPayload.appBasePath;
}

function parseHomeData(value: unknown): HomeBootstrapData {
  if (!isRecord(value)) {
    return defaultHomeData;
  }

  return {
    agents: isStringArray(value.agents) ? value.agents : [],
    models: isModelCatalog(value.models) ? value.models : {},
  };
}

function parseDebatesData(value: unknown): DebatesBootstrapData {
  if (!isRecord(value) || !Array.isArray(value.debates)) {
    return { debates: [] };
  }

  return {
    debates: value.debates.filter(isDebateListItem),
  };
}

function parseTranscriptEntry(value: unknown): DebateTranscriptEntry | null {
  if (!isTranscriptEntry(value)) {
    return null;
  }

  return {
    agent: value.agent,
    content: value.content,
    thinking: readOptionalString(value.thinking),
  };
}

function createFallbackDebate(): DebateRecord {
  return {
    id: "",
    timestamp: "",
    agent1: "",
    agent2: "",
    model1: "",
    model2: "",
    topic: "",
    transcript: [],
    analysis: "",
    analysis_json: null,
    analysis_thinking: "",
    summary: "",
    summary_thinking: "",
  };
}

function createDefaultPayload(route: BootstrapRoute): BootstrapPayload {
  switch (route) {
    case "debates":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: defaultDebatesData,
      };
    case "debate-view":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: { debate: createFallbackDebate() },
      };
    case "home":
    default:
      return defaultPayload;
  }
}

export function getBootstrapRouteFromPathname(pathname: string, appBasePath = ""): BootstrapRoute {
  const routePath = stripAppBasePath(pathname, appBasePath);

  if (routePath === "/debates") {
    return "debates";
  }

  if (routePath.startsWith("/debates/")) {
    return "debate-view";
  }

  return "home";
}

export function getDebateIdFromPathname(pathname: string, appBasePath = ""): string | null {
  const routePath = stripAppBasePath(pathname, appBasePath);

  if (!routePath.startsWith("/debates/")) {
    return null;
  }

  const debateId = routePath.slice("/debates/".length).split("/")[0] ?? "";

  return debateId ? decodeURIComponent(debateId) : null;
}

function parseDebateRecord(value: DebateRecord): DebateRecord {
  return {
    id: readString(value.id),
    timestamp: readString(value.timestamp),
    agent1: readString(value.agent1),
    agent2: readString(value.agent2),
    provider1: readOptionalString(value.provider1),
    provider2: readOptionalString(value.provider2),
    model1: readString(value.model1),
    model2: readString(value.model2),
    thinking_effort1: readOptionalString(value.thinking_effort1),
    thinking_effort2: readOptionalString(value.thinking_effort2),
    max_tokens1: readOptionalString(value.max_tokens1),
    max_tokens2: readOptionalString(value.max_tokens2),
    debate_mode: readOptionalString(value.debate_mode),
    debate_mode_custom: readOptionalString(value.debate_mode_custom),
    topic: readString(value.topic),
    transcript: value.transcript.map(parseTranscriptEntry).filter((entry): entry is DebateTranscriptEntry => entry !== null),
    analysis: readOptionalString(value.analysis),
    analysis_json: readAnalysisData(value.analysis_json),
    analysis_thinking: readOptionalString(value.analysis_thinking),
    summary: readOptionalString(value.summary),
    summary_thinking: readOptionalString(value.summary_thinking),
  };
}

function parseDebateViewData(value: unknown): DebateViewBootstrapData {
  if (!isRecord(value) || !isDebateRecord(value.debate)) {
    return { debate: createFallbackDebate() };
  }

  return {
    debate: parseDebateRecord(value.debate),
  };
}

export function parseBootstrapPayload(payload: unknown): BootstrapPayload {

  if (!isRecord(payload)) {
    return defaultPayload;
  }

  const route = parseRoute(payload.route);
  const apiBaseUrl = parseApiBaseUrl(payload.apiBaseUrl);
  const appBasePath = parseAppBasePath(payload.appBasePath);

  switch (route) {
    case "debates":
      return {
        route,
        apiBaseUrl,
        appBasePath,
        initialData: parseDebatesData(payload.initialData),
      };
    case "debate-view":
      return {
        route,
        apiBaseUrl,
        appBasePath,
        initialData: parseDebateViewData(payload.initialData),
      };
    case "home":
    default:
      return {
        route: "home",
        apiBaseUrl,
        appBasePath,
        initialData: parseHomeData(payload.initialData),
      };
  }
}

function getCurrentBootstrapPayload(): BootstrapPayload | null {
  if (window.__POD_EXP_BOOTSTRAP__ === undefined) {
    return null;
  }

  const payload = parseBootstrapPayload(window.__POD_EXP_BOOTSTRAP__);
  const expectedRoute = getBootstrapRouteFromPathname(window.location.pathname, payload.appBasePath);

  return payload.route === expectedRoute ? payload : null;
}

export function getBootstrapData(): BootstrapPayload {
  const payload = getCurrentBootstrapPayload();

  if (payload) {
    return payload;
  }

  return createDefaultPayload(getBootstrapRouteFromPathname(window.location.pathname));
}

export function hasBootstrapPayload(): boolean {
  return getCurrentBootstrapPayload() !== null;
}

export function setBootstrapData(payload: BootstrapPayload) {
  window.__POD_EXP_BOOTSTRAP__ = payload;
}