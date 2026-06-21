import { Inbox } from 'lucide-react';

interface Props {
  title?: string;
  description?: string;
}

export default function EmptyState({
  title = 'No data',
  description = 'Nothing to display yet.',
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-trading-textdim">
      <Inbox className="w-12 h-12 mb-4 text-trading-border" />
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs mt-1">{description}</p>
    </div>
  );
}
