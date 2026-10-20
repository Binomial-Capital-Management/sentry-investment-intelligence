/**
 * ToolSourcesPanel - Left sidebar for tool tabs, styled like the data Sources panel.
 *
 * Contains three always-visible sections:
 * 1. Tool Selector — searchable, categorized list (like EndpointBrowser)
 * 2. Data — ticker/portfolio input based on tool's inputType
 * 3. Config — ToolParamsForm + Run button
 */

import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { ToolParamsForm } from './index';
import { TickerPicker } from '@/features/canvas/shared/symbol-search';
import { GroupPicker } from '@/features/canvas/data-workspace/dataset-viewer/components/GroupPicker';
import { useToolTab } from '../hooks/useToolTab';

const CATEGORIES: Record<string, { label: string; color: string }> = {
  risk: { label: 'Risk', color: '#dc2626' },
  valuation: { label: 'Valuation', color: '#059669' },
  quant: { label: 'Quant', color: '#7c3aed' },
  analytics: { label: 'Analytics', color: '#0284c7' },
  structuring: { label: 'Structuring', color: '#0891b2' },
  alternatives: { label: 'Alternatives', color: '#d97706' },
  sentiment: { label: 'Sentiment', color: '#ec4899' },
};

const CATEGORY_KEYS = ['all', ...Object.keys(CATEGORIES)] as const;

interface ToolSourcesPanelProps {
  tabId?: string;
  /** When true, skip the outer card container — parent provides the container */
  embedded?: boolean;
}

