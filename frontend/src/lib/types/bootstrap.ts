export type BootstrapRoute = "home" | "debates" | "debate-view" | "new-debate";

export type ModelCatalog = Record<string, string[]>;

export type HomeBootstrapData = {
	agents: string[];
	models: ModelCatalog;
	debates: DebateListItem[];
};

export type DebateListItem = {
	id: string;
	timestamp: string;
	agent1: string;
	agent2: string;
	topic: string;
	turns: number;
	model1: string;
	model2: string;
};

export type DebatesBootstrapData = {
	debates: DebateListItem[];
};

export type DebateTranscriptEntry = {
	agent: string;
	content: string;
	thinking?: string;
};

export type DebateHistoryMessage = {
	role: string;
	content: string;
};

export type DebateAnalysisData = Record<string, unknown>;
export type DebateConfigData = Record<string, unknown>;
export type DebateLiveNotesData = Record<string, unknown>;

export type DebateSetupData = {
	publicGoal: string;
	publicDocuments: string;
	agent1PrivateGoal: string;
	agent1PrivateDocuments: string;
	agent2PrivateGoal: string;
	agent2PrivateDocuments: string;
};

export type DebateRecord = {
	id: string;
	timestamp: string;
	agent1: string;
	agent2: string;
	provider1?: string;
	provider2?: string;
	model1: string;
	model2: string;
	thinking_effort1?: string;
	thinking_effort2?: string;
	max_tokens1?: string;
	max_tokens2?: string;
	debate_mode?: string;
	debate_mode_custom?: string;
	topic: string;
	config?: DebateConfigData | null;
	setup?: DebateSetupData | null;
	history1?: DebateHistoryMessage[];
	history2?: DebateHistoryMessage[];
	transcript: DebateTranscriptEntry[];
	live_notes?: DebateLiveNotesData | null;
	analysis?: string;
	analysis_json?: DebateAnalysisData | null;
	analysis_thinking?: string;
	summary?: string;
	summary_thinking?: string;
};

export type NewDebateBootstrapData = {
	agents: string[];
	models: ModelCatalog;
};

export type DebateViewBootstrapData = {
	agents: string[];
	models: ModelCatalog;
	debate: DebateRecord;
};

export type HomeBootstrapPayload = {
	route: "home";
	apiBaseUrl: string;
	appBasePath: string;
	initialData: HomeBootstrapData;
};

export type DebatesBootstrapPayload = {
	route: "debates";
	apiBaseUrl: string;
	appBasePath: string;
	initialData: DebatesBootstrapData;
};

export type DebateViewBootstrapPayload = {
	route: "debate-view";
	apiBaseUrl: string;
	appBasePath: string;
	initialData: DebateViewBootstrapData;
};

export type NewDebateBootstrapPayload = {
	route: "new-debate";
	apiBaseUrl: string;
	appBasePath: string;
	initialData: NewDebateBootstrapData;
};

export type BootstrapPayload =
	| HomeBootstrapPayload
	| DebatesBootstrapPayload
	| DebateViewBootstrapPayload
	| NewDebateBootstrapPayload;