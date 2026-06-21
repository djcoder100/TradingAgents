import { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';
import { useAnalysisStore } from '../../stores/analysisStore';

interface SearchResult {
  ticker: string;
  name: string;
  exchange: string;
}

export default function TickerInput() {
  const { form, setForm } = useAnalysisStore();
  const [query, setQuery] = useState(form.ticker);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setQuery(form.ticker);
  }, [form.ticker]);

  const doSearch = async (q: string) => {
    if (q.length < 1) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const resp = await fetch(`/api/search/ticker?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      setResults(data.results || []);
      setShowDropdown(true);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleInputChange = (value: string) => {
    setQuery(value);
    setForm({ ticker: value.toUpperCase() });

    // Debounce search
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 400);
  };

  const handleSelect = (result: SearchResult) => {
    setQuery(result.ticker);
    setForm({ ticker: result.ticker });
    setShowDropdown(false);
    setResults([]);
  };

  const handleClear = () => {
    setQuery('');
    setForm({ ticker: '' });
    setResults([]);
    setShowDropdown(false);
  };

  const isCrypto = form.ticker.toUpperCase().endsWith('-USD') ||
    form.ticker.toUpperCase().endsWith('-USDT') ||
    form.ticker.toUpperCase().endsWith('-USDC') ||
    form.ticker.toUpperCase().endsWith('-BTC') ||
    form.ticker.toUpperCase().endsWith('-ETH');

  return (
    <div className="relative">
      <label className="block text-xs font-medium text-trading-textdim mb-1.5">
        Ticker or Company Name
      </label>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-trading-textdim" />
        <input
          type="text"
          value={query}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => results.length > 0 && setShowDropdown(true)}
          placeholder="AAPL, Apple, 0700.HK, BTC-USD"
          className="w-full bg-trading-surface border border-trading-border rounded-lg pl-9 pr-8 py-2 text-sm text-trading-text placeholder:text-trading-border focus:outline-none focus:border-trading-emerald transition-colors"
          maxLength={64}
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-trading-textdim hover:text-trading-text cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Search results dropdown */}
      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full bg-trading-surface border border-trading-border rounded-lg shadow-2xl overflow-hidden">
          {searching && (
            <div className="px-3 py-2 text-xs text-trading-textdim">
              Searching...
            </div>
          )}
          {!searching && results.length === 0 && query.length >= 2 && (
            <div className="px-3 py-2 text-xs text-trading-textdim">
              No results — typing as a ticker will be used directly
            </div>
          )}
          {results.map((r) => (
            <button
              key={r.ticker}
              onClick={() => handleSelect(r)}
              className="w-full text-left px-3 py-2 hover:bg-trading-surface2 transition-colors flex items-center justify-between cursor-pointer"
            >
              <span>
                <span className="text-sm font-semibold text-trading-text">{r.ticker}</span>
                <span className="text-xs text-trading-textdim ml-2">{r.name}</span>
              </span>
              {r.exchange && (
                <span className="text-xs text-trading-textdim bg-trading-bg px-1.5 py-0.5 rounded">
                  {r.exchange}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Close dropdown on outside click */}
      {showDropdown && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowDropdown(false)}
        />
      )}

      {isCrypto && (
        <p className="text-xs text-trading-amber mt-1">
          Crypto asset detected — Fundamentals analyst will be excluded
        </p>
      )}
    </div>
  );
}
