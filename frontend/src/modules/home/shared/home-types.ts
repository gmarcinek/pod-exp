export type HomeMode = "chat" | "debate";

export type ChatProvider = "openai" | "anthropic";

export type ChatSettings = {
  agent: string;
  provider: ChatProvider;
  model: string;
  thinking_effort: string | null;
};

export type DebateSettings = {
  agent1: string;
  agent2: string;
  provider1: ChatProvider;
  provider2: ChatProvider;
  model1: string;
  model2: string;
  thinking_effort1: string | null;
  thinking_effort2: string | null;
  max_tokens1: string;
  max_tokens2: string;
  topic: string;
  debate_mode: string;
  debate_mode_custom: string;
  max_turns: number;
};

export type ChatTranscriptEntry = {
  id: string;
  role: "user" | "assistant" | "tool" | "error";
  content: string;
  toolName?: string;
};

export type DebateTurnEntry = {
  id: string;
  type: "turn";
  slot: "s1" | "s2";
  agent: string;
  turn: number;
  total: number;
  thinking: string;
  content: string;
  renderContentAsMarkdown: boolean;
};

export type DebateTopicEntry = {
  id: string;
  type: "topic";
  topic: string;
};

export type DebateDividerEntry = {
  id: string;
  type: "divider";
  label: string;
};

export type DebateAnalysisEntry = {
  id: string;
  type: "analysis";
  variant: "analyzer" | "summariser";
  title: string;
  content: string;
  renderContentAsMarkdown: boolean;
  jsonData?: unknown;
};

export type DebateErrorEntry = {
  id: string;
  type: "error";
  message: string;
};

export type DebateTranscriptEntry =
  | DebateTurnEntry
  | DebateTopicEntry
  | DebateDividerEntry
  | DebateAnalysisEntry
  | DebateErrorEntry;

export type LiveNoteCard = {
  turn: number;
  agent?: string;
  note?: string;
};

export type FactCard = {
  turn: number;
  agent?: string;
  request?: string;
};

export type LiveNotes = {
  entries?: LiveNoteCard[];
  fact_cards?: FactCard[];
  facts_error?: string;
};

export type DebateContinuationState = {
  history1?: string[];
  history2?: string[];
  transcript?: Array<{ agent: string; content: string; thinking?: string }>;
  live_notes?: LiveNotes | null;
  turns_completed?: number;
};

export type DebateProgress = {
  fillPercent: number;
  label: string;
  savedDebateId: string | null;
};