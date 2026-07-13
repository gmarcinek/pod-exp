import type {
  BootstrapPayload,
  BootstrapRoute,
  DebateAnalysisData,
  DebateConfigData,
  DebateHistoryMessage,
  DebateLiveNotesData,
  DebateListItem,
  DebateRecord,
  DebateSetupData,
  DebateTranscriptEntry,
  DebatesBootstrapData,
  DebateViewBootstrapData,
  EditorialListItem,
  EditorialsBootstrapData,
  EditorialBootstrapData,
  FederationBootstrapData,
  FederationViewBootstrapData,
  FederationViewRecord,
  FederationViewTurn,
  AgentsBootstrapData,
  AgentSummary,
  HomeBootstrapData,
  ModelCatalog,
  NewDebateBootstrapData,
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
    debates: [],
  },
};

const defaultHomeData: HomeBootstrapData = {
  agents: [],
  models: {},
  debates: [],
};

const defaultDebatesData: DebatesBootstrapData = {
  debates: [],
};

const defaultEditorialsData: EditorialsBootstrapData = {
  editorials: [],
};

const defaultNewDebateData: NewDebateBootstrapData = {
  agents: [],
  models: {},
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

function readAnalysisData(
  value: unknown,
): DebateAnalysisData | null | undefined {
  if (value === undefined) {
    return undefined;
  }

  return isRecord(value) ? value : null;
}

function readConfigData(value: unknown): DebateConfigData | null | undefined {
  if (value === undefined) {
    return undefined;
  }

  return isRecord(value) ? value : null;
}

function readLiveNotesData(
  value: unknown,
): DebateLiveNotesData | null | undefined {
  if (value === undefined) {
    return undefined;
  }

  return isRecord(value) ? value : null;
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((entry) => typeof entry === "string")
  );
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
    typeof value.process_id === "string" &&
    typeof value.timestamp === "string" &&
    typeof value.agent1 === "string" &&
    typeof value.agent2 === "string" &&
    typeof value.topic === "string" &&
    typeof value.turns === "number" &&
    typeof value.model1 === "string" &&
    typeof value.model2 === "string"
  );
}

function isEditorialListItem(value: unknown): value is EditorialListItem {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.timestamp === "string" &&
    typeof value.topic === "string" &&
    typeof value.model === "string" &&
    typeof value.provider === "string" &&
    typeof value.cycles_completed === "number"
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

function isHistoryMessage(value: unknown): value is DebateHistoryMessage {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.role === "string" && typeof value.content === "string";
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
  if (
    value === "home" ||
    value === "debates" ||
    value === "editorials" ||
    value === "debate-view" ||
    value === "new-debate" ||
    value === "editorial" ||
    value === "federation" ||
    value === "federation-view" ||
    value === "agents"
  ) {
    return value;
  }

  return defaultPayload.route;
}

function normalizePathname(pathname: string): string {
  const withoutSuffix = pathname.split("?")[0]?.split("#")[0] ?? "";
  const normalized = withoutSuffix.startsWith("/")
    ? withoutSuffix
    : `/${withoutSuffix}`;

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
    debates: Array.isArray(value.debates)
      ? value.debates.filter(isDebateListItem)
      : [],
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

function parseEditorialsData(value: unknown): EditorialsBootstrapData {
  if (!isRecord(value) || !Array.isArray(value.editorials)) {
    return defaultEditorialsData;
  }

  return {
    editorials: value.editorials.filter(isEditorialListItem),
  };
}

function parseNewDebateData(value: unknown): NewDebateBootstrapData {
  if (!isRecord(value)) {
    return defaultNewDebateData;
  }

  return {
    agents: isStringArray(value.agents) ? value.agents : [],
    models: isModelCatalog(value.models) ? value.models : {},
  };
}

function isDebateSetupData(value: unknown): value is DebateSetupData {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.publicGoal === "string" &&
    typeof value.publicDocuments === "string" &&
    typeof value.agent1PrivateGoal === "string" &&
    typeof value.agent1PrivateDocuments === "string" &&
    typeof value.agent2PrivateGoal === "string" &&
    typeof value.agent2PrivateDocuments === "string"
  );
}

function readDebateSetupData(
  value: unknown,
): DebateSetupData | null | undefined {
  if (value === undefined) {
    return undefined;
  }

  return isDebateSetupData(value) ? value : null;
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
    config: null,
    setup: null,
    history1: [],
    history2: [],
    transcript: [],
    live_notes: null,
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
    case "editorials":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: defaultEditorialsData,
      };
    case "new-debate":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: defaultNewDebateData,
      };
    case "editorial":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: {
          models: {},
        },
      };
    case "debate-view":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: { agents: [], models: {}, debate: createFallbackDebate() },
      };
    case "federation":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: {
          agents: [],
          models: {},
        },
      };
    case "federation-view":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: {
          record: {
            id: "",
            timestamp: "",
            topic: "",
            agents: [],
            model: "",
            transcript: [],
            live_notes: null,
            summary: "",
            total_steps: 0,
          },
        },
      };
    case "agents":
      return {
        route,
        apiBaseUrl: "",
        appBasePath: "",
        initialData: { agents: [] as AgentSummary[] },
      };
    case "home":
    default:
      return defaultPayload;
  }
}

