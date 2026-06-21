import ReportCard from './ReportCard';
import type { AnalysisResultFinalState } from '../../types/api';

interface Props {
  state: AnalysisResultFinalState;
}

export default function AnalystReportsGrid({ state }: Props) {
  const reports = [
    { key: 'market_report', title: 'Market Analysis', content: state.market_report, icon: '📊' },
    { key: 'sentiment_report', title: 'Sentiment Analysis', content: state.sentiment_report, icon: '💬' },
    { key: 'news_report', title: 'News Analysis', content: state.news_report, icon: '📰' },
    { key: 'fundamentals_report', title: 'Fundamentals Analysis', content: state.fundamentals_report, icon: '📈' },
  ].filter((r) => r.content);

  if (reports.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {reports.map((r) => (
        <ReportCard key={r.key} title={r.title} content={r.content} icon={r.icon} />
      ))}
    </div>
  );
}
