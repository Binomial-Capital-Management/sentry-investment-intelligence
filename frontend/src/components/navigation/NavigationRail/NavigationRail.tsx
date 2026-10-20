import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore } from '@stores/uiStore';
import OrganizationSwitcher from '@components/Layout/OrganizationSwitcher';

// --- Custom Institutional SVGs ---

const Icons = {
  Home: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Roof */}
      <path d="M12 3L2 12h3v8h5v-6h4v6h5v-8h3L12 3z" fill="#dc2626"/>
      {/* Walls */}
      <path d="M5 12v8h5v-6h4v6h5v-8" fill="#fef3c7"/>
      {/* Door */}
      <rect x="10" y="14" width="4" height="6" fill="#92400e"/>
    </svg>
  ),
  Chat: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Speech bubble */}
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" fill="#3b82f6"/>
      {/* Chat dots */}
      <circle cx="8" cy="11" r="1.5" fill="#ffffff"/>
      <circle cx="12" cy="11" r="1.5" fill="#ffffff"/>
      <circle cx="16" cy="11" r="1.5" fill="#ffffff"/>
    </svg>
  ),
  Portfolio: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Briefcase body */}
      <path d="M20 7h-4V5l-2-2h-4L8 5v2H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2z" fill="#92400e"/>
      {/* Handle */}
      <rect x="10" y="5" width="4" height="2" fill="#78350f"/>
      {/* Lock/clasp */}
      <rect x="11" y="11" width="2" height="3" fill="#fbbf24"/>
    </svg>
  ),
  Tasks: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Checkmark */}
      <path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z" fill="#10b981"/>
    </svg>
  ),
  Review: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Paper */}
      <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6z" fill="#ffffff"/>
      {/* Folded corner */}
      <path d="M14 2v6h6l-6-6z" fill="#e5e7eb"/>
      {/* Text lines */}
      <rect x="8" y="12" width="8" height="1" fill="#6b7280"/>
      <rect x="8" y="15" width="8" height="1" fill="#6b7280"/>
      <rect x="8" y="18" width="5" height="1" fill="#6b7280"/>
    </svg>
  ),
  Analytics: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Trend line */}
      <path d="M2 16.59L3.41 18l6-6 4 4 6.3-6.29L22 12V6h-6l2.29 2.29-4.88 4.88-4-4z" fill="#10b981"/>
      {/* Arrow */}
      <path d="M16 6h6v6" fill="#10b981"/>
    </svg>
  ),
  Graph: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Nodes */}
      <circle cx="5" cy="12" r="3" fill="#3b82f6"/>
      <circle cx="19" cy="6" r="3" fill="#8b5cf6"/>
      <circle cx="19" cy="18" r="3" fill="#10b981"/>
      {/* Connections */}
      <path d="M7.5 10.5l8-3M7.5 13.5l8 3" stroke="#94a3b8" strokeWidth="2" fill="none"/>
    </svg>
  ),
  Settings: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Gear teeth */}
      <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58z" fill="#71717a"/>
      {/* Center */}
      <circle cx="12" cy="12" r="3" fill="#52525b"/>
    </svg>
  ),
  Marketplace: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* Product grid */}
      <rect x="3" y="3" width="7" height="7" rx="1" fill="#ef4444"/>
      <rect x="14" y="3" width="7" height="7" rx="1" fill="#3b82f6"/>
      <rect x="14" y="14" width="7" height="7" rx="1" fill="#10b981"/>
      <rect x="3" y="14" width="7" height="7" rx="1" fill="#f59e0b"/>
    </svg>
  ),
  Canvas: ({ isActive: _isActive, color: _color }: { isActive: boolean; color: string }) => (
    <svg width="20" height="20" viewBox="0 0 24 24">
      {/* 3D Cube - Front face */}
      <path d="M12 2L4 6v12l8 4 8-4V6z" fill="#a855f7"/>
      {/* Top face */}
      <path d="M12 2l8 4-8 4-8-4z" fill="#c084fc"/>
      {/* Right face */}
      <path d="M20 6v12l-8 4V10z" fill="#9333ea"/>
    </svg>
  ),
  ChevronLeft: ({ color }: { color: string }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  ),
  ChevronRight: ({ color }: { color: string }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  ),
};

const navItems: Array<{
  path: string;
  icon: ({ isActive, color }: { isActive: boolean; color: string }) => JSX.Element;
  label: string;
  color: string;
  disabled?: boolean;
}> = [
  { path: '/dashboard', icon: Icons.Home, label: 'Home', color: '#3b82f6' },
  { path: '/chat', icon: Icons.Chat, label: 'Chat', color: '#8b5cf6' },
  { path: '/portfolio', icon: Icons.Portfolio, label: 'Portfolio', color: '#059669' },
  { path: '/tasks', icon: Icons.Tasks, label: 'Tasks', color: '#10b981' },
  { path: '/review', icon: Icons.Review, label: 'Review', color: '#ef4444' },
  { path: '/market-lists', icon: Icons.Analytics, label: 'Analytics', color: '#f59e0b' },
  { path: '/canvas', icon: Icons.Canvas, label: 'Canvas', color: '#a855f7' },
  { path: '/marketplace', icon: Icons.Marketplace, label: 'Market', color: '#ef4444' },
];