export function getBootstrapRouteFromPathname(
  pathname: string,
  appBasePath = "",
): BootstrapRoute {
  const routePath = stripAppBasePath(pathname, appBasePath);

  if (routePath === "/newDebate") {
    return "new-debate";
  }

  if (routePath === "/debates") {
    return "debates";
  }

  if (routePath === "/editorials") {
    return "editorials";
  }

  if (routePath.startsWith("/debate/") || routePath.startsWith("/debates/")) {
    return "debate-view";
  }

  if (routePath === "/federation") {
    return "federation";
  }

  if (routePath === "/editorial") {
    return "editorial";
  }

  if (routePath.startsWith("/federation/")) {
    return "federation-view";
  }

  if (routePath === "/agents") {
    return "agents";
  }

  return "home";
}

export function getDebateIdFromPathname(
  pathname: string,
  appBasePath = "",
): string | null {
  const routePath = stripAppBasePath(pathname, appBasePath);

  const routePrefixes = ["/debate/", "/debates/"];

  for (const routePrefix of routePrefixes) {
    if (!routePath.startsWith(routePrefix)) {
      continue;
    }

    const debateId = routePath.slice(routePrefix.length).split("/")[0] ?? "";

    return debateId ? decodeURIComponent(debateId) : null;
  }

  return null;
}

export function getFederationIdFromPathname(
  pathname: string,
  appBasePath = "",
): string | null {
  const routePath = stripAppBasePath(pathname, appBasePath);
  const prefix = "/federation/";
  if (!routePath.startsWith(prefix)) return null;
  const id = routePath.slice(prefix.length).split("/")[0] ?? "";
  return id ? decodeURIComponent(id) : null;
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
    config: readConfigData(value.config),
    setup: readDebateSetupData(value.setup),
    history1: Array.isArray(value.history1)
      ? value.history1
          .filter(isHistoryMessage)
          .map((entry) => ({ role: entry.role, content: entry.content }))
      : [],
    history2: Array.isArray(value.history2)
      ? value.history2
          .filter(isHistoryMessage)
          .map((entry) => ({ role: entry.role, content: entry.content }))
      : [],
    transcript: value.transcript
      .map(parseTranscriptEntry)
      .filter((entry): entry is DebateTranscriptEntry => entry !== null),
    live_notes: readLiveNotesData(value.live_notes),
    analysis: readOptionalString(value.analysis),
    analysis_json: readAnalysisData(value.analysis_json),
    analysis_thinking: readOptionalString(value.analysis_thinking),
    summary: readOptionalString(value.summary),
    summary_thinking: readOptionalString(value.summary_thinking),
  };
}

