import { useEffect, useRef } from 'react';
import { Brain, Wrench, User, Activity } from 'lucide-react';

export interface FeedMessage {
  type: 'agent' | 'tool' | 'user' | 'control' | 'system';
  content: string;
  truncated?: boolean;
  timestamp: string;
}

export interface ToolCall {
  name: string;
  args: string;
  timestamp: string;
}

interface Props {
  messages: FeedMessage[];
  toolCalls: ToolCall[];
  maxMessages?: number;
}

const typeConfig = {
  agent: { icon: Brain, color: 'text-trading-accent', bg: 'bg-trading-accent/5', label: 'Agent' },
  tool: { icon: Wrench, color: 'text-trading-amber', bg: 'bg-trading-amber/5', label: 'Tool' },
  user: { icon: User, color: 'text-trading-textdim', bg: 'bg-trading-bg', label: 'User' },
  control: { icon: Activity, color: 'text-trading-textdim', bg: 'bg-trading-bg', label: 'Control' },
  system: { icon: Activity, color: 'text-trading-green', bg: 'bg-trading-green/5', label: 'System' },
};

export default function MessageFeed({ messages, toolCalls, maxMessages = 100 }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, toolCalls.length]);

  // Combine messages and tool calls into a single feed, sorted by timestamp
  const feed: Array<{ type: 'message' | 'tool_call'; data: FeedMessage | ToolCall; ts: string }> = [];
  for (const m of messages.slice(-maxMessages)) {
    feed.push({ type: 'message', data: m, ts: m.timestamp });
  }
  for (const tc of toolCalls.slice(-maxMessages)) {
    feed.push({ type: 'tool_call', data: tc, ts: tc.timestamp });
  }
  feed.sort((a, b) => a.ts.localeCompare(b.ts));

  if (feed.length === 0) {
    return (
      <div className="text-xs text-trading-textdim text-center py-4">
        Waiting for analysis to begin...
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="max-h-64 overflow-y-auto space-y-1.5 p-2">
      {feed.map((item, i) => {
        if (item.type === 'message') {
          const msg = item.data as FeedMessage;
          const cfg = typeConfig[msg.type] || typeConfig.system;
          const Icon = cfg.icon;
          return (
            <div key={`msg-${i}`} className={`flex items-start gap-2 px-2 py-1.5 rounded-md ${cfg.bg} text-xs`}>
              <Icon className={`w-3.5 h-3.5 ${cfg.color} shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <span className={`font-medium ${cfg.color} mr-1`}>{cfg.label}:</span>
                <span className="text-trading-text leading-relaxed break-words">
                  {msg.content.slice(0, 300)}
                  {msg.truncated && '…'}
                </span>
              </div>
            </div>
          );
        } else {
          const tc = item.data as ToolCall;
          return (
            <div key={`tc-${i}`} className="flex items-start gap-2 px-2 py-1.5 rounded-md bg-trading-amber/5 text-xs">
              <Wrench className="w-3.5 h-3.5 text-trading-amber shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-trading-amber mr-1">Calling:</span>
                <span className="text-trading-text">{tc.name}</span>
                <span className="text-trading-textdim ml-1">{tc.args.slice(0, 120)}</span>
              </div>
            </div>
          );
        }
      })}
    </div>
  );
}
