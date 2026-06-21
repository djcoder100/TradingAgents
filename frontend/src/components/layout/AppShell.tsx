import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import { useUIStore } from '../../stores/uiStore';

export default function AppShell() {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);

  return (
    <div className="min-h-screen bg-trading-bg">
      <Sidebar />
      <div
        className={`transition-all duration-200 ${
          sidebarCollapsed ? 'ml-16' : 'ml-56'
        }`}
      >
        <TopBar />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
