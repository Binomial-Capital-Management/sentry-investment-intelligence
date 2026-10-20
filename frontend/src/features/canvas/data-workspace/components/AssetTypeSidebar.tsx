/**
 * Sidebar - Dark sidebar with object types and portfolios
 * Includes type-specific icons and collapsed state support
 */

import { OBJECT_TYPES } from '@/features/canvas/types';
import type { ObjectTypeResult, Portfolio } from '@/features/canvas/types';

// SVG icons for each object type - Colorful filled icons matching legacy
const typeIcons: Record<string, JSX.Element> = {
  equity: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <path d="M3 13h2v8H3v-8zm4-6h2v14H7V7zm4-4h2v18h-2V3zm4 8h2v10h-2V11zm4-3h2v13h-2V8z" fill="#10b981"/>
    </svg>
  ),
  etf: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <rect x="3" y="3" width="7" height="7" rx="1" fill="#3b82f6"/>
      <rect x="14" y="3" width="7" height="7" rx="1" fill="#3b82f6"/>
      <rect x="3" y="14" width="7" height="7" rx="1" fill="#3b82f6"/>
      <rect x="14" y="14" width="7" height="7" rx="1" fill="#3b82f6"/>
    </svg>
  ),
  crypto: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="9" fill="#f59e0b"/>
      <path d="M12 6v2m0 8v2m-4-6h8" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  forex: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <circle cx="9" cy="12" r="6" fill="#8b5cf6"/>
      <circle cx="15" cy="12" r="6" fill="#ec4899" opacity="0.8"/>
    </svg>
  ),
  commodity: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#f59e0b" strokeWidth="2" fill="none"/>
    </svg>
  ),
  macro_series: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <path d="M2 20h20M5 20V10l5-5 4 4 6-6v17" stroke="#ef4444" strokeWidth="2" fill="none"/>
    </svg>
  ),
  index: (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      <path d="M3 13h2v8H3v-8zm4-6h2v14H7V7zm4-4h2v18h-2V3zm4 8h2v10h-2V11zm4-3h2v13h-2V8z" fill="#3b82f6"/>
    </svg>
  ),
};

// Collapsed state vertical icons
const collapsedTypeIcons: Record<string, JSX.Element> = {
  equity: <span className="text-[8px] font-bold text-gray-400">EQ</span>,
  etf: <span className="text-[8px] font-bold text-gray-400">ETF</span>,
  crypto: <span className="text-[8px] font-bold text-orange-400">₿</span>,
  forex: <span className="text-[8px] font-bold text-green-400">FX</span>,
  commodity: <span className="text-[8px] font-bold text-amber-400">CMD</span>,
  macro_series: <span className="text-[8px] font-bold text-purple-400">MAC</span>,
  index: <span className="text-[8px] font-bold text-blue-400">IDX</span>,
};

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchResults: ObjectTypeResult[];
  onAddObject: (result: ObjectTypeResult | { symbol: string }, forceType?: string | null) => void;
  browsingType: string | null;
  onSetBrowsingType: (type: string | null) => void;
  onSetTypeFilter: (type: string | null) => void;
  expandedCategory: string | null;
  onSetExpandedCategory: (category: string | null) => void;
  portfolios: Portfolio[];
  loadingPortfolios: boolean;
  workspaceObjects: Array<{ symbol: string; name?: string; objectType: string }>;
  onAddWorkspaceObject: (obj: { symbol: string; objectType: string }) => void;
  onResetWorkspace: () => void;
}

