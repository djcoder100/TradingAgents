export default function LoadingSpinner({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-trading-textdim">
      <div className="w-8 h-8 border-2 border-trading-border border-t-trading-emerald rounded-full animate-spin mb-3" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
