import {
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowUpRight,
} from 'lucide-react';
import type { Signal } from '../../types/api';

const signalConfig: Record<Signal, { icon: typeof TrendingUp; bg: string; text: string; glow: string }> = {
  Buy: { icon: TrendingUp, bg: 'bg-emerald-500/15', text: 'text-emerald-400', glow: 'shadow-emerald-500/20' },
  Overweight: { icon: ArrowUpRight, bg: 'bg-emerald-400/10', text: 'text-emerald-300', glow: 'shadow-emerald-400/10' },
  Hold: { icon: Minus, bg: 'bg-amber-500/10', text: 'text-amber-400', glow: 'shadow-amber-500/10' },
  Underweight: { icon: TrendingDown, bg: 'bg-red-400/10', text: 'text-red-300', glow: 'shadow-red-400/10' },
  Sell: { icon: TrendingDown, bg: 'bg-red-500/15', text: 'text-red-400', glow: 'shadow-red-500/20' },
};

interface Props {
  signal: string;
  size?: 'sm' | 'md' | 'lg';
  pulsing?: boolean;
}

export default function SignalBadge({ signal, size = 'md', pulsing = false }: Props) {
  const cfg = signalConfig[signal as Signal] || signalConfig.Hold;
  const Icon = cfg.icon;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1 text-sm gap-1.5',
    lg: 'px-5 py-2 text-base gap-2',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ${cfg.bg} ${cfg.text} ${sizeClasses[size]} shadow-lg ${cfg.glow} ${
        pulsing ? 'animate-pulse-green' : ''
      }`}
    >
      <Icon className={size === 'lg' ? 'w-5 h-5' : 'w-3.5 h-3.5'} />
      {signal}
    </span>
  );
}