export default function Sidebar({
  collapsed,
  onToggleCollapse,
  searchQuery,
  onSearchChange,
  searchResults,
  onAddObject,
  browsingType,
  onSetBrowsingType,
  onSetTypeFilter,
  expandedCategory,
  onSetExpandedCategory,
  portfolios,
  loadingPortfolios,
  workspaceObjects,
  onAddWorkspaceObject,
  onResetWorkspace,
}: SidebarProps) {
  return (
    <div className={`${collapsed ? 'w-12' : 'w-56'} bg-[#1a1d23] border-r border-[#2a2d35] flex flex-col transition-all duration-200`}>
      {/* Collapse toggle */}
      <button
        onClick={onToggleCollapse}
        className="p-3 border-b border-[#2a2d35] flex items-center justify-center hover:bg-[#252830] transition-colors"
      >
        <svg className={`w-4 h-4 text-gray-400 transition-transform ${collapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"/>
        </svg>
      </button>

      {/* Collapsed state - vertical icons */}
      {collapsed && (
        <div className="flex-1 flex flex-col items-center py-2 gap-1">
          {/* Type icons */}
          {OBJECT_TYPES.slice(0, 6).map((type) => (
            <button
              key={type.id}
              onClick={() => {
                onSetBrowsingType(type.id);
                onSetTypeFilter(type.id);
              }}
              className={`w-8 h-8 rounded flex items-center justify-center transition-colors ${
                browsingType === type.id 
                  ? 'bg-[#252830] text-white' 
                  : 'text-gray-500 hover:bg-[#252830] hover:text-gray-300'
              }`}
              title={type.name}
            >
              {typeIcons[type.id] || collapsedTypeIcons[type.id] || (
                <div className="w-3 h-3 rounded bg-gray-600" />
              )}
            </button>
          ))}
          
          <div className="w-6 h-px bg-[#2a2d35] my-1" />
          
          {/* Portfolio icon */}
          <button
            onClick={() => onSetExpandedCategory(expandedCategory === 'portfolios' ? null : 'portfolios')}
            className={`w-8 h-8 rounded flex items-center justify-center transition-colors ${
              expandedCategory === 'portfolios' 
                ? 'bg-[#252830] text-white' 
                : 'text-gray-500 hover:bg-[#252830] hover:text-gray-300'
            }`}
            title="Portfolios"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/>
            </svg>
          </button>
          
          {/* Count badge */}
          {workspaceObjects.length > 0 && (
            <div className="mt-auto mb-2 w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center">
              <span className="text-[9px] font-bold text-white">{workspaceObjects.length}</span>
            </div>
          )}
        </div>
      )}

      {!collapsed && (
        <>
          {/* Search */}
          <div className="p-3 border-b border-[#2a2d35]">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQuery.length >= 1) {
                    e.preventDefault();
                    onAddObject({ symbol: searchQuery }, browsingType);
                  }
                }}
                placeholder="Add symbol..."
                className="w-full px-3 py-2 pl-8 bg-[#252830] border border-[#2a2d35] rounded text-xs text-white placeholder:text-gray-500 focus:outline-none focus:border-gray-500 font-mono"
              />
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
              </svg>
            </div>
            {searchResults.length > 0 && (
              <div className="absolute z-30 left-3 right-3 mt-1 bg-[#252830] border border-[#2a2d35] rounded shadow-xl max-h-48 overflow-auto">
                {searchResults.map((result) => (
                  <button
                    key={result.symbol}
                    onClick={() => onAddObject(result)}
                    className="w-full px-3 py-2 text-left hover:bg-[#1a1d23] flex items-center justify-between text-xs border-b border-[#2a2d35] last:border-0"
                  >
                    <span className="font-mono font-medium text-white">{result.symbol}</span>
                    <span className="text-[10px] text-gray-500">{result.object_type || 'Equity'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Object Types */}
          <div className="border-b border-[#2a2d35]">
            <button
              onClick={() => onSetExpandedCategory(expandedCategory === 'types' ? null : 'types')}
              className="w-full px-3 py-2.5 flex items-center justify-between text-left hover:bg-[#252830] transition-colors"
            >
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Object Types</span>
              <svg className={`w-3.5 h-3.5 text-gray-500 transition-transform ${expandedCategory === 'types' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            {expandedCategory === 'types' && (
              <div className="px-2 pb-2 space-y-0.5">
                {OBJECT_TYPES.map((type) => (
                  <button
                    key={type.id}
                    onClick={() => {
                      onSetBrowsingType(type.id);
                      onSetTypeFilter(type.id);
                    }}
                    className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded text-left transition-colors ${
                      browsingType === type.id ? 'bg-[#252830] text-white' : 'text-gray-400 hover:bg-[#252830] hover:text-gray-200'
                    }`}
                  >
                    <span className={browsingType === type.id ? 'text-blue-400' : 'text-gray-500'}>
                      {typeIcons[type.id] || <div className="w-4 h-4 rounded bg-gray-600" />}
                    </span>
                    <span className="text-xs font-medium">{type.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Portfolios */}
          <div className="flex-1 overflow-auto">
            <button
              onClick={() => onSetExpandedCategory(expandedCategory === 'portfolios' ? null : 'portfolios')}
              className="w-full px-3 py-2.5 flex items-center justify-between text-left hover:bg-[#252830] transition-colors"
            >
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/>
                </svg>
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Your Portfolios</span>
              </div>
              <svg className={`w-3.5 h-3.5 text-gray-500 transition-transform ${expandedCategory === 'portfolios' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            {expandedCategory === 'portfolios' && (
              <div className="px-2 pb-2">
                {loadingPortfolios ? (
                  <div className="px-2 py-4 text-center">
                    <div className="w-4 h-4 border-2 border-gray-600 border-t-gray-400 rounded-full animate-spin mx-auto" />
                  </div>
                ) : portfolios.length === 0 ? (
                  <div className="px-2 py-4 text-center text-[10px] text-gray-600">No portfolios</div>
                ) : (
                  <div className="space-y-0.5">
                    {portfolios.map(p => (
                      <button
                        key={p.id}
                        onClick={() => {
                          p.tickers.forEach(t => {
                            if (!workspaceObjects.some(o => o.symbol === t)) {
                              onAddWorkspaceObject({ symbol: t, objectType: 'equity' });
                            }
                          });
                        }}
                        className="w-full flex items-center justify-between px-2 py-1.5 rounded text-left text-gray-400 hover:bg-[#252830] hover:text-gray-200 transition-colors group"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <svg className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/>
                          </svg>
                          <span className="text-xs font-medium truncate">{p.name}</span>
                        </div>
                        <span className="text-[10px] text-gray-600 group-hover:text-gray-500 flex-shrink-0 ml-2">{p.tickers.length}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Selected count */}
          {workspaceObjects.length > 0 && (
            <div className="px-3 py-2 border-t border-[#2a2d35] bg-[#252830]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                    <span className="text-[9px] font-bold text-white">{workspaceObjects.length}</span>
                  </span>
                  <span className="text-[10px] text-gray-400">selected</span>
                </div>
                <button onClick={onResetWorkspace} className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors">
                  Clear
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
