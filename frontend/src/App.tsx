import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import AppShell from './components/layout/AppShell';
import Dashboard from './pages/Dashboard';
import AnalysisDetail from './pages/AnalysisDetail';
import History from './pages/History';
import Status from './pages/Status';
import Logs from './pages/Logs';
import Competition from './pages/Competition';
import CompetitionAnalysis from './pages/CompetitionAnalysis';
import { useConfigStore } from './stores/configStore';

export default function App() {
  const loadConfig = useConfigStore((s) => s.loadConfig);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="analysis/:taskId" element={<AnalysisDetail />} />
          <Route path="history" element={<History />} />
          <Route path="history/run/:runId" element={<AnalysisDetail />} />
          <Route path="status" element={<Status />} />
          <Route path="logs" element={<Logs />} />
          <Route path="competition" element={<Competition />} />
          <Route path="competition/analysis/:analysisId" element={<CompetitionAnalysis />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
