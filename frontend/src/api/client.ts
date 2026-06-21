/** Base API client with typed fetch wrappers. */

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail || body;
    } catch {}
    throw new Error(detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// Config
export function fetchConfig() {
  return request<import('../types/api').AppConfig>('/config');
}

export function fetchProviderModels(providerKey: string, mode: string) {
  return request<{ models: import('../types/api').ModelOption[]; supports_custom: boolean }>(
    `/providers/${providerKey}/models?mode=${mode}`
  );
}

// Analysis
export function startAnalysis(body: import('../types/api').AnalysisStartRequest) {
  return request<import('../types/api').AnalysisStartResponse>('/analysis/start', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getTaskStatus(taskId: string) {
  return request<import('../types/api').TaskStatusResponse>(`/analysis/${taskId}/status`);
}

export function getTaskResult(taskId: string) {
  return request<import('../types/api').AnalysisResultResponse>(`/analysis/${taskId}/result`);
}

export function cancelAnalysis(taskId: string) {
  return request<{ status: string; task_id: string }>(`/analysis/${taskId}`, {
    method: 'DELETE',
  });
}

// SSE stream
export function createAnalysisStream(taskId: string): EventSource {
  return new EventSource(`${BASE_URL}/analysis/${taskId}/stream`);
}

// History
export function fetchHistory(params?: {
  ticker?: string;
  offset?: number;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.ticker) searchParams.set('ticker', params.ticker);
  if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
  if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
  const qs = searchParams.toString();
  return request<import('../types/api').HistoryResponse>(`/history${qs ? `?${qs}` : ''}`);
}

export function fetchRunDetail(runId: string) {
  return request<any>(`/history/run/${runId}`);
}

export function fetchTickers() {
  return request<{ tickers: string[] }>('/history/tickers');
}

export function fetchMemoryLog() {
  return request<{ entries: import('../types/api').MemoryEntry[] }>('/history/memory');
}
