import { useEffect, useState } from 'react';
import { Server, CheckCircle, XCircle, Clock, Activity } from 'lucide-react';

export default function Status() {
  const [health, setHealth] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    const startTime = Date.now();

    const check = async () => {
      try {
        const resp = await fetch('/api/health');
        const data = await resp.json();
        setHealth(data);
        setError(null);
        setUptime(Math.floor((Date.now() - startTime) / 1000));
      } catch (err: any) {
        setError(err.message);
      }
    };

    check();
    const interval = setInterval(check, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-lg font-bold text-trading-text">Service Status</h1>
        <p className="text-sm text-trading-textdim mt-1">
          Backend health and runtime metrics
        </p>
      </div>

      {/* Status card */}
      <div className="bg-trading-surface border border-trading-border rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
            health ? 'bg-trading-green/10' : 'bg-trading-red/10'
          }`}>
            {health ? (
              <CheckCircle className="w-6 h-6 text-trading-green" />
            ) : (
              <XCircle className="w-6 h-6 text-trading-red" />
            )}
          </div>
          <div>
            <h2 className="text-sm font-semibold text-trading-text">
              {health ? 'All Systems Operational' : 'Service Unavailable'}
            </h2>
            <p className="text-xs text-trading-textdim">
              {health ? 'The API backend is healthy and responding' : error || 'Cannot reach the backend'}
            </p>
          </div>
        </div>

        {health && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-trading-bg rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Server className="w-3.5 h-3.5 text-trading-accent" />
                <span className="text-xs text-trading-textdim">API Version</span>
              </div>
              <span className="text-sm font-mono text-trading-text">{health.version}</span>
            </div>
            <div className="bg-trading-bg rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Activity className="w-3.5 h-3.5 text-trading-green" />
                <span className="text-xs text-trading-textdim">Status</span>
              </div>
              <span className="text-sm font-mono text-trading-green">{health.status}</span>
            </div>
            <div className="bg-trading-bg rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-3.5 h-3.5 text-trading-amber" />
                <span className="text-xs text-trading-textdim">Session Uptime</span>
              </div>
              <span className="text-sm font-mono text-trading-text">{uptime}s</span>
            </div>
            <div className="bg-trading-bg rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Server className="w-3.5 h-3.5 text-trading-textdim" />
                <span className="text-xs text-trading-textdim">Endpoint</span>
              </div>
              <span className="text-xs font-mono text-trading-text">localhost:8000</span>
            </div>
          </div>
        )}
      </div>

      {/* Endpoints reference */}
      <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-trading-border">
          <h3 className="text-sm font-semibold text-trading-text">API Endpoints</h3>
        </div>
        <div className="divide-y divide-trading-border text-xs">
          {[
            ['GET', '/api/health', 'Health check'],
            ['GET', '/api/config', 'Configuration & providers'],
            ['GET', '/api/providers/{key}/models', 'Model listing'],
            ['POST', '/api/analysis/start', 'Start analysis'],
            ['GET', '/api/analysis/{id}/status', 'Task status'],
            ['GET', '/api/analysis/{id}/stream', 'SSE progress stream'],
            ['GET', '/api/analysis/{id}/result', 'Full result'],
            ['DELETE', '/api/analysis/{id}', 'Cancel task'],
            ['GET', '/api/history', 'Past runs'],
            ['GET', '/api/history/memory', 'Memory log'],
            ['GET', '/api/search/ticker', 'Ticker search'],
          ].map(([method, path, desc]) => (
            <div key={path} className="px-4 py-2 flex items-center gap-3">
              <span className={`font-mono font-semibold w-14 ${
                method === 'GET' ? 'text-trading-green' :
                method === 'POST' ? 'text-trading-accent' :
                method === 'DELETE' ? 'text-trading-red' : 'text-trading-textdim'
              }`}>{method}</span>
              <span className="font-mono text-trading-text flex-1">{path}</span>
              <span className="text-trading-textdim">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
