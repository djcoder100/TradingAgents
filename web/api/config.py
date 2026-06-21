"""API routes for configuration, providers, and model information."""

from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, Query

from cli.utils import (
    _llm_provider_table,
    ANALYST_ORDER,
    filter_analysts_for_asset_type,
)
from cli.models import AssetType
from tradingagents.llm_clients.model_catalog import get_model_options
from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV
from tradingagents.default_config import DEFAULT_CONFIG

from web.models.responses import (
    ConfigResponse,
    ProviderInfo,
    ProviderRegion,
    ModelOption,
    LanguageOption,
    ResearchDepthOption,
)

router = APIRouter(tags=["config"])


# ── Static option tables ────────────────────────────────────────────────────

_LANGUAGES: List[LanguageOption] = [
    LanguageOption(value="English", label="English (default)"),
    LanguageOption(value="Chinese", label="Chinese (中文)"),
    LanguageOption(value="Japanese", label="Japanese (日本語)"),
    LanguageOption(value="Korean", label="Korean (한국어)"),
    LanguageOption(value="Hindi", label="Hindi (हिन्दी)"),
    LanguageOption(value="Spanish", label="Spanish (Español)"),
    LanguageOption(value="Portuguese", label="Portuguese (Português)"),
    LanguageOption(value="French", label="French (Français)"),
    LanguageOption(value="German", label="German (Deutsch)"),
    LanguageOption(value="Arabic", label="Arabic (العربية)"),
    LanguageOption(value="Russian", label="Russian (Русский)"),
]

_RESEARCH_DEPTHS: List[ResearchDepthOption] = [
    ResearchDepthOption(
        value=1,
        label="Shallow - Quick research, few debate rounds",
    ),
    ResearchDepthOption(
        value=3,
        label="Medium - Moderate debate rounds",
    ),
    ResearchDepthOption(
        value=5,
        label="Deep - Comprehensive research, in-depth debate",
    ),
]

_ANALYSTS = [
    {"key": item[1].value, "label": item[0], "available_for_crypto": item[1].value != "fundamentals"}
    for item in ANALYST_ORDER
]


# ── Region definitions for multi-region providers ───────────────────────────

_QWEN_REGIONS = [
    ProviderRegion(
        key="qwen",
        display_name="International — dashscope-intl.aliyuncs.com (DASHSCOPE_API_KEY)",
        url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ),
    ProviderRegion(
        key="qwen-cn",
        display_name="China — dashscope.aliyuncs.com (DASHSCOPE_CN_API_KEY)",
        url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
]

_GLM_REGIONS = [
    ProviderRegion(
        key="glm",
        display_name="Z.AI — api.z.ai (international, ZHIPU_API_KEY)",
        url="https://api.z.ai/api/paas/v4/",
    ),
    ProviderRegion(
        key="glm-cn",
        display_name="BigModel — open.bigmodel.cn (China, ZHIPU_CN_API_KEY)",
        url="https://open.bigmodel.cn/api/paas/v4/",
    ),
]

_MINIMAX_REGIONS = [
    ProviderRegion(
        key="minimax",
        display_name="Global — api.minimax.io (MINIMAX_API_KEY)",
        url="https://api.minimax.io/v1",
    ),
    ProviderRegion(
        key="minimax-cn",
        display_name="China — api.minimaxi.com (MINIMAX_CN_API_KEY)",
        url="https://api.minimaxi.com/v1",
    ),
]


def _build_provider_info(key: str) -> ProviderInfo:
    """Build a ProviderInfo from a provider key."""
    display_name = key
    default_url = None
    for dname, pkey, url in _llm_provider_table():
        if pkey == key:
            display_name = dname
            default_url = url
            break

    api_key_env = PROVIDER_API_KEY_ENV.get(key)

    # Region-aware providers
    has_regions = key in ("qwen", "glm", "minimax")
    regions = []
    if has_regions:
        if key == "qwen":
            regions = _QWEN_REGIONS
        elif key == "glm":
            regions = _GLM_REGIONS
        elif key == "minimax":
            regions = _MINIMAX_REGIONS

    # Provider-specific thinking config support
    supports_reasoning_effort = key == "openai"
    supports_thinking_level = key == "google"
    supports_effort = key == "anthropic"

    return ProviderInfo(
        key=key,
        display_name=display_name,
        default_url=default_url,
        has_regions=has_regions,
        regions=regions,
        requires_api_key=api_key_env is not None,
        api_key_env=api_key_env,
        supports_reasoning_effort=supports_reasoning_effort,
        supports_thinking_level=supports_thinking_level,
        supports_effort=supports_effort,
    )


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Return the full configuration state: defaults, available options, providers."""
    all_providers = []
    for _, pkey, _ in _llm_provider_table():
        all_providers.append(_build_provider_info(pkey))

    return ConfigResponse(
        llm_provider=DEFAULT_CONFIG.get("llm_provider", "openai"),
        quick_think_llm=DEFAULT_CONFIG.get("quick_think_llm", "gpt-5.4-mini"),
        deep_think_llm=DEFAULT_CONFIG.get("deep_think_llm", "gpt-5.5"),
        backend_url=DEFAULT_CONFIG.get("backend_url"),
        output_language=DEFAULT_CONFIG.get("output_language", "English"),
        max_debate_rounds=DEFAULT_CONFIG.get("max_debate_rounds", 1),
        max_risk_discuss_rounds=DEFAULT_CONFIG.get("max_risk_discuss_rounds", 1),
        google_thinking_level=DEFAULT_CONFIG.get("google_thinking_level"),
        openai_reasoning_effort=DEFAULT_CONFIG.get("openai_reasoning_effort"),
        anthropic_effort=DEFAULT_CONFIG.get("anthropic_effort"),
        benchmark_ticker=DEFAULT_CONFIG.get("benchmark_ticker"),
        checkpoint_enabled=DEFAULT_CONFIG.get("checkpoint_enabled", False),
        temperature=DEFAULT_CONFIG.get("temperature"),
        available_providers=all_providers,
        output_languages=_LANGUAGES,
        research_depths=_RESEARCH_DEPTHS,
        analysts=_ANALYSTS,
    )


@router.get("/providers/{provider_key}/models")
async def get_provider_models(
    provider_key: str,
    mode: str = Query("quick", description="quick or deep"),
):
    """Return model options for a specific provider and mode."""
    # Validate mode
    if mode not in ("quick", "deep"):
        mode = "quick"

    try:
        options = get_model_options(provider_key, mode)
        models = [ModelOption(display=display, value=value) for display, value in options]
        # All providers with get_model_options support custom model ID
        supports_custom = provider_key.lower() not in ("openrouter",)
        return {"models": models, "supports_custom": supports_custom}
    except Exception:
        return {"models": [], "supports_custom": True}
