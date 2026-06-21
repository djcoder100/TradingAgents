import { AlertTriangle, X } from 'lucide-react';

interface Props {
  open: boolean;
  title: string;
  message: string;
  warnings?: string[];
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning';
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  warnings,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'warning',
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;

  const colors = variant === 'danger'
    ? { border: 'border-trading-red/50', bg: 'bg-trading-red/10', text: 'text-trading-red', btn: 'bg-trading-red hover:bg-trading-red/80' }
    : { border: 'border-trading-amber/50', bg: 'bg-trading-amber/10', text: 'text-trading-amber', btn: 'bg-trading-amber hover:bg-trading-amber/80' };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />

      {/* Dialog */}
      <div className={`relative ${colors.bg} ${colors.border} border rounded-xl max-w-md w-full mx-4 p-6 shadow-2xl animate-slide-up`}>
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle className={`w-5 h-5 ${colors.text} shrink-0 mt-0.5`} />
          <div>
            <h3 className="text-sm font-semibold text-trading-text">{title}</h3>
            <p className="text-xs text-trading-textdim mt-1">{message}</p>
          </div>
          <button onClick={onCancel} className="ml-auto text-trading-textdim hover:text-trading-text cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Warnings */}
        {warnings && warnings.length > 0 && (
          <div className="mb-4 p-3 bg-trading-bg rounded-lg">
            <p className="text-xs font-medium text-trading-textdim mb-1.5">Warnings:</p>
            <ul className="space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="text-xs text-trading-textdim flex items-start gap-1.5">
                  <span className="text-trading-amber mt-0.5">•</span>
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-xs font-medium border border-trading-border text-trading-textdim hover:text-trading-text hover:border-trading-textdim transition-colors cursor-pointer"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-xs font-medium text-white ${colors.btn} transition-colors cursor-pointer`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
