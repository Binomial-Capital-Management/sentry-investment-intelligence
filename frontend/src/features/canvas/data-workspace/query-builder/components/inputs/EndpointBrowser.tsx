/**
 * EndpointBrowser - Category tree for browsing and selecting endpoints
 * Extracted from SingleObjectForm lines 634-697
 */

import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import type { EndpointInfo } from '@/features/canvas/types';
import { getSourceColor, getSourceLabel } from '../../utils/queryUtils';

const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const FONT_MONO = "'SF Mono', 'Cascadia Code', 'JetBrains Mono', 'Roboto Mono', monospace";

interface EndpointBrowserProps {
  loading: boolean;
  endpointsByCategory: Record<string, EndpointInfo[]>;
  expandedCategories: Set<string>;
  onToggleCategory: (category: string) => void;
  selectedEndpoint: EndpointInfo | null;
  onEndpointSelect: (ep: EndpointInfo) => void;
  emptyMessage?: string;
  /** Endpoints already added to workspace - will be highlighted */
  addedEndpoints?: Set<string>;
  /** Initial scroll position to restore on mount */
  initialScrollPosition?: number;
  /** Callback when scroll position changes (debounced internally) */
  onScrollChange?: (position: number) => void;
}

export default function EndpointBrowser({
  loading,
  endpointsByCategory,
  expandedCategories,
  onToggleCategory,
  selectedEndpoint,
  onEndpointSelect,
  emptyMessage = 'No endpoints found',
  addedEndpoints = new Set(),
  initialScrollPosition = 0,
  onScrollChange,
}: EndpointBrowserProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const updateFades = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    setShowTopFade(el.scrollTop > 2);
    setShowBottomFade(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
  }, []);

  // Restore scroll position on mount
  useEffect(() => {
    if (scrollContainerRef.current && initialScrollPosition > 0) {
      scrollContainerRef.current.scrollTop = initialScrollPosition;
    }
    // Check fades after mount / restore
    requestAnimationFrame(updateFades);
  }, []); // Only run on mount

  // Recheck fades when content changes
  useEffect(() => {
    requestAnimationFrame(updateFades);
  }, [endpointsByCategory, searchQuery, expandedCategories, updateFades]);

  // Debounced scroll handler
  const handleScroll = useCallback(() => {
    updateFades();

    if (!onScrollChange) return;

    // Clear existing timeout
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    // Debounce: wait 100ms before reporting scroll position
    scrollTimeoutRef.current = setTimeout(() => {
      if (scrollContainerRef.current) {
        onScrollChange(scrollContainerRef.current.scrollTop);
      }
    }, 100);
  }, [onScrollChange, updateFades]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  // Filter endpoints based on search query
  const filteredEndpointsByCategory = useMemo(() => {
    if (!searchQuery.trim()) return endpointsByCategory;
    
    const query = searchQuery.toLowerCase();
    const filtered: Record<string, EndpointInfo[]> = {};
    
    for (const [category, endpoints] of Object.entries(endpointsByCategory)) {
      const matchingEndpoints = endpoints.filter(ep => 
        ep.endpoint.toLowerCase().includes(query) ||
        category.toLowerCase().includes(query)
      );
      if (matchingEndpoints.length > 0) {
        filtered[category] = matchingEndpoints;
      }
    }
    return filtered;
  }, [endpointsByCategory, searchQuery]);

  // Auto-expand all categories when searching
  const effectiveExpandedCategories = searchQuery.trim() 
    ? new Set(Object.keys(filteredEndpointsByCategory))
    : expandedCategories;

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <style>{`
.ep-browser-item:hover { background-color: hsl(210 10% 87% / 50%) !important; color: hsl(60 2.5% 23.3%) !important; }
.ep-browser-item--active:hover { background-color: hsl(30 3.3% 11.8% / 12%) !important; }
      `}</style>
      {/* Search bar — static, never scrolls */}
      <div className="px-4 pb-2 pt-1 flex-shrink-0 bg-white">
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: 'hsl(60 2.5% 23.3% / 35%)' }} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search endpoints..."
            className="w-full pl-8 pr-8 py-1.5 text-xs rounded-lg focus:outline-none focus:ring-0"
            style={{ border: '0.5px solid hsl(30 3.3% 11.8% / 20%)', fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif", color: 'hsl(60 2.5% 23.3%)' }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="relative flex-1 min-h-0 overflow-hidden">
        {/* Top fade */}
        {showTopFade && (
          <div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white to-transparent z-10 pointer-events-none" />
        )}

        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto px-4 pb-4"
        >
        {loading ? null : Object.keys(filteredEndpointsByCategory).length === 0 ? (
          <div style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 35%)', padding: '1rem 0', textAlign: 'center', fontFamily: FONT_UI }}>
            {searchQuery ? 'No matching endpoints' : emptyMessage}
          </div>
        ) : (
          Object.entries(filteredEndpointsByCategory).map(([category, endpoints]) => (
            <div key={category} style={{ marginBottom: '0.5rem' }}>
              <button
                onClick={() => onToggleCategory(category)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.375rem 0',
                  fontSize: '0.688rem',
                  fontWeight: 500,
                  fontFamily: FONT_UI,
                  color: 'hsl(60 2.5% 23.3% / 75%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <svg className={`w-3 h-3 transition-transform ${effectiveExpandedCategories.has(category) ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                {category}
                <span style={{ color: 'hsl(60 2.5% 23.3% / 30%)', fontWeight: 400 }}>({endpoints.length} endpoints)</span>
              </button>
              {effectiveExpandedCategories.has(category) && (
                <div style={{ marginLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {endpoints.map((ep) => {
                    const isSelected = selectedEndpoint?.endpoint === ep.endpoint;
                    const isAdded = addedEndpoints.has(ep.endpoint);
                    const isHighlighted = isSelected || isAdded;
                    return (
                      <button
                        key={`${ep.source}-${ep.endpoint}`}
                        onClick={() => onEndpointSelect(ep)}
                        className={`ep-browser-item${isHighlighted ? ' ep-browser-item--active' : ''}`}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          padding: '0.375rem 0.5rem',
                          fontSize: '0.688rem',
                          fontFamily: FONT_UI,
                          borderRadius: '0.5rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '0.5rem',
                          border: isHighlighted ? '0.5px solid hsl(30 3.3% 11.8% / 15%)' : '0.5px solid transparent',
                          backgroundColor: isHighlighted ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                          color: isHighlighted ? 'hsl(60 2.5% 23.3%)' : 'hsl(60 2.5% 23.3% / 60%)',
                          cursor: 'pointer',
                          transition: 'all 0.1s ease',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', minWidth: 0, flex: 1 }}>
                          <span className={`text-[8px] px-1 py-0.5 rounded font-medium flex-shrink-0 ${getSourceColor(ep.source, isHighlighted)}`}>
                            {getSourceLabel(ep.source)}
                          </span>
                          <span style={{ fontFamily: FONT_MONO, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ep.endpoint}</span>
                        </div>
                        <span style={{ fontSize: '0.563rem', flexShrink: 0, color: isHighlighted ? 'hsl(60 2.5% 23.3% / 30%)' : 'hsl(60 2.5% 23.3% / 25%)' }}>
                          {ep.fields.length} fields
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          ))
        )}
        </div>

        {/* Bottom fade */}
        {showBottomFade && (
          <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-white to-transparent z-10 pointer-events-none" />
        )}
      </div>
    </div>
  );
}