export default function ToolSourcesPanel({ tabId, embedded }: ToolSourcesPanelProps) {
  const {
    toolState,
    update,
    tools,
    loadingTools,
    portfolios,
    loadingPortfolios,
    selectedTool,
    inputType,
    validationError,
    runningTime,
    runTool,
  } = useToolTab(tabId);

  // === Sidebar width resize ===
  const [sidebarWidth, setSidebarWidth] = useState(288);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeRef.current = { startX: e.clientX, startWidth: sidebarWidth };
  }, [sidebarWidth]);

  useEffect(() => {
    if (!isResizing) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeRef.current) return;
      const delta = e.clientX - resizeRef.current.startX;
      setSidebarWidth(Math.max(200, Math.min(500, resizeRef.current.startWidth + delta)));
    };
    const handleMouseUp = () => {
      setIsResizing(false);
      resizeRef.current = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const containerRef = useRef<HTMLDivElement>(null);

  // === Tool search & filter ===
  const [toolSearchQuery, setToolSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchOpen, setSearchOpen] = useState(false);
  const searchWrapperRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!searchOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (searchWrapperRef.current && !searchWrapperRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
        setToolSearchQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [searchOpen]);

  const filteredTools = useMemo(() => {
    let list = tools;
    if (activeCategory !== 'all') {
      list = list.filter(t => t.category === activeCategory);
    }
    if (toolSearchQuery.trim()) {
      const q = toolSearchQuery.toLowerCase();
      list = list.filter(t =>
        t.name.toLowerCase().includes(q) ||
        (t.description || '').toLowerCase().includes(q),
      );
    }
    return list;
  }, [tools, activeCategory, toolSearchQuery]);

  // === Scroll fades for tool list ===
  const toolListRef = useRef<HTMLDivElement>(null);
  const [toolFades, setToolFades] = useState({ top: false, bottom: false });

  const updateFades = useCallback(() => {
    const el = toolListRef.current;
    if (!el) return;
    setToolFades({
      top: el.scrollTop > 4,
      bottom: el.scrollHeight - el.scrollTop - el.clientHeight > 4,
    });
  }, []);

  useEffect(() => {
    updateFades();
  }, [filteredTools, updateFades]);

  // === Run button enabled ===
  const canRun = !!(toolState.toolId) && !toolState.isRunning && !validationError;

  // Inner content shared between embedded and standalone modes
  const innerContent = (
    <>
      <style>{`
        .tool-item:hover { background-color: hsl(210 10% 87% / 50%) !important; color: hsl(60 2.5% 23.3%) !important; }
        .tool-item--active:hover { background-color: hsl(30 3.3% 11.8% / 12%) !important; }
      `}</style>

      {/* Panel header — only in standalone mode (embedded uses ViewModeToggle) */}
      {!embedded && (
        <div className="px-3 flex items-center justify-between border-b border-slate-100 flex-shrink-0" style={{ height: 44 }}>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider whitespace-nowrap">Tool</span>
        </div>
      )}

      {/* Scrollable body */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col scrollbar-auto" style={{ overflowY: 'auto', overflowX: 'hidden', scrollbarGutter: 'stable' }}>

          {/* ── SECTION 1: Tool Selector (dropdown) ── */}
          <div ref={searchWrapperRef} className="flex-shrink-0 relative pt-2 pb-2" style={{ padding: '0.5rem 0.75rem' }}>
            <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', marginBottom: '0.375rem' }}>Tool</div>
            {/* Trigger button */}
            <button
              type="button"
              onClick={() => {
                setSearchOpen(!searchOpen);
                setToolSearchQuery('');
                if (!searchOpen) {
                  setTimeout(() => searchInputRef.current?.focus(), 0);
                }
              }}
              style={{
                width: '100%',
                height: 30,
                padding: '0.3rem 0.625rem',
                fontSize: '0.688rem',
                fontWeight: 500,
                textAlign: 'left' as const,
                border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                borderRadius: '0.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                color: selectedTool ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
                backgroundColor: 'white',
                cursor: 'pointer',
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                {selectedTool?.name || 'Select tool...'}
              </span>
              <svg
                style={{ width: 10, height: 10, color: 'hsl(60 2.5% 23.3% / 35%)', flexShrink: 0, transition: 'transform 0.15s ease', transform: searchOpen ? 'rotate(180deg)' : 'none' }}
                fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Dropdown panel */}
            {searchOpen && (
              <div
                className="absolute left-0 right-0 z-20 mt-1 flex flex-col"
                style={{
                  marginLeft: '0.75rem', marginRight: '0.75rem',
                  backgroundColor: 'white',
                  borderRadius: '0.75rem',
                  border: '0.5px solid hsl(30 3.3% 11.8% / 15%)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
                  height: 260,
                }}
              >
                {/* Search input inside dropdown */}
                <div className="px-3 pt-2 pb-1.5 flex-shrink-0">
                  <div className="relative">
                    <svg
                      className="absolute left-2 top-1/2 -translate-y-1/2"
                      style={{ width: 12, height: 12, color: 'hsl(60 2.5% 23.3% / 35%)' }}
                      fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      ref={searchInputRef}
                      type="text"
                      value={toolSearchQuery}
                      onChange={e => setToolSearchQuery(e.target.value)}
                      placeholder="Search..."
                      className="focus:outline-none"
                      style={{
                        width: '100%',
                        padding: '0.25rem 0.25rem 0.25rem 1.5rem',
                        fontSize: '0.625rem',
                        border: '0.5px solid hsl(30 3.3% 11.8% / 12%)',
                        borderRadius: '0.375rem',
                        color: 'hsl(60 2.5% 23.3%)',
                      }}
                    />
                  </div>
                </div>



                {/* Tool list */}
                <div className="relative flex-1 min-h-0" style={{ borderRadius: '0 0 0.75rem 0.75rem', overflow: 'hidden' }}>
                  {toolFades.top && (
                    <div className="pointer-events-none absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10" />
                  )}
                  {toolFades.bottom && (
                    <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 z-10" style={{ borderRadius: '0 0 0.75rem 0.75rem', background: 'linear-gradient(to top, white, transparent)' }} />
                  )}
                  <div
                    ref={toolListRef}
                    onScroll={updateFades}
                    className="overflow-y-auto px-3 py-1.5 flex flex-col gap-0.5 h-full"
                  >
                    {loadingTools ? (
                      <div className="flex items-center justify-center py-6">
                        <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-500 rounded-full animate-spin" />
                      </div>
                    ) : filteredTools.length === 0 ? (
                      <p style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 30%)', textAlign: 'center', padding: '1rem 0' }}>
                        No tools found
                      </p>
                    ) : (
                      filteredTools.map(tool => {
                        const isSelected = toolState.toolId === tool.id;
                        return (
                          <button
                            key={tool.id}
                            onClick={() => {
                              update({ toolId: tool.id });
                              setSearchOpen(false);
                              setToolSearchQuery('');
                            }}
                            className={`tool-item${isSelected ? ' tool-item--active' : ''}`}
                            style={{
                              width: '100%',
                              textAlign: 'left' as const,
                              padding: '0.3rem 0.5rem',
                              fontSize: '0.688rem',
                              borderRadius: '0.5rem',
                              border: isSelected ? '0.5px solid hsl(30 3.3% 11.8% / 15%)' : '0.5px solid transparent',
                              backgroundColor: isSelected ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                              color: isSelected ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 60%)',
                              cursor: 'pointer',
                              transition: 'all 0.1s ease',
                            }}
                          >
                            <span style={{
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                              fontWeight: isSelected ? 500 : 400,
                            }}>
                              {tool.name}
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── Scrollable form body (Data + Config + Run) ── */}
          <div className="flex-1 flex flex-col min-h-0 overflow-y-auto pt-1 pb-2 space-y-3" style={{ padding: '0.25rem 0.75rem 0.5rem' }}>
            {!selectedTool ? null : (
              <>
                {/* Data input */}
                {inputType === 'none' ? (
                  <div style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 35%)', fontStyle: 'italic' }}>
                    Market-wide — no input required
                  </div>
                ) : inputType === 'single_ticker' ? (
                  <div>
                    <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', marginBottom: '0.375rem' }}>Ticker</div>
                    <TickerPicker
                      mode="single"
                      selectedSymbols={toolState.manualTickers ? [toolState.manualTickers] : []}
                      onSelect={(t) => update({ manualTickers: t.symbol, selectedPortfolioId: '' })}
                      placeholder="Select ticker..."
                    />
                    {validationError && (
                      <div style={{ fontSize: '0.563rem', color: 'hsl(24 75% 45%)', marginTop: '0.25rem' }}>
                        {validationError}
                      </div>
                    )}
                  </div>
                ) : inputType === 'tickers' ? (
                  (() => {
                    const tickers = toolState.manualTickers.split(/[,\s]+/).filter(Boolean);
                    return (
                      <div>
                        <div style={{ fontSize: '0.563rem', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em', color: 'hsl(60 2.5% 23.3% / 35%)', marginBottom: '0.375rem' }}>Tickers</div>
                        <TickerPicker
                          mode="multi"
                          selectedSymbols={tickers}
                          onSelect={(t) => update({ manualTickers: [...tickers, t.symbol].join(', ') })}
                          onRemove={(sym) => update({ manualTickers: tickers.filter(x => x !== sym).join(', ') })}
                          placeholder="Select tickers..."
                          maxTickers={10}
                        />
                        {validationError && (
                          <div style={{ fontSize: '0.563rem', color: 'hsl(24 75% 45%)', marginTop: '0.25rem' }}>
                            {validationError}
                          </div>
                        )}
                      </div>
                    );
                  })()
                ) : (
                  <div>
                    {/* Portfolio list */}
                    <div style={{ maxHeight: 120, overflowY: 'auto' as const, marginBottom: '0.375rem' }}>
                      {loadingPortfolios ? (
                        <p style={{ fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 25%)' }}>Loading...</p>
                      ) : portfolios.length === 0 ? (
                        <p style={{ fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 25%)' }}>No portfolios</p>
                      ) : (
                        portfolios.map(p => (
                          <button
                            key={p.id}
                            onClick={() => update({ selectedPortfolioId: p.id, manualTickers: '' })}
                            className="tool-item"
                            style={{
                              width: '100%',
                              textAlign: 'left' as const,
                              padding: '0.25rem 0.5rem',
                              marginBottom: 2,
                              borderRadius: '0.5rem',
                              fontSize: '0.688rem',
                              border: toolState.selectedPortfolioId === p.id
                                ? '0.5px solid hsl(30 3.3% 11.8% / 15%)' : '0.5px solid transparent',
                              backgroundColor: toolState.selectedPortfolioId === p.id
                                ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                              color: 'hsl(60 2.5% 23.3%)',
                              cursor: 'pointer',
                              transition: 'all 0.1s ease',
                            }}
                          >
                            <div style={{ fontWeight: 500 }}>{p.name}</div>
                            <div style={{ fontSize: '0.563rem', color: 'hsl(60 2.5% 23.3% / 30%)' }}>
                              {p.tickers.slice(0, 4).join(', ')}{p.tickers.length > 4 && ` +${p.tickers.length - 4}`}
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                    {/* OR divider */}
                    <div className="flex items-center gap-2 my-1.5">
                      <div className="flex-1 h-px" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 8%)' }} />
                      <span style={{ fontSize: '0.5rem', color: 'hsl(60 2.5% 23.3% / 25%)' }}>or</span>
                      <div className="flex-1 h-px" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 8%)' }} />
                    </div>
                    {(() => {
                      const tickers = toolState.manualTickers.split(/[,\s]+/).filter(Boolean).map(t => t.toUpperCase());
                      return (
                        <TickerPicker
                          mode="multi"
                          selectedSymbols={tickers}
                          onSelect={(t) => update({ manualTickers: [...tickers, t.symbol].join(', '), selectedPortfolioId: '' })}
                          onRemove={(sym) => update({ manualTickers: tickers.filter(x => x !== sym).join(', '), selectedPortfolioId: '' })}
                          placeholder="Select tickers..."
                          maxTickers={20}
                        />
                      );
                    })()}
                    {validationError && !toolState.selectedPortfolioId && (
                      <div style={{ fontSize: '0.563rem', color: 'hsl(24 75% 45%)', marginTop: '0.25rem' }}>
                        {validationError}
                      </div>
                    )}
                  </div>
                )}

                {/* Group picker — where this analysis's result will be filed */}
                <div style={{ marginLeft: '-0.75rem', marginRight: '-0.75rem' }}>
                  <GroupPicker mode="analysis" />
                </div>

                {/* Config params */}
                <ToolParamsForm
                  schema={selectedTool.params_schema || {}}
                  values={toolState.toolParams}
                  onChange={(v: Record<string, any>) => update({ toolParams: v })}
                  excludeFields={['portfolio_id', 'tickers', 'weights', 'ticker', 'underlying']}
                  portfolios={portfolios}
                />
              </>
            )}

            {/* Server-side error from last run */}
            {toolState.error && (
              <div style={{
                padding: '0.5rem',
                backgroundColor: 'hsl(0 72% 97%)',
                border: '0.5px solid hsl(0 72% 90%)',
                borderRadius: '0.5rem',
                fontSize: '0.688rem', color: '#dc2626',
              }}>
                {toolState.error}
              </div>
            )}
          </div>

          {/* Run button — pinned to bottom */}
          <div className="pb-3 pt-2 flex-shrink-0" style={{ padding: '0.5rem 0.75rem 0.75rem' }}>
            <button
              onClick={() => runTool()}
              disabled={!canRun}
              style={{
                width: '100%',
                padding: '0.5rem 0',
                fontSize: '0.75rem',
                fontWeight: 600,
                backgroundColor: canRun ? 'hsl(30 3.3% 11.8% / 8%)' : 'hsl(30 3.3% 11.8% / 3%)',
                color: canRun ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 35%)',
                border: `0.5px solid hsl(30 3.3% 11.8% / ${canRun ? '20%' : '10%'})`,
                borderRadius: '0.5rem',
                cursor: !canRun ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => { if (canRun) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 12%)'; }}
              onMouseLeave={e => { if (canRun) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 8%)'; }}
            >
              {toolState.isRunning ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Running... {runningTime}s
                </>
              ) : 'Run Analysis'}
            </button>
          </div>
        </div>
      </div>

    </>
  );

  if (embedded) {
    return innerContent;
  }

  return (
    <div
      className={`flex-shrink-0 self-stretch ${isResizing ? 'select-none' : ''}`}
      style={{ width: sidebarWidth }}
    >
      <div
        ref={containerRef}
        className="flex flex-col overflow-hidden relative h-full"
        style={{
          minWidth: sidebarWidth,
          backgroundColor: 'white',
          borderRadius: '1.5rem',
          boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
          border: '1px solid hsl(30 3.3% 11.8% / 15%)',
        }}
      >
        {innerContent}

        {/* Sidebar right-edge resize handle */}
        <div
          onMouseDown={handleResizeStart}
          className="absolute top-0 bottom-0 right-0 w-2 cursor-col-resize z-10"
          style={{ transform: 'translateX(50%)' }}
          title="Drag to resize"
        />
      </div>
    </div>
  );
}