const ANIM_DURATION = 200;

const NavigationRail = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const isExpanded = useUIStore((s) => s.sidebarExpanded);
  const setSidebarExpanded = useUIStore((s) => s.setSidebarExpanded);

  const [visible, setVisible] = useState(isExpanded);
  const [showState, setShowState] = useState(isExpanded); // drives the actual CSS values

  useEffect(() => {
    if (isExpanded) {
      // Mount off-screen, then slide in next frame
      setVisible(true);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setShowState(true));
      });
    } else if (visible) {
      // Slide out, then unmount
      setShowState(false);
      const t = setTimeout(() => setVisible(false), ANIM_DURATION);
      return () => clearTimeout(t);
    }
  }, [isExpanded]);

  const close = useCallback(() => setSidebarExpanded(false), [setSidebarExpanded]);

  if (!visible) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 transition-opacity"
        style={{
          background: 'rgba(0,0,0,0.2)',
          opacity: showState ? 1 : 0,
          transitionDuration: `${ANIM_DURATION}ms`,
        }}
        onClick={close}
      />

      {/* Overlay sidebar */}
      <div
        className="fixed left-0 top-0 bottom-0 w-[200px] bg-[#1a1d23] border-r border-[#2a2d35] shadow-2xl z-50 flex flex-col transition-transform"
        style={{
          transform: showState ? 'translateX(0)' : 'translateX(-100%)',
          transitionDuration: `${ANIM_DURATION}ms`,
          transitionTimingFunction: 'ease-out',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-[48px] border-b border-[#2a2d35] px-3">
          <div className="flex items-center overflow-hidden">
            <div className="w-5 h-5 relative flex-shrink-0">
              <img
                src="/binomial-icon-logo.png"
                alt="Sentry"
                className="w-full h-full object-contain"
              />
            </div>
            <span className="text-xs font-semibold text-white ml-2 whitespace-nowrap">
              Sentry
            </span>
          </div>
          <button
            onClick={() => setSidebarExpanded(false)}
            className="flex items-center justify-center w-5 h-5 rounded hover:bg-[#1F2128] text-gray-400 hover:text-white transition-colors"
          >
            <Icons.ChevronLeft color="currentColor" />
          </button>
        </div>

        {/* Workspace Switcher */}
        <div className="px-2 py-3 border-b border-[#2a2d35]">
          <OrganizationSwitcher />
        </div>

        {/* Main Navigation */}
        <div className="flex-1 flex flex-col py-2 gap-0.5 overflow-y-auto scrollbar-none">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path ||
                            (item.path === '/dashboard' && location.pathname === '/') ||
                            (item.path === '/canvas' && location.pathname.startsWith('/canvas'));
            const iconColor = isActive ? item.color : item.color + '99';

            return (
              <button
                key={item.path}
                onClick={() => { if (!item.disabled) { navigate(item.path); setSidebarExpanded(false); } }}
                disabled={item.disabled}
                className={`
                  group relative flex items-center min-h-[36px] mx-1.5 rounded-md transition-all duration-200 px-2 justify-start
                  ${item.disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-[#252830] cursor-pointer'}
                  ${isActive ? 'bg-[#252830]' : ''}
                `}
              >
                {isActive && (
                  <div
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-r-full"
                    style={{ backgroundColor: item.color }}
                  />
                )}
                <div className="flex-shrink-0">
                  <Icon isActive={isActive} color={iconColor} />
                </div>
                <span
                  className="text-xs font-medium ml-2 whitespace-nowrap"
                  style={{ color: isActive ? '#ffffff' : '#9ca3af' }}
                >
                  {item.label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Settings */}
        <div className="flex flex-col pb-3 pt-2 border-t border-[#2a2d35] px-1.5">
          <button
            onClick={() => { navigate('/settings'); setSidebarExpanded(false); }}
            className={`
              group relative flex items-center min-h-[36px] rounded-md transition-all duration-200 hover:bg-[#252830] px-2 justify-start
              ${location.pathname === '/settings' ? 'bg-[#252830]' : ''}
            `}
            title="Settings"
          >
            {location.pathname === '/settings' && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-r-full bg-gray-500" />
            )}
            <div className="flex-shrink-0">
              <Icons.Settings
                isActive={location.pathname === '/settings'}
                color={location.pathname === '/settings' ? '#ffffff' : '#6b7280'}
              />
            </div>
            <span className={`text-xs font-medium ml-2 whitespace-nowrap ${location.pathname === '/settings' ? 'text-white' : 'text-gray-400'}`}>
              Setup
            </span>
          </button>
        </div>
      </div>
    </>
  );
};

export default NavigationRail;
