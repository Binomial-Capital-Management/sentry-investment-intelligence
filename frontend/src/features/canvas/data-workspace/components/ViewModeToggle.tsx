/**
 * ViewModeToggle - Mode switcher for unified workspace tabs.
 *
 * Renders 4 icon buttons (Sources, Analysis, Pivot, Chart) in a horizontally
 * scrollable area with edge fades, plus a fixed collapse chevron on the right.
 */

import { useRef, useState, useEffect, useCallback } from 'react';
import { Database, FlaskConical, Grid3x3, LineChart, ChevronLeft } from 'lucide-react';
import type { WorkspaceViewMode } from '../stores/types';

const MODES: { key: WorkspaceViewMode; label: string; icon: typeof Database }[] = [
  { key: 'explorer', label: 'Sources', icon: Database },
  { key: 'tools', label: 'Analysis', icon: FlaskConical },
  { key: 'pivot', label: 'Pivot', icon: Grid3x3 },
  { key: 'chart', label: 'Chart', icon: LineChart },
];

interface ViewModeToggleProps {
  activeMode: WorkspaceViewMode;
  onModeChange: (mode: WorkspaceViewMode) => void;
  onCollapse?: () => void;
}

export default function ViewModeToggle({ activeMode, onModeChange, onCollapse }: ViewModeToggleProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showLeftFade, setShowLeftFade] = useState(false);
  const [showRightFade, setShowRightFade] = useState(false);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setShowLeftFade(el.scrollLeft > 2);
    setShowRightFade(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }, []);

  useEffect(() => {
    updateFades();
    const el = scrollRef.current;
    if (!el) return;
    const ro = new ResizeObserver(updateFades);
    ro.observe(el);
    return () => ro.disconnect();
  }, [updateFades]);

  return (
    <div className="flex items-center relative">
      {/* Scrollable mode buttons */}
      <div
        ref={scrollRef}
        className="flex-1 flex items-center gap-0.5 px-3 overflow-x-auto min-w-0"
        onScroll={updateFades}
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none', height: 44 }}
      >
        <style>{`.view-mode-scroll::-webkit-scrollbar { display: none; }`}</style>
        {MODES.map(({ key, label, icon: Icon }) => {
          const isActive = activeMode === key;
          return (
            <button
              key={key}
              onClick={() => onModeChange(key)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap"
              style={{
                backgroundColor: isActive ? 'hsl(30 3.3% 11.8% / 8%)' : 'transparent',
                color: isActive
                  ? 'hsl(30 3.3% 11.8% / 85%)'
                  : 'hsl(30 3.3% 11.8% / 45%)',
                cursor: 'pointer',
              }}
              onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)'; }}
              onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
            >
              <Icon size={13} strokeWidth={2} />
              {label}
            </button>
          );
        })}
      </div>

      {/* Left fade */}
      {showLeftFade && (
        <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-6 z-10"
          style={{ background: 'linear-gradient(to right, white, transparent)' }} />
      )}

      {/* Right fade (stops before chevron) */}
      {showRightFade && (
        <div className="pointer-events-none absolute top-0 bottom-0 w-6 z-10"
          style={{ right: onCollapse ? 44 : 0, background: 'linear-gradient(to left, white, transparent)' }} />
      )}

      {/* Collapse chevron — fixed on right, never scrolls */}
      {onCollapse && (
        <button
          onClick={onCollapse}
          className="flex items-center justify-center flex-shrink-0 px-2.5 py-1 rounded-md text-xs transition-colors mr-2"
          title="Collapse panel"
          style={{ color: 'hsl(30 3.3% 11.8% / 45%)' }}
          onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'hsl(30 3.3% 11.8% / 6%)')}
          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
        >
          <ChevronLeft size={16} strokeWidth={2} />
        </button>
      )}
    </div>
  );
}
