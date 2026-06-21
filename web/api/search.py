"""API route for resolving company names to ticker symbols.

Tries multiple sources: yfinance search, then a curated mapping of
well-known companies as a fast path for common queries.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("tradingagents.web.search")

router = APIRouter(tags=["search"])


class TickerResult(BaseModel):
    ticker: str
    name: str
    exchange: str


class SearchResponse(BaseModel):
    results: List[TickerResult]


# Fast-path mapping for common company name → ticker lookups.
# Extended with major global names.  Sorted by key for readability.
_KNOWN_COMPANIES: dict[str, list[dict]] = {
    "adobe":           [{"ticker": "ADBE",  "name": "Adobe Inc.",              "exchange": "NASDAQ"}],
    "airbnb":          [{"ticker": "ABNB",  "name": "Airbnb Inc.",             "exchange": "NASDAQ"}],
    "alibaba":         [{"ticker": "BABA",  "name": "Alibaba Group",           "exchange": "NYSE"}],
    "alphabet":        [{"ticker": "GOOGL", "name": "Alphabet Inc.",           "exchange": "NASDAQ"}],
    "amazon":          [{"ticker": "AMZN",  "name": "Amazon.com Inc.",         "exchange": "NASDAQ"}],
    "amd":             [{"ticker": "AMD",   "name": "Advanced Micro Devices",  "exchange": "NASDAQ"}],
    "apple":           [{"ticker": "AAPL",  "name": "Apple Inc.",              "exchange": "NASDAQ"}],
    "arm":             [{"ticker": "ARM",   "name": "Arm Holdings plc",        "exchange": "NASDAQ"}],
    "bank of america": [{"ticker": "BAC",   "name": "Bank of America Corp",    "exchange": "NYSE"}],
    "berkshire":       [{"ticker": "BRK-B", "name": "Berkshire Hathaway Inc.", "exchange": "NYSE"}],
    "byd":             [{"ticker": "1211.HK","name": "BYD Company Limited",    "exchange": "HKEX"}],
    "coca-cola":       [{"ticker": "KO",    "name": "The Coca-Cola Company",   "exchange": "NYSE"}],
    "costco":          [{"ticker": "COST",  "name": "Costco Wholesale Corp",   "exchange": "NASDAQ"}],
    "crowdstrike":     [{"ticker": "CRWD",  "name": "CrowdStrike Holdings",    "exchange": "NASDAQ"}],
    "disney":          [{"ticker": "DIS",   "name": "The Walt Disney Company", "exchange": "NYSE"}],
    "ethereum":        [{"ticker": "ETH-USD","name": "Ethereum",               "exchange": "CRYPTO"}],
    "exxon":           [{"ticker": "XOM",   "name": "Exxon Mobil Corp",        "exchange": "NYSE"}],
    "facebook":        [{"ticker": "META",  "name": "Meta Platforms Inc.",     "exchange": "NASDAQ"}],
    "goldman":         [{"ticker": "GS",    "name": "Goldman Sachs Group",     "exchange": "NYSE"}],
    "google":          [{"ticker": "GOOGL", "name": "Alphabet Inc.",           "exchange": "NASDAQ"}],
    "hsbc":            [{"ticker": "HSBC",  "name": "HSBC Holdings plc",       "exchange": "NYSE"}],
    "intel":           [{"ticker": "INTC",  "name": "Intel Corporation",       "exchange": "NASDAQ"}],
    "johnson":         [{"ticker": "JNJ",   "name": "Johnson & Johnson",       "exchange": "NYSE"}],
    "jpmorgan":        [{"ticker": "JPM",   "name": "JPMorgan Chase & Co.",    "exchange": "NYSE"}],
    "mastercard":      [{"ticker": "MA",    "name": "Mastercard Inc.",         "exchange": "NYSE"}],
    "mcdonalds":       [{"ticker": "MCD",   "name": "McDonald's Corporation",  "exchange": "NYSE"}],
    "meta":            [{"ticker": "META",  "name": "Meta Platforms Inc.",     "exchange": "NASDAQ"}],
    "microsoft":       [{"ticker": "MSFT",  "name": "Microsoft Corporation",   "exchange": "NASDAQ"}],
    "netflix":         [{"ticker": "NFLX",  "name": "Netflix Inc.",            "exchange": "NASDAQ"}],
    "nike":            [{"ticker": "NKE",   "name": "NIKE Inc.",               "exchange": "NYSE"}],
    "nvidia":          [{"ticker": "NVDA",  "name": "NVIDIA Corporation",      "exchange": "NASDAQ"}],
    "oracle":          [{"ticker": "ORCL",  "name": "Oracle Corporation",      "exchange": "NYSE"}],
    "palantir":        [{"ticker": "PLTR",  "name": "Palantir Technologies",   "exchange": "NASDAQ"}],
    "paypal":          [{"ticker": "PYPL",  "name": "PayPal Holdings Inc.",    "exchange": "NASDAQ"}],
    "pfizer":          [{"ticker": "PFE",   "name": "Pfizer Inc.",             "exchange": "NYSE"}],
    "procter":         [{"ticker": "PG",    "name": "Procter & Gamble Co.",    "exchange": "NYSE"}],
    "samsung":         [{"ticker": "005930.KS","name":"Samsung Electronics",   "exchange": "KRX"}],
    "shopify":         [{"ticker": "SHOP",  "name": "Shopify Inc.",            "exchange": "NYSE"}],
    "sony":            [{"ticker": "SONY",  "name": "Sony Group Corporation",  "exchange": "NYSE"}],
    "spacex":          [{"ticker": "",      "name": "SpaceX (private)",        "exchange": "PRIVATE"}],
    "spotify":         [{"ticker": "SPOT",  "name": "Spotify Technology S.A.", "exchange": "NYSE"}],
    "starbucks":       [{"ticker": "SBUX",  "name": "Starbucks Corporation",   "exchange": "NASDAQ"}],
    "taiwan semi":     [{"ticker": "TSM",   "name": "Taiwan Semiconductor",    "exchange": "NYSE"}],
    "tencent":         [{"ticker": "0700.HK","name":"Tencent Holdings Ltd",    "exchange": "HKEX"}],
    "tesla":           [{"ticker": "TSLA",  "name": "Tesla Inc.",              "exchange": "NASDAQ"}],
    "toyota":          [{"ticker": "TM",    "name": "Toyota Motor Corporation","exchange": "NYSE"}],
    "uber":            [{"ticker": "UBER",  "name": "Uber Technologies Inc.",  "exchange": "NYSE"}],
    "visa":            [{"ticker": "V",     "name": "Visa Inc.",               "exchange": "NYSE"}],
    "walmart":         [{"ticker": "WMT",   "name": "Walmart Inc.",            "exchange": "NYSE"}],
}

# Cache for yfinance lookups
_cache: dict = {}
_CACHE_MAX_SIZE = 200


def _search_known(query: str) -> List[dict]:
    """Check the curated company-name mapping first (instant, no network)."""
    q = query.lower().strip()
    results = []
    # Exact match
    if q in _KNOWN_COMPANIES:
        for r in _KNOWN_COMPANIES[q]:
            if r["ticker"]:  # skip private companies
                results.append(dict(r))
    # Substring match against keys
    if not results:
        for key, entries in _KNOWN_COMPANIES.items():
            if q in key or key in q:
                for r in entries:
                    if r["ticker"]:
                        results.append(dict(r))
                if len(results) >= 8:
                    break
    return results[:10]


def _search_yfinance(query: str) -> List[dict]:
    """Use yfinance's built-in search to find tickers."""
    cache_key = f"yf_{query.lower().strip()}"
    if cache_key in _cache:
        return _cache[cache_key]

    results: List[dict] = []
    try:
        import yfinance as yf

        # yfinance has a search/Ticker object that can look up by name
        search = yf.Search(query)
        quotes = search.quotes if hasattr(search, "quotes") else []

        for q in quotes[:8]:
            ticker = (q.get("symbol") or "").strip()
            name = (
                q.get("longname")
                or q.get("shortname")
                or q.get("longName")
                or q.get("shortName")
                or ticker
            )
            exchange = q.get("exchange") or q.get("exchDisp") or ""
            if ticker:
                results.append({
                    "ticker": ticker,
                    "name": name,
                    "exchange": exchange,
                })
    except Exception as e:
        logger.debug("yfinance search failed for '%s': %s", query, e)

    # Prune cache if needed
    if len(_cache) >= _CACHE_MAX_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[cache_key] = results
    return results


