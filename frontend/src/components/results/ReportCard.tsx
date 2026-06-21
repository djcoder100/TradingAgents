import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import MarkdownRenderer from '../shared/MarkdownRenderer';

interface Props {
  title: string;
  content: string | null;
  icon?: string;
}

export default function ReportCard({ title, content, icon }: Props) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden animate-slide-up">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between border-b border-trading-border hover:bg-trading-surface2/50 transition-colors cursor-pointer"
      >
        <h4 className="text-sm font-semibold text-trading-text flex items-center gap-2">
          {icon && <span>{icon}</span>}
          {title}
        </h4>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-trading-textdim" />
        ) : (
          <ChevronDown className="w-4 h-4 text-trading-textdim" />
        )}
      </button>

      {expanded && (
        <div className="p-4 max-h-96 overflow-y-auto">
          {content ? (
            <MarkdownRenderer content={content} />
          ) : (
            <p className="text-xs text-trading-textdim italic">No report available</p>
          )}
        </div>
      )}
    </div>
  );
}