function parseDebateViewData(value: unknown): DebateViewBootstrapData {
  if (!isRecord(value) || !isDebateRecord(value.debate)) {
    return { agents: [], models: {}, debate: createFallbackDebate() };
  }

  return {
    agents: isStringArray(value.agents) ? value.agents : [],
    models: isModelCatalog(value.models) ? value.models : {},
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
    case "editorials":
      return {
        route,
        apiBaseUrl,
        appBasePath,
        initialData: parseEditorialsData(payload.initialData),
      };
    case "new-debate":
      return {
        route,
        apiBaseUrl,
        appBasePath,
        initialData: parseNewDebateData(payload.initialData),
      };
    case "editorial": {
      const ed = payload.initialData;
      const editorialData: EditorialBootstrapData = {
        models:
          isRecord(ed) && isModelCatalog((ed as Record<string, unknown>).models)
            ? ((ed as Record<string, unknown>).models as ModelCatalog)
            : {},
      };
      return { route, apiBaseUrl, appBasePath, initialData: editorialData };
    }
    case "debate-view":
      return {
        route,
        apiBaseUrl,
        appBasePath,
        initialData: parseDebateViewData(payload.initialData),
      };
    case "federation": {
      const fd = payload.initialData;
      const federationData: FederationBootstrapData = {
        agents:
          isRecord(fd) && isStringArray((fd as Record<string, unknown>).agents)
            ? ((fd as Record<string, unknown>).agents as string[])
            : [],
        models:
          isRecord(fd) && isModelCatalog((fd as Record<string, unknown>).models)
            ? ((fd as Record<string, unknown>).models as ModelCatalog)
            : {},
      };
      return { route, apiBaseUrl, appBasePath, initialData: federationData };
    }
    case "federation-view": {
      const fv = payload.initialData;
      const rawRecord = isRecord(fv)
        ? (fv as Record<string, unknown>).record
        : undefined;
      const rec = isRecord(rawRecord) ? rawRecord : {};
      const transcript: FederationViewTurn[] = Array.isArray(rec.transcript)
        ? (rec.transcript as unknown[]).filter(isRecord).map((t) => ({
            agent: typeof t.agent === "string" ? t.agent : "",
            short_name: typeof t.short_name === "string" ? t.short_name : "",
            content: typeof t.content === "string" ? t.content : "",
            step: typeof t.step === "number" ? t.step : 0,
            thinking: typeof t.thinking === "string" ? t.thinking : undefined,
          }))
        : [];
      const fvRecord: FederationViewRecord = {
        id: typeof rec.id === "string" ? rec.id : "",
        timestamp: typeof rec.timestamp === "string" ? rec.timestamp : "",
        topic: typeof rec.topic === "string" ? rec.topic : "",
        agents: isStringArray(rec.agents) ? rec.agents : [],
        model: typeof rec.model === "string" ? rec.model : "",
        transcript,
        live_notes: isRecord(rec.live_notes) ? rec.live_notes : null,
        summary: typeof rec.summary === "string" ? rec.summary : "",
        total_steps:
          typeof rec.total_steps === "number"
            ? rec.total_steps
            : transcript.length,
      };
      const fvData: FederationViewBootstrapData = { record: fvRecord };
      return { route, apiBaseUrl, appBasePath, initialData: fvData };
    }
    case "agents": {
      const ad = payload.initialData;
      const agentsData: AgentsBootstrapData = {
        agents:
          isRecord(ad) && Array.isArray((ad as Record<string, unknown>).agents)
            ? ((ad as Record<string, unknown>).agents as AgentSummary[])
            : [],
      };
      return { route, apiBaseUrl, appBasePath, initialData: agentsData };
    }
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
  const expectedRoute = getBootstrapRouteFromPathname(
    window.location.pathname,
    payload.appBasePath,
  );

  return payload.route === expectedRoute ? payload : null;
}

export function getBootstrapData(): BootstrapPayload {
  const payload = getCurrentBootstrapPayload();

  if (payload) {
    return payload;
  }

  return createDefaultPayload(
    getBootstrapRouteFromPathname(window.location.pathname),
  );
}

export function hasBootstrapPayload(): boolean {
  return getCurrentBootstrapPayload() !== null;
}

export function setBootstrapData(payload: BootstrapPayload) {
  window.__POD_EXP_BOOTSTRAP__ = payload;
}