def _fallback_lookup(query: str) -> List[dict]:
    """Final fallback — validate a bare ticker via yfinance."""
    clean = query.strip().upper()
    if len(clean) > 10 or not all(c.isalnum() or c in ".-^" for c in clean):
        return []
    try:
        import yfinance as yf
        info = yf.Ticker(clean).info
        symbol = info.get("symbol")
        if symbol:
            return [{
                "ticker": symbol,
                "name": info.get("longName") or info.get("shortName") or clean,
                "exchange": info.get("exchange", ""),
            }]
    except Exception:
        pass
    return []


@router.get("/search/ticker", response_model=SearchResponse)
async def search_ticker(
    q: str = Query(..., min_length=1, description="Company name or ticker to search"),
):
    """Search for ticker symbols by company name or ticker.

    Uses a curated company-name mapping for instant results on well-known
    companies, then falls back to Yahoo Finance search if needed.
    """
    results: List[dict] = []

    # 1. Try the curated mapping first (instant, no network)
    results = _search_known(q)
    if results:
        logger.info("Search '%s': %d results from known-company map", q, len(results))
        return SearchResponse(results=[TickerResult(**r) for r in results])

    # 2. Try yfinance search
    results = _search_yfinance(q)
    if results:
        logger.info("Search '%s': %d results from yfinance", q, len(results))
        return SearchResponse(results=[TickerResult(**r) for r in results])

    # 3. Fallback — validate as raw ticker
    results = _fallback_lookup(q)
    if results:
        logger.info("Search '%s': validated as raw ticker", q)
        return SearchResponse(results=[TickerResult(**r) for r in results])

    logger.info("Search '%s': no results", q)
    return SearchResponse(results=[])
