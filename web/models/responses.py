"""Pydantic response models for the web API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProviderRegion(BaseModel):
    key: str
    display_name: str
    url: str


class ProviderInfo(BaseModel):
    key: str
    display_name: str
    default_url: Optional[str] = None
    has_regions: bool = False
    regions: List[ProviderRegion] = []
    requires_api_key: bool = True
    api_key_env: Optional[str] = None
    supports_reasoning_effort: bool = False
    supports_thinking_level: bool = False
    supports_effort: bool = False


class ModelOption(BaseModel):
    display: str
    value: str


class LanguageOption(BaseModel):
    value: str
    label: str


class ResearchDepthOption(BaseModel):
    value: int
    label: str


class AnalystOption(BaseModel):
    key: str
    label: str
    available_for_crypto: bool


class ConfigResponse(BaseModel):
    llm_provider: str
    quick_think_llm: str
    deep_think_llm: str
    backend_url: Optional[str]
    output_language: str
    max_debate_rounds: int
    max_risk_discuss_rounds: int
    google_thinking_level: Optional[str]
    openai_reasoning_effort: Optional[str]
    anthropic_effort: Optional[str]
    benchmark_ticker: Optional[str]
    checkpoint_enabled: bool
    temperature: Optional[float]
    available_providers: List[ProviderInfo]
    output_languages: List[LanguageOption]
    research_depths: List[ResearchDepthOption]
    analysts: List[AnalystOption]


class AnalysisStartResponse(BaseModel):
    task_id: str
    status: str
    ticker: str
    analysis_date: str
    created_at: str


class AgentStatus(BaseModel):
    agent_name: str
    status: str  # pending | running | completed | error


class TaskProgress(BaseModel):
    agent_status: Dict[str, str] = {}
    reports_completed: int = 0
    reports_total: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    elapsed_seconds: float = 0.0
    current_report_section: Optional[str] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending | running | completed | failed
    progress: TaskProgress
    error: Optional[str] = None


class DebateState(BaseModel):
    bull_history: Optional[str] = None
    bear_history: Optional[str] = None
    judge_decision: Optional[str] = None


class RiskDebateState(BaseModel):
    aggressive_history: Optional[str] = None
    conservative_history: Optional[str] = None
    neutral_history: Optional[str] = None
    judge_decision: Optional[str] = None


class AnalysisResultFinalState(BaseModel):
    market_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    news_report: Optional[str] = None
    fundamentals_report: Optional[str] = None
    investment_plan: Optional[str] = None
    trader_investment_plan: Optional[str] = None
    final_trade_decision: Optional[str] = None
    investment_debate_state: Optional[DebateState] = None
    risk_debate_state: Optional[RiskDebateState] = None


class AnalysisStats(BaseModel):
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    elapsed_seconds: float = 0.0
    analyst_wall_times: Dict[str, float] = {}


class AnalysisResultResponse(BaseModel):
    task_id: str
    ticker: str
    analysis_date: str
    signal: str
    final_state: AnalysisResultFinalState
    stats: AnalysisStats
    asset_type: str = "stock"
    instrument_context: Optional[str] = None


class HistoryRun(BaseModel):
    run_id: str
    ticker: str
    analysis_date: str
    signal: str
    created_at: Optional[str] = None
    asset_type: str = "stock"
    has_reflection: bool = False
    raw_return: Optional[str] = None
    alpha_return: Optional[str] = None


class HistoryResponse(BaseModel):
    items: List[HistoryRun]
    total: int
    offset: int
    limit: int


class MemoryEntry(BaseModel):
    date: str
    ticker: str
    rating: str
    pending: bool
    raw: Optional[str] = None
    alpha: Optional[str] = None
    holding: Optional[str] = None
    decision: Optional[str] = None
    reflection: Optional[str] = None


class MemoryLogResponse(BaseModel):
    entries: List[MemoryEntry]


class ErrorResponse(BaseModel):
    detail: str
