/** Generic API response wrappers and common types used across the frontend. */

export interface ApiError {
  detail: string;
}

export interface ProviderRegion {
  key: string;
  display_name: string;
  url: string;
}

export interface ProviderInfo {
  key: string;
  display_name: string;
  default_url: string | null;
  has_regions: boolean;
  regions: ProviderRegion[];
  requires_api_key: boolean;
  api_key_env: string | null;
  supports_reasoning_effort: boolean;
  supports_thinking_level: boolean;
  supports_effort: boolean;
}

export interface ModelOption {
  display: string;
  value: string;
}

export interface LanguageOption {
  value: string;
  label: string;
}

export interface ResearchDepthOption {
  value: number;
  label: string;
}

export interface AnalystOption {
  key: string;
  label: string;
  available_for_crypto: boolean;
}

export interface AppConfig {
  llm_provider: string;
  quick_think_llm: string;
  deep_think_llm: string;
  backend_url: string | null;
  output_language: string;
  max_debate_rounds: number;
  max_risk_discuss_rounds: number;
  google_thinking_level: string | null;
  openai_reasoning_effort: string | null;
  anthropic_effort: string | null;
  benchmark_ticker: string | null;
  checkpoint_enabled: boolean;
  temperature: number | null;
  available_providers: ProviderInfo[];
  output_languages: LanguageOption[];
  research_depths: ResearchDepthOption[];
  analysts: AnalystOption[];
}

export interface AnalysisStartRequest {
  ticker: string;
  analysis_date: string;
  output_language: string;
  analysts: string[];
  research_depth: number;
  llm_provider: string;
  backend_url: string | null;
  quick_think_llm: string;
  deep_think_llm: string;
  google_thinking_level: string | null;
  openai_reasoning_effort: string | null;
  anthropic_effort: string | null;
  temperature: number | null;
}

export interface AnalysisStartResponse {
  task_id: string;
  status: string;
  ticker: string;
  analysis_date: string;
  created_at: string;
}

export interface TaskProgress {
  agent_status: Record<string, string>;
  reports_completed: number;
  reports_total: number;
  llm_calls: number;
  tool_calls: number;
  tokens_in: number;
  tokens_out: number;
  elapsed_seconds: number;
  current_report_section: string | null;
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress: TaskProgress;
  error: string | null;
}

export interface DebateState {
  bull_history: string | null;
  bear_history: string | null;
  judge_decision: string | null;
}

export interface RiskDebateState {
  aggressive_history: string | null;
  conservative_history: string | null;
  neutral_history: string | null;
  judge_decision: string | null;
}

export interface AnalysisResultFinalState {
  market_report: string | null;
  sentiment_report: string | null;
  news_report: string | null;
  fundamentals_report: string | null;
  investment_plan: string | null;
  trader_investment_plan: string | null;
  final_trade_decision: string | null;
  investment_debate_state: DebateState | null;
  risk_debate_state: RiskDebateState | null;
}

export interface AnalysisStats {
  llm_calls: number;
  tool_calls: number;
  tokens_in: number;
  tokens_out: number;
  elapsed_seconds: number;
  analyst_wall_times: Record<string, number>;
}

export interface AnalysisResultResponse {
  task_id: string;
  ticker: string;
  analysis_date: string;
  signal: string;
  final_state: AnalysisResultFinalState;
  stats: AnalysisStats;
  asset_type: string;
  instrument_context: string | null;
}

export interface HistoryRun {
  run_id: string;
  ticker: string;
  analysis_date: string;
  signal: string;
  created_at: string | null;
  asset_type: string;
  has_reflection: boolean;
  raw_return: string | null;
  alpha_return: string | null;
}

export interface HistoryResponse {
  items: HistoryRun[];
  total: number;
  offset: number;
  limit: number;
}

export interface MemoryEntry {
  date: string;
  ticker: string;
  rating: string;
  pending: boolean;
  raw: string | null;
  alpha: string | null;
  holding: string | null;
  decision: string | null;
  reflection: string | null;
}

export type Signal = 'Buy' | 'Overweight' | 'Hold' | 'Underweight' | 'Sell';
