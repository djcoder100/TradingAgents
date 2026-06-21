import { useEffect, useCallback, useState } from 'react';
import { useAnalysisStore } from '../stores/analysisStore';
import { startAnalysis, cancelAnalysis, getTaskStatus, getTaskResult } from '../api/client';
import type { FeedMessage, ToolCall } from '../components/progress/MessageFeed';

export interface StreamedReport {
  section: string;
  agent: string;
  title: string;
  content: string;
  wall_time: number;
}

export function useSubmitAnalysis() {
  const { form, setTaskId, setTaskStatus, setResult, setError } = useAnalysisStore();

  return useCallback(async () => {
    try {
      const resp = await startAnalysis(form);
      setTaskId(resp.task_id);
      return resp.task_id;
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  }, [form, setTaskId, setTaskStatus, setResult, setError]);
}

export function useCancelAnalysis() {
  const { taskId, reset } = useAnalysisStore();

  return useCallback(async () => {
    if (!taskId) return;
    try {
      await cancelAnalysis(taskId);
    } catch {}
    reset();
  }, [taskId, reset]);
}

export function useAnalysisStream(taskId: string | null) {
  const { setTaskStatus, setResult, setError, isRunning } = useAnalysisStore();
  const [messages, setMessages] = useState<FeedMessage[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [reports, setReports] = useState<StreamedReport[]>([]);
  const [agentTimes, setAgentTimes] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!taskId || !isRunning) return;

    // Clear previous state
    setMessages([]);
    setToolCalls([]);
    setReports([]);
    setAgentTimes({});

    const es = new EventSource(`/api/analysis/${taskId}/stream`);

    es.addEventListener('message', (e) => {
      try {
        const data = JSON.parse(e.data);
        setMessages((prev) => [...prev.slice(-200), {
          type: data.type || 'system',
          content: data.content || '',
          truncated: data.truncated || false,
          timestamp: data.timestamp || new Date().toISOString(),
        }]);
      } catch {}
    });

    es.addEventListener('tool_call', (e) => {
      try {
        const data = JSON.parse(e.data);
        setToolCalls((prev) => [...prev.slice(-200), {
          name: data.name || '',
          args: data.args || '',
          timestamp: data.timestamp || new Date().toISOString(),
        }]);
      } catch {}
    });

    es.addEventListener('report', (e) => {
      try {
        const data = JSON.parse(e.data);
        setReports((prev) => {
          // Replace existing report for same section, or append
          const existing = prev.findIndex((r) => r.section === data.section);
          if (existing >= 0) {
            const updated = [...prev];
            updated[existing] = data;
            return updated;
          }
          return [...prev, data];
        });
      } catch {}
    });

    es.addEventListener('status', (e) => {
      try {
        const data = JSON.parse(e.data);
        setTaskStatus({
          task_id: taskId,
          status: 'running',
          progress: {
            agent_status: data.agent_status || {},
            reports_completed: data.reports_completed || 0,
            reports_total: data.reports_total || 0,
            llm_calls: data.llm_calls || 0,
            tool_calls: data.tool_calls || 0,
            tokens_in: data.tokens_in || 0,
            tokens_out: data.tokens_out || 0,
            elapsed_seconds: data.elapsed_seconds || 0,
            current_report_section: null,
          },
          error: null,
        });
        if (data.agent_times) {
          setAgentTimes(data.agent_times);
        }
      } catch {}
    });

    es.addEventListener('complete', async (e) => {
      try {
        const data = JSON.parse(e.data);
        es.close();
        if (data.status === 'completed') {
          const result = await getTaskResult(taskId);
          setResult(result);
        } else if (data.status === 'failed') {
          setError(data.error || 'Analysis failed');
        } else {
          setError('Analysis was cancelled');
        }
      } catch {}
    });

    es.addEventListener('error', (e) => {
      try {
        const raw = (e as MessageEvent).data;
        const data = raw ? JSON.parse(raw) : {};
        setError(data.message || 'Stream error');
      } catch {
        setError('Connection lost — retrying...');
      }
      es.close();
    });

    es.onerror = () => {
      es.close();
      const interval = setInterval(async () => {
        try {
          const status = await getTaskStatus(taskId);
          setTaskStatus(status);
          if (status.status === 'completed') {
            clearInterval(interval);
            const result = await getTaskResult(taskId);
            setResult(result);
          } else if (status.status === 'failed' || status.status === 'cancelled') {
            clearInterval(interval);
            setError(status.error || `Analysis ${status.status}`);
          }
        } catch {
          clearInterval(interval);
        }
      }, 3000);
      return () => clearInterval(interval);
    };

    return () => {
      es.close();
    };
  }, [taskId, isRunning]);

  return { messages, toolCalls, reports, agentTimes };
}
