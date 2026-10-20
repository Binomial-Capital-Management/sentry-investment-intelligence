import { useEffect, useState } from 'react';
import { Activity, Bug } from 'lucide-react';
import UserMenu from './UserMenu';
import BugReportModal from '@components/BugReport/BugReportModal';
import { useUIStore } from '@stores/uiStore';

const SystemBar = () => {
  const sidebarExpanded = useUIStore((s) => s.sidebarExpanded);
  const setSidebarExpanded = useUIStore((s) => s.setSidebarExpanded);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'down'>('healthy');
  const [environment] = useState<string>(
    (import.meta as any).env?.MODE === 'production' ? 'PROD' : 'DEV',
  );
  const [isBugReportOpen, setIsBugReportOpen] = useState(false);

  // Update time every second
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Health check with more frequent polling for institutional requirements
  useEffect(() => {
    let mounted = true;
    const ping = async () => {
      const start = performance.now();
      try {
        const base = (import.meta as any).env?.VITE_API_BASE || '';
        const res = await fetch(`${base}/v6/health`, { cache: 'no-store' });
        const ms = Math.max(1, Math.round(performance.now() - start));
        if (!mounted) return;
        setLatencyMs(ms);
        setStatus(res.ok ? (ms > 500 ? 'degraded' : 'healthy') : 'down');
      } catch {
        if (!mounted) return;
        setLatencyMs(null);
        setStatus('down');
      }
    };
    ping();
    const id = setInterval(ping, 15000); // 15s intervals for real-time monitoring
    return () => { mounted = false; clearInterval(id); };
  }, []);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: '2-digit',
      year: 'numeric',
    });
  };

  const getStatusColor = () => {
    switch (status) {
      case 'healthy': return '#107C10';
      case 'degraded': return '#FFB900';
      case 'down': return '#D13438';
      default: return 'var(--text-muted)';
    }
  };

  const getEnvironmentColor = () => {
    return environment === 'PROD' ? '#D13438' : '#0078D4';
  };

  return (
    <div
      className="flex items-center justify-center px-3 relative"
      style={{
        width: '100%',
        height: '48px',
        background: '#FFFFFF',
        borderBottom: '1px solid #E1DFDD',
        fontSize: '12px',
      }}
    >
      {/* Sentry icon — visible when nav is collapsed */}
      {!sidebarExpanded && (
        <button
          onClick={() => setSidebarExpanded(true)}
          className="absolute left-3 flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 transition-colors"
          title="Open navigation"
        >
          <img
            src="/binomial-icon-logo.png"
            alt="Sentry"
            className="w-5 h-5 object-contain"
          />
        </button>
      )}

      {/* Center Section - Compact Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1">
          <div
            className="w-2 h-2 rounded-full"
            style={{ background: getEnvironmentColor() }}
          />
          <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>
            {environment}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <Activity size={10} style={{ color: getStatusColor() }} />
          <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </span>
        </div>

        <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>
          {latencyMs !== null ? `${latencyMs}ms` : 'unknown'}
        </span>
      </div>

      {/* Right Section - Bug Report, Time, and User */}
      <div className="flex items-center gap-3 absolute right-3">
        <button
          onClick={() => setIsBugReportOpen(true)}
          className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
          style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}
          title="Report a Bug"
        >
          <Bug size={14} />
          <span className="hidden sm:inline">Report Bug</span>
        </button>
        <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>
          {formatTime(currentTime)}
        </span>
        <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)' }}>
          {formatDate(currentTime).toUpperCase()}
        </span>
        <UserMenu />
      </div>

      {/* Bug Report Modal */}
      <BugReportModal isOpen={isBugReportOpen} onClose={() => setIsBugReportOpen(false)} />
    </div>
  );
};

export default SystemBar;
