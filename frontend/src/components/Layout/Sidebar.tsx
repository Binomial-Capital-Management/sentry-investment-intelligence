import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore } from '@stores/uiStore';
import { useChatStore } from '@stores/chatStore';
import { Home, Compass, Box, Sparkles, Download, LayoutGrid } from 'lucide-react';
import clsx from 'clsx';

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isHovering, setIsHovering] = useState(false);
  const [isCreatingThread, setIsCreatingThread] = useState(false);
  const { sidebarExpanded } = useUIStore();
  const { threads, currentThreadId, createNewThread } = useChatStore();

  const expanded = sidebarExpanded || isHovering;

  const handleNewThread = async () => {
    if (isCreatingThread) return; // Prevent double-click

    setIsCreatingThread(true);
    try {
      // Create new thread and wait for completion
      await createNewThread();
      navigate('/');
    } finally {
      setIsCreatingThread(false);
    }
  };

  // Group threads by date
  const groupedThreads = threads.reduce((acc, thread) => {
    const date = new Date(thread.updatedAt);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    let group = 'Older';
    if (date.toDateString() === today.toDateString()) {
      group = 'Today';
    } else if (date.toDateString() === yesterday.toDateString()) {
      group = 'Yesterday';
    }

    if (!acc[group]) acc[group] = [];
    acc[group].push(thread);
    return acc;
  }, {} as Record<string, typeof threads>);

  return (
    <div
      className={clsx(
        'fixed left-0 top-0 h-full transition-all duration-300 z-50',
        expanded ? 'w-60' : 'w-[72px]',
      )}
      style={{
        background: 'var(--bg-base)',
        borderRight: '1px solid var(--border-light)',
      }}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Fixed Section */}
      <div className="p-4">
        <div className="flex items-center justify-center mb-6">
          <img
            src="/binomial-icon-logo.png"
            alt="Sentry"
            className="w-8 h-8"
          />
        </div>

        <button
          onClick={handleNewThread}
          disabled={isCreatingThread}
          className={clsx(
            'w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-200 text-white',
            isCreatingThread ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105',
          )}
          style={{
            background: 'var(--gradient-primary)',
          }}
          title="New Thread"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 4v16m8-8H4" />
          </svg>
        </button>

        <div className="mt-6 space-y-2">
          <SidebarButton icon="home" label="Home" onClick={() => navigate('/')} isActive={location.pathname === '/'} />
          <SidebarButton icon="discover" label="Discover" />
          <SidebarButton icon="spaces" label="Spaces" onClick={() => navigate('/canvas')} isActive={location.pathname.startsWith('/canvas')} />
          <SidebarButton icon="marketplace" label="Marketplace" onClick={() => navigate('/marketplace')} isActive={location.pathname === '/marketplace'} />
        </div>
      </div>

      {/* Expandable Section */}
      {expanded && (
        <div className="pl-[72px] pr-4 animate-fade-in">
          <div className="mb-4">
            <button
              onClick={handleNewThread}
              disabled={isCreatingThread}
              className={clsx(
                'w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                isCreatingThread && 'opacity-50 cursor-not-allowed',
              )}
              style={{
                color: 'var(--text-primary)',
                background: 'var(--accent-subtle)',
                border: '1px solid var(--accent)',
              }}
              onMouseEnter={(e) => {
                if (!isCreatingThread) {
                  e.currentTarget.style.transform = 'translateX(2px)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateX(0)';
              }}
            >
              + New Thread
            </button>
          </div>

          {/* Thread Groups */}
          {Object.entries(groupedThreads).map(([group, groupThreads]) => (
            <div key={group} className="mb-4">
              <h3 className="text-xs font-semibold uppercase px-3 mb-2 tracking-wider"
                  style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
                {group}
              </h3>
              <div className="space-y-1">
                {groupThreads.map((thread) => (
                  <button
                    key={thread.id}
                    onClick={() => navigate(`/thread/${thread.id}`)}
                    className={clsx(
                      'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                    )}
                    style={{
                      color: thread.id === currentThreadId ? 'var(--text-primary)' : 'var(--text-secondary)',
                      background: thread.id === currentThreadId ? 'color-mix(in oklab, var(--bg-subtle), white 4%)' : 'transparent',
                      border: thread.id === currentThreadId ? '1px solid var(--border)' : '1px solid transparent',
                    }}
                  >
                    <div className="truncate">{thread.title}</div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bottom Section */}
      <div className="absolute bottom-0 left-0 right-0 p-4" style={{ borderTop: '1px solid var(--border)' }}>
        <SidebarButton icon="upgrade" label="Upgrade" showBadge />
        <SidebarButton icon="install" label="Install" />
      </div>
    </div>
  );
};

// Helper component for sidebar buttons
const SidebarButton = ({
  icon,
  label,
  onClick,
  showBadge = false,
  isActive = false,
}: {
  icon: string;
  label: string;
  onClick?: () => void;
  showBadge?: boolean;
  isActive?: boolean;
}) => {
  const getIconColor = () => {
    switch (icon) {
      case 'home': return '#3b82f6'; // Blue
      case 'discover': return '#a855f7'; // Purple
      case 'spaces': return '#10b981'; // Green
      case 'marketplace': return '#ef4444'; // Red
      case 'upgrade': return '#f59e0b'; // Amber
      case 'install': return '#6b7280'; // Gray
      default: return '#6b7280';
    }
  };

  const getIcon = () => {
    const iconColor = isActive ? getIconColor() : 'currentColor';
    const iconSize = 20;

    switch (icon) {
      case 'home':
        return <Home size={iconSize} color={iconColor} />;
      case 'discover':
        return <Compass size={iconSize} color={iconColor} />;
      case 'spaces':
        return <Box size={iconSize} color={iconColor} />;
      case 'marketplace':
        return <LayoutGrid size={iconSize} color={iconColor} />;
      case 'upgrade':
        return <Sparkles size={iconSize} color={iconColor} />;
      case 'install':
        return <Download size={iconSize} color={iconColor} />;
      default:
        return null;
    }
  };

  const [isHovered, setIsHovered] = useState(false);

  return (
    <button
      onClick={onClick}
      className="relative w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-200"
      style={{
        background: isActive
          ? `color-mix(in srgb, ${getIconColor()} 10%, transparent)`
          : 'transparent',
        color: isActive ? getIconColor() : 'var(--text-secondary)',
      }}
      onMouseEnter={(e) => {
        setIsHovered(true);
        if (!isActive) {
          e.currentTarget.style.background = 'var(--bg-hover)';
        }
      }}
      onMouseLeave={(e) => {
        setIsHovered(false);
        if (!isActive) {
          e.currentTarget.style.background = 'transparent';
        }
      }}
      title={label}
    >
      <div style={{
        color: isActive || isHovered ? getIconColor() : 'currentColor',
        transition: 'color 0.2s',
      }}>
        {getIcon()}
      </div>
      {showBadge && (
        <span className="absolute top-0 right-0 w-2 h-2 rounded-full"
              style={{ background: getIconColor() }} />
      )}
    </button>
  );
};

export default Sidebar;
