import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useHistoryStore } from '../stores/historyStore';
import SignalBadge from '../components/shared/SignalBadge';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';

export default function History() {
  const { runs, tickers, total, isLoading, error, loadHistory, loadTickers } = useHistoryStore();
  const navigate = useNavigate();
  const [searchTicker, setSearchTicker] = useState('');
  const [signalFilter, setSignalFilter] = useState('');

  useEffect(() => {
    loadHistory();
    loadTickers();
  }, []);

  const handleFilter = () => {
    loadHistory({ ticker: searchTicker || undefined });
  };

  const handleRunClick = (runId: string) => {
    navigate(`/history/run/${runId}`);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-lg font-bold text-trading-text">History</h1>
        <p className="text-sm text-trading-textdim mt-1">
          Browse past analysis runs and their outcomes
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="flex-1 flex items-center gap-2 bg-trading-surface border border-trading-border rounded-lg px-3 py-2">
          <Search className="w-4 h-4 text-trading-textdim" />
          <input
            type="text"
            value={searchTicker}
            onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
            placeholder="Filter by ticker..."
            className="bg-transparent text-sm text-trading-text placeholder:text-trading-border focus:outline-none flex-1"
            onKeyDown={(e) => e.key === 'Enter' && handleFilter()}
          />
        </div>
        <select
          value={signalFilter}
          onChange={(e) => {
            setSignalFilter(e.target.value);
            loadHistory({ offset: 0 });
          }}
          className="bg-trading-surface border border-trading-border rounded-lg px-3 py-2 text-sm text-trading-text focus:outline-none focus:border-trading-emerald"
        >
          <option value="">All Signals</option>
          <option value="Buy">Buy</option>
          <option value="Overweight">Overweight</option>
          <option value="Hold">Hold</option>
          <option value="Underweight">Underweight</option>
          <option value="Sell">Sell</option>
        </select>
        <button
          onClick={handleFilter}
          className="px-4 py-2 bg-trading-emerald text-trading-bg rounded-lg text-sm font-medium hover:bg-trading-emerald/90 transition-colors cursor-pointer"
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      {/* Loading */}
      {isLoading && <LoadingSpinner label="Loading history..." />}

      {/* Error */}
      {error && (
        <div className="bg-trading-red/10 border border-trading-red/30 rounded-lg p-4 text-sm text-trading-red">
          {error}
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && runs.length === 0 && (
        <EmptyState
          title="No history yet"
          description="Run your first analysis to see results here."
        />
      )}

      {/* Runs table */}
      {runs.length > 0 && (
        <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-trading-border text-xs text-trading-textdim uppercase tracking-wide">
                  <th className="text-left px-4 py-3 font-medium">Ticker</th>
                  <th className="text-left px-4 py-3 font-medium">Date</th>
                  <th className="text-left px-4 py-3 font-medium">Signal</th>
                  <th className="text-left px-4 py-3 font-medium">Return</th>
                  <th className="text-left px-4 py-3 font-medium">Alpha</th>
                  <th className="text-left px-4 py-3 font-medium">Reflection</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.run_id}
                    onClick={() => handleRunClick(run.run_id)}
                    className="border-b border-trading-border/50 hover:bg-trading-surface2/50 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <span className="text-sm font-semibold text-trading-text">{run.ticker}</span>
                      {run.asset_type === 'crypto' && (
                        <span className="ml-2 px-1.5 py-0.5 rounded text-xs bg-trading-amber/10 text-trading-amber">
                          crypto
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-trading-textdim">{run.analysis_date}</td>
                    <td className="px-4 py-3">
                      <SignalBadge signal={run.signal} size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      {run.raw_return ? (
                        <span
                          className={`text-sm font-mono ${
                            parseFloat(run.raw_return) >= 0 ? 'text-trading-green' : 'text-trading-red'
                          }`}
                        >
                          {parseFloat(run.raw_return) >= 0 ? '+' : ''}
                          {run.raw_return}
                        </span>
                      ) : (
                        <span className="text-sm text-trading-textdim">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {run.alpha_return ? (
                        <span
                          className={`text-sm font-mono ${
                            parseFloat(run.alpha_return) >= 0 ? 'text-trading-green' : 'text-trading-red'
                          }`}
                        >
                          {parseFloat(run.alpha_return) >= 0 ? '+' : ''}
                          {run.alpha_return}
                        </span>
                      ) : (
                        <span className="text-sm text-trading-textdim">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {run.has_reflection ? (
                        <span className="text-xs text-trading-green">✓</span>
                      ) : (
                        <span className="text-xs text-trading-textdim">pending</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination info */}
          <div className="px-4 py-3 border-t border-trading-border flex items-center justify-between text-xs text-trading-textdim">
            <span>
              Showing {runs.length} of {total} runs
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
