import { useState } from 'react';

type TabType = 'account' | 'preferences' | 'security' | 'organization' | 'integrations' | 'exports' | 'docs';

interface SettingsSidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
}

// Colorful filled icons for settings
const Icons = {
  User: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="#3b82f6"/>
    </svg>
  ),
  Bell: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" fill="#8b5cf6"/>
    </svg>
  ),
  Shield: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z" fill="#10b981"/>
    </svg>
  ),
  Building: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z" fill="#f59e0b"/>
    </svg>
  ),
  Link: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" fill="#06b6d4"/>
    </svg>
  ),
  FileOutput: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 14h-2v-2h2v2zm0-4h-2V7h2v5zM13 9V3.5L18.5 9H13z" fill="#ec4899"/>
    </svg>
  ),
  Book: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z" fill="#6366f1"/>
    </svg>
  ),
  ChevronLeft: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
    </svg>
  ),
  ChevronRight: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
  ),
};

const TABS = [
  { id: 'account' as TabType, icon: Icons.User, label: 'Account' },
  { id: 'preferences' as TabType, icon: Icons.Bell, label: 'Preferences' },
  { id: 'security' as TabType, icon: Icons.Shield, label: 'Security' },
  { id: 'organization' as TabType, icon: Icons.Building, label: 'Organization' },
  { id: 'integrations' as TabType, icon: Icons.Link, label: 'Integrations' },
  { id: 'exports' as TabType, icon: Icons.FileOutput, label: 'Exports' },
  { id: 'docs' as TabType, icon: Icons.Book, label: 'Documentation' },
];

const SettingsSidebar = ({ activeTab, setActiveTab }: SettingsSidebarProps) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className={`
      border-r border-gray-200 flex flex-col py-3 gap-2 bg-white transition-all duration-300
      ${isCollapsed ? 'w-12 items-center' : 'w-56 items-start px-3'}
    `}>
      {/* Collapse/Expand Toggle */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className={`
          rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors mb-2
          ${isCollapsed ? 'p-2 w-auto' : 'p-2 w-full flex items-center justify-between'}
        `}
        title={isCollapsed ? 'Expand' : 'Collapse'}
      >
        {isCollapsed ? (
          <Icons.ChevronRight />
        ) : (
          <>
            <span className="text-xs font-semibold text-gray-700">Settings</span>
            <Icons.ChevronLeft />
          </>
        )}
      </button>

      {/* Divider */}
      <div className={`h-px bg-gray-200 mb-1 ${isCollapsed ? 'w-8' : 'w-full'}`}></div>

      {/* Tabs */}
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={`
            rounded-lg transition-all duration-200 group relative
            ${isCollapsed ? 'p-2' : 'p-2 w-full flex items-center gap-3'}
            ${activeTab === tab.id
              ? 'bg-gray-100 shadow-sm'
              : 'hover:bg-gray-50'
            }
          `}
        >
          <div className="flex-shrink-0">
            <tab.icon />
          </div>

          {/* Label - shown when expanded */}
          {!isCollapsed && (
            <span className={`text-xs font-medium whitespace-nowrap ${
              activeTab === tab.id ? 'text-gray-900' : 'text-gray-600'
            }`}>
              {tab.label}
            </span>
          )}

          {/* Tooltip - only shown when collapsed */}
          {isCollapsed && (
            <div className="absolute left-full ml-3 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap transition-opacity z-50">
              {tab.label}
            </div>
          )}
        </button>
      ))}
    </div>
  );
};

export default SettingsSidebar;
