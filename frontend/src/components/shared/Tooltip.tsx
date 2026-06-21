import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  maxWidth?: number;
}

export default function Tooltip({ content, children, position = 'top', maxWidth = 240 }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLSpanElement>(null);

  const show = () => {
    if (!triggerRef.current) return;
    const r = triggerRef.current.getBoundingClientRect();
    const gap = 8;
    let top = 0, left = 0;

    switch (position) {
      case 'top':
        top = r.top + window.scrollY - gap;
        left = r.left + window.scrollX + r.width / 2;
        break;
      case 'bottom':
        top = r.bottom + window.scrollY + gap;
        left = r.left + window.scrollX + r.width / 2;
        break;
      case 'left':
        top = r.top + window.scrollY + r.height / 2;
        left = r.left + window.scrollX - gap;
        break;
      case 'right':
        top = r.top + window.scrollY + r.height / 2;
        left = r.right + window.scrollX + gap;
        break;
    }
    setCoords({ top, left });
    setVisible(true);
  };

  const hide = () => setVisible(false);

  const positionClasses: Record<string, string> = {
    top:    '-translate-x-1/2 -translate-y-full',
    bottom: '-translate-x-1/2',
    left:   '-translate-x-full -translate-y-1/2',
    right:  '-translate-y-1/2',
  };

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="inline-flex items-center"
      >
        {children}
      </span>
      {visible && createPortal(
        <div
          className={`fixed z-50 pointer-events-none ${positionClasses[position]}`}
          style={{ top: coords.top, left: coords.left, maxWidth }}
        >
          <div className="bg-gray-900 border border-trading-border text-trading-textdim text-xs rounded-lg px-3 py-2 shadow-xl leading-relaxed whitespace-normal">
            {content}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
