import { useEffect, useState, useRef } from 'react';
import { ScrollText, Trash2, Pause, Play } from 'lucide-react';

interface LogEntry {
  id: number;
  timestamp: string;
  level: string;
  message: string;
}

const levelColors: Record<string, string> = {
  INFO: 'text-trading-accent',
  WARNING: 'text-trading-amber',
  ERROR: 'text-trading-red',
  DEBUG: 'text-trading-textdim',
};

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);

  // Fetch recent logs from the analysis stream events
  useEffect(() => {
    const interval = setInterval(async () => {
      if (paused) return;
      try {
        const resp = await fetch('/api/history');
        const data = await resp.json();

        // Log the API access
        idRef.current += 1;
        const entry: LogEntry = {
          id: idRef.current,
          timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
          level: data.items ? 'INFO' : 'WARNING',
          message: `History API returned ${data.total || 0} runs`,
        };

        setLogs((prev) => [...prev.slice(-500), entry]);
      } catch (err: any) {
        idRef.current += 1;
        setLogs((prev) => [...prev.slice(-500), {
          id: idRef.current,
          timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
          level: 'ERROR',
          message: `Failed to reach backend: ${err.message}`,
        }]);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [paused]);

  // Auto-scroll
  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, paused]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-trading-text">Log Viewer</h1>
          <p className="text-sm text-trading-textdim mt-1">
            Real-time backend activity — check the server terminal for full output
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPaused(!paused)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
              paused
                ? 'bg-trading-amber/10 border-trading-amber/30 text-trading-amber'
                : 'bg-trading-surface border-trading-border text-trading-textdim hover:text-trading-text'
            }`}
          >
            {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            onClick={() => setLogs([])}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-trading-border text-trading-textdim hover:text-trading-red transition-colors cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </button>
        </div>
      </div>

      {/* Log output */}
      <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-trading-border flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-trading-textdim" />
          <span className="text-sm font-semibold text-trading-text">Application Log</span>
          <span className="text-xs text-trading-textdim ml-auto">{logs.length} entries</span>
        </div>
        <div
          ref={scrollRef}
          className="max-h-[600px] overflow-y-auto font-mono text-xs leading-relaxed"
        >
          {logs.length === 0 ? (
            <div className="p-8 text-center text-trading-textdim">
              <ScrollText className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>No log entries yet. Backend logs appear in the server terminal.</p>
              <p className="mt-1">Run <code className="bg-trading-bg px-1.5 py-0.5 rounded">uv run uvicorn web.main:app</code> to see full output.</p>
            </div>
          ) : (
            logs.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start gap-3 px-4 py-1.5 hover:bg-trading-surface2/50 border-b border-trading-border/30"
              >
                <span className="text-trading-textdim shrink-0">{entry.timestamp}</span>
                <span className={`font-semibold shrink-0 w-16 ${levelColors[entry.level] || 'text-trading-textdim'}`}>
                  {entry.level}
                </span>
                <span className="text-trading-text break-all">{entry.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
