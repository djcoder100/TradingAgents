import { create } from 'zustand';
import type {
  AnalysisStartRequest,
  TaskStatusResponse,
  AnalysisResultResponse,
} from '../types/api';

interface AnalysisState {
  // Form state
  form: AnalysisStartRequest;

  // Active analysis
  taskId: string | null;
  taskStatus: TaskStatusResponse | null;
  result: AnalysisResultResponse | null;
  isRunning: boolean;
  error: string | null;

  // Actions
  setForm: (partial: Partial<AnalysisStartRequest>) => void;
  resetForm: () => void;
  setTaskId: (id: string | null) => void;
  setTaskStatus: (status: TaskStatusResponse) => void;
  setResult: (result: AnalysisResultResponse) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const defaultForm: AnalysisStartRequest = {
  ticker: 'SPY',
  analysis_date: new Date().toISOString().slice(0, 10),
  output_language: 'English',
  analysts: ['market', 'social', 'news', 'fundamentals'],
  research_depth: 1,
  llm_provider: 'openai',
  backend_url: null,
  quick_think_llm: 'gpt-5.4-mini',
  deep_think_llm: 'gpt-5.5',
  google_thinking_level: null,
  openai_reasoning_effort: null,
  anthropic_effort: null,
  temperature: null,
};

export const useAnalysisStore = create<AnalysisState>((set) => ({
  form: { ...defaultForm, analysis_date: new Date().toISOString().slice(0, 10) },

  taskId: null,
  taskStatus: null,
  result: null,
  isRunning: false,
  error: null,

  setForm: (partial) =>
    set((s) => ({ form: { ...s.form, ...partial } })),

  resetForm: () =>
    set({ form: { ...defaultForm, analysis_date: new Date().toISOString().slice(0, 10) } }),

  setTaskId: (id) => set({ taskId: id, isRunning: id !== null }),

  setTaskStatus: (status) => set({ taskStatus: status }),

  setResult: (result) =>
    set({ result, isRunning: false, taskStatus: null }),

  setError: (error) =>
    set({ error, isRunning: false }),

  reset: () =>
    set({
      taskId: null,
      taskStatus: null,
      result: null,
      isRunning: false,
      error: null,
    }),
}));
