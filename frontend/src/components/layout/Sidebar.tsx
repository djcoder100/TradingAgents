import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Clock,
  Activity,
  ScrollText,
  ChevronLeft,
  ChevronRight,
  BarChart3,
  Trophy,
} from 'lucide-react';
import { useUIStore } from '../../stores/uiStore';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/competition', icon: Trophy, label: 'Competition' },
  { to: '/history', icon: Clock, label: 'History' },
  { to: '/status', icon: Activity, label: 'Status' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
];

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={`fixed left-0 top-0 h-full bg-trading-surface border-r border-trading-border z-30 transition-all duration-200 flex flex-col ${
        sidebarCollapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-trading-border shrink-0">
        <div className="w-8 h-8 rounded-lg bg-trading-emerald flex items-center justify-center shrink-0">
          <BarChart3 className="w-5 h-5 text-trading-bg" />
        </div>
        {!sidebarCollapsed && (
          <span className="font-semibold text-sm tracking-wide">
            BRV Trading
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-trading-emerald/10 text-trading-emerald'
                  : 'text-trading-textdim hover:text-trading-text hover:bg-trading-surface2'
              }`
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            {!sidebarCollapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="p-3 border-t border-trading-border text-trading-textdim hover:text-trading-text transition-colors cursor-pointer"
      >
        {sidebarCollapsed ? (
          <ChevronRight className="w-5 h-5 mx-auto" />
        ) : (
          <ChevronLeft className="w-5 h-5 mx-auto" />
        )}
      </button>
    </aside>
  );
}
