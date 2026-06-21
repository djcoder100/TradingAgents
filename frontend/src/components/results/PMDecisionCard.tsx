import MarkdownRenderer from '../shared/MarkdownRenderer';

interface Props {
  content: string | null;
  signal: string;
}

export default function PMDecisionCard({ content, signal }: Props) {
  if (!content) return null;

  return (
    <div className="bg-trading-surface border border-trading-border rounded-xl overflow-hidden animate-slide-up">
      <div className="px-4 py-3 border-b border-trading-border bg-trading-emerald/5">
        <h4 className="text-sm font-semibold text-trading-text flex items-center gap-2">
          📋 Portfolio Manager Final Decision
          <span className="text-xs text-trading-textdim font-normal ml-auto">
            Signal: {signal}
          </span>
        </h4>
      </div>
      <div className="p-4 max-h-[600px] overflow-y-auto">
        <MarkdownRenderer content={content} />
      </div>
    </div>
  );
}
