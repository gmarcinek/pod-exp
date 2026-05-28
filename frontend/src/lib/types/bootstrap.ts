export type BootstrapRoute = "home" | "debates" | "debate-view";

export type ModelCatalog = Record<string, string[]>;

export type HomeBootstrapData = {
	agents: string[];
	models: ModelCatalog;
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

export type DebateAnalysisData = Record<string, unknown>;

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
	transcript: DebateTranscriptEntry[];
	analysis?: string;
	analysis_json?: DebateAnalysisData | null;
	analysis_thinking?: string;
	summary?: string;
	summary_thinking?: string;
};

export type DebateViewBootstrapData = {
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

export type BootstrapPayload =
	| HomeBootstrapPayload
	| DebatesBootstrapPayload
	| DebateViewBootstrapPayload;