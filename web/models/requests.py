"""Pydantic request models for the web API."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AnalysisStartRequest(BaseModel):
    """Request to start a new analysis run."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9._^\-]+$",
        description="Ticker symbol (e.g. AAPL, 0700.HK, BTC-USD)",
    )
    analysis_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Analysis date in YYYY-MM-DD format",
    )
    output_language: str = Field(
        default="English",
        description="Language for analyst reports and final decision",
    )
    analysts: List[str] = Field(
        default=["market", "social", "news", "fundamentals"],
        description="Selected analyst types",
    )
    research_depth: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Research depth (1=Shallow, 3=Medium, 5=Deep)",
    )
    llm_provider: str = Field(
        default="openai",
        description="LLM provider key",
    )
    backend_url: Optional[str] = Field(
        default=None,
        description="Override API endpoint URL",
    )
    quick_think_llm: str = Field(
        default="gpt-5.4-mini",
        description="Model for quick-thinking tasks",
    )
    deep_think_llm: str = Field(
        default="gpt-5.5",
        description="Model for deep-thinking tasks",
    )
    google_thinking_level: Optional[str] = Field(
        default=None,
        description="Google Gemini thinking level (high/minimal)",
    )
    openai_reasoning_effort: Optional[str] = Field(
        default=None,
        description="OpenAI reasoning effort (low/medium/high)",
    )
    anthropic_effort: Optional[str] = Field(
        default=None,
        description="Anthropic effort level (low/medium/high)",
    )
    temperature: Optional[float] = Field(
        default=None,
        description="Sampling temperature for LLM",
    )


class ConfigValidateRequest(BaseModel):
    """Request to validate a configuration without running analysis."""

    llm_provider: Optional[str] = None
    quick_think_llm: Optional[str] = None
    deep_think_llm: Optional[str] = None
    backend_url: Optional[str] = None
