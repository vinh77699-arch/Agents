export type AgentName = "planner" | "searcher" | "credibility" | "synthesizer" | "report_writer" | "pipeline";
export type AgentStatus = "pending" | "running" | "completed" | "failed" | "retrying";

export interface PipelineEvent {
  type: "agent_start" | "agent_complete" | "progress" | "complete" | "error" | "done";
  agent?: AgentName;
  message?: string;
  data?: Record<string, unknown>;
  session_id?: string;
  report?: string;
  bibliography?: string[];
  all_sources?: Record<string, SourceInfo>;
}

export interface AgentState {
  name: AgentName;
  label: string;
  status: AgentStatus;
  message: string;
  icon: string;
  data?: Record<string, unknown>;
}

export interface SourceInfo {
  source_id: string;
  url: string;
  title: string;
  total_score: number;
  domain_score: number;
  recency_score: number;
  cross_ref_score: number;
  llm_judge_score: number;
  explanation: string;
  is_credible: boolean;
  published_date?: string;
}
