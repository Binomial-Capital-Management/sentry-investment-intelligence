import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Plus, X } from 'lucide-react';
import type { WorkspaceTab } from '../stores/dataWorkspaceStore';
import { useUIStore } from '@stores/uiStore';
import {
  TAB_STANDARD_WIDTH,
  BOUNDS_ANIMATION_MS,
} from './tab-bar/chromeTabConstants';
import { useGlowHover } from './tab-bar/useGlowHover';
import { useSeparatorOpacity } from './tab-bar/useSeparatorOpacity';
import './tab-bar/chromeTab.css';

interface TabBarProps {
  workspaceTabs: WorkspaceTab[];
  activeTabId: string | null;
  addWorkspaceTab: (type: 'single' | 'multi' | 'compare', name: string) => string;
  setActiveWorkspaceTab: (id: string) => void;
  renameTab: (id: string, name: string) => void;
  reorderTabs: (fromIndex: number, toIndex: number) => void;
  removeTab: (id: string) => void;
  renamingTabId: string | null;
  setRenamingTabId: (id: string | null) => void;
  renamingTabName: string;
  setRenamingTabName: (name: string) => void;
  openNewTab: () => void;
  /** @deprecated No longer used — unified tabs handle pivot/chart via viewMode toggle */
  setShowPivotSheetSelector?: (show: boolean) => void;
  /** @deprecated No longer used — unified tabs handle pivot/chart via viewMode toggle */
  setShowChartCreator?: (show: boolean) => void;
  /** @deprecated No longer used — unified tabs handle tools via viewMode toggle */
  openToolTab?: () => void;
  workspaceMenuSlot?: React.ReactNode;
  rightSlot?: React.ReactNode;
}

// --- Animations (tab_container_impl.cc:1117 — 200ms BoundsAnimator) ---

function animateTabClose(el: HTMLElement): Promise<void> {
  return new Promise((resolve) => {
    const w = el.getBoundingClientRect().width;
    const anim = el.animate(
      {
        maxWidth: [`${w}px`, '0px'],
        opacity: ['1', '0'],
        paddingLeft: [getComputedStyle(el).paddingLeft, '0px'],
        paddingRight: [getComputedStyle(el).paddingRight, '0px'],
      },
      { duration: BOUNDS_ANIMATION_MS, easing: 'ease-out', fill: 'forwards' },
    );
    anim.onfinish = () => resolve();
    anim.oncancel = () => resolve();
  });
}

function animateTabOpen(el: HTMLElement) {
  el.animate(
    { maxWidth: ['0px', `${TAB_STANDARD_WIDTH}px`], opacity: ['0', '1'] },
    { duration: BOUNDS_ANIMATION_MS, easing: 'ease-out', fill: 'forwards' },
  );
}

export default function TabBar({
  workspaceTabs, activeTabId, addWorkspaceTab, setActiveWorkspaceTab,
  renameTab, reorderTabs, removeTab,
  renamingTabId, setRenamingTabId, renamingTabName, setRenamingTabName,
  openNewTab,
  workspaceMenuSlot, rightSlot,
}: TabBarProps) {
  const isDraggingRef = useRef(false);
  const [hoveredTabId, setHoveredTabId] = useState<string | null>(null);
  /**
   * Tab closing mode — tab_container_impl.cc:702-727
   * When true, tab widths are frozen so close buttons don't shift position.
   * Exited when mouse leaves the strip (with 40px vertical slop — line 1446).
   */
  const [inTabCloseMode, setInTabCloseMode] = useState(false);
  const frozenTabWidth = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const rightSlotRef = useRef<HTMLDivElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  // Glow hover — glow_hover_controller.cc
  const glow = useGlowHover();

  // Separator opacity — tab_style_views.cc:727-836
  const tabStates = useMemo(() =>
    workspaceTabs.map(tab => ({
      isActive: tab.id === activeTabId,
      isHovered: tab.id === hoveredTabId,
    })),
    [workspaceTabs, activeTabId, hoveredTabId],
  );
  const separatorOpacities = useSeparatorOpacity(tabStates);

  // --- Open/close animation state ---
  const tabRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const prevTabIds = useRef<Set<string>>(new Set());
  const closingTabs = useRef<Set<string>>(new Set());
  const hasRenderedOnce = useRef(false);

  useEffect(() => {
    const currentIds = new Set(workspaceTabs.map(t => t.id));
    for (const tab of workspaceTabs) {
      if (!prevTabIds.current.has(tab.id) && hasRenderedOnce.current) {
        const el = tabRefs.current.get(tab.id);
        if (el) animateTabOpen(el);
      }
    }
    prevTabIds.current = currentIds;
    hasRenderedOnce.current = true;
  }, [workspaceTabs]);

  const handleAnimatedClose = useCallback(async (id: string) => {
    if (closingTabs.current.has(id)) return;
    closingTabs.current.add(id);

    // EnterTabClosingMode (tab_container_impl.cc:702-727)
    // Freeze tab widths so close buttons stay in place during rapid closing
    if (containerRef.current) {
      const tabEls = containerRef.current.querySelectorAll<HTMLElement>('.chrome-tab');
      if (tabEls.length > 0 && !frozenTabWidth.current) {
        frozenTabWidth.current = tabEls[0].getBoundingClientRect().width;
      }
      setInTabCloseMode(true);
    }

    const el = tabRefs.current.get(id);
    if (el) await animateTabClose(el);
    closingTabs.current.delete(id);
    tabRefs.current.delete(id);
    removeTab(id);
  }, [removeTab]);

  /**
   * Chrome-style drag via mousedown/mousemove/mouseup.
   *
   * Direct DOM manipulation during drag (no React re-renders on mousemove).
   * Positions are snapshotted at drag start so transforms never contaminate
   * swap detection. A 5px threshold distinguishes clicks from drags.
   */
  const handleMouseDown = useCallback((e: React.MouseEvent, index: number) => {
    if (e.button !== 0) return;
    if (renamingTabId === workspaceTabs[index]?.id) return;

    const container = containerRef.current;
    if (!container) return;

    setActiveWorkspaceTab(workspaceTabs[index].id);

    const startX = e.clientX;
    const tabEls = Array.from(container.querySelectorAll<HTMLElement>('.chrome-tab'));

    // Compute effective zoom: getBoundingClientRect is in viewport space,
    // but translateX operates in local (zoomed) space
    const zoom = tabEls[0].getBoundingClientRect().width / tabEls[0].offsetWidth || 1;

    // Snapshot untransformed positions at drag start (viewport space)
    const slots = tabEls.map(el => {
      const r = el.getBoundingClientRect();
      return { left: r.left, width: r.width, mid: r.left + r.width / 2 };
    });

    let dragging = false;
    let insertAt = index;
    let rafId: number | null = null;

    const applyTransforms = (offset: number) => {
      // Convert viewport-space offset to local-space for transforms
      const localOffset = offset / zoom;
      const localShift = slots[index].width / zoom;
      tabEls.forEach((el, i) => {
        if (i === index) {
          el.style.transform = `translateX(${localOffset}px)`;
        } else {
          let shift = 0;
          if (index < insertAt && i > index && i <= insertAt) shift = -localShift;
          else if (index > insertAt && i >= insertAt && i < index) shift = localShift;
          el.style.transform = shift ? `translateX(${shift}px)` : '';
        }
      });
    };

    const handleMouseMove = (ev: MouseEvent) => {
      let dx = ev.clientX - startX;

      // 5px drag threshold
      if (!dragging) {
        if (Math.abs(dx) < 5) return;
        dragging = true;
        isDraggingRef.current = true;
        tabEls[index]?.classList.add('chrome-tab--dragging');
        tabEls.forEach((el, i) => {
          if (i !== index) el.classList.add('chrome-tab--shifting');
        });
      }

      // Clamp within tab strip bounds
      const draggedLeft = slots[index].left + dx;
      const draggedRight = draggedLeft + slots[index].width;
      const boundsLeft = slots[0].left;
      const boundsRight = slots[slots.length - 1].left + slots[slots.length - 1].width;
      if (draggedLeft < boundsLeft) dx = boundsLeft - slots[index].left;
      else if (draggedRight > boundsRight) dx = boundsRight - slots[index].left - slots[index].width;

      // Swap detection: dragged tab's leading edge vs snapshotted midpoints
      const dragLeft = slots[index].left + dx;
      const dragRight = dragLeft + slots[index].width;
      let newInsert = index;
      // Rightward: iterate forward, last match wins (furthest crossed midpoint)
      for (let i = index + 1; i < slots.length; i++) {
        if (dragRight > slots[i].mid) newInsert = i;
        else break;
      }
      // Leftward: iterate backward, last match wins (furthest crossed midpoint)
      for (let i = index - 1; i >= 0; i--) {
        if (dragLeft < slots[i].mid) newInsert = i;
        else break;
      }
      insertAt = newInsert;

      if (rafId !== null) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => applyTransforms(dx));
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (rafId !== null) cancelAnimationFrame(rafId);

      // Clean up DOM
      tabEls.forEach(el => {
        el.style.transform = '';
        el.classList.remove('chrome-tab--dragging', 'chrome-tab--shifting');
      });

      if (dragging && insertAt !== index) {
        reorderTabs(index, insertAt);
      }

      // Reset after click event fires (click fires synchronously after mouseup)
      if (dragging) {
        requestAnimationFrame(() => { isDraggingRef.current = false; });
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [renamingTabId, workspaceTabs, reorderTabs, setActiveWorkspaceTab]);

  // Wheel scroll
  useEffect(() => {
    const c = containerRef.current;
    if (!c) return;
    const h = (e: WheelEvent) => { if (c.scrollWidth > c.clientWidth) { e.preventDefault(); c.scrollLeft += e.deltaY || e.deltaX; } };
    c.addEventListener('wheel', h, { passive: false });
    return () => c.removeEventListener('wheel', h);
  }, []);

  const sidebarExpanded = useUIStore(s => s.sidebarExpanded);
  const setSidebarExpanded = useUIStore(s => s.setSidebarExpanded);

  /**
   * MouseMovedOutOfHost (tab_container_impl.cc:1077) → ResizeLayoutTabs (line 1384)
   * When mouse leaves strip (+40px vertical slop), exit closing mode and
   * let tabs resize to natural width via AnimateToIdealBounds.
   */
  const handleStripMouseLeave = useCallback(() => {
    if (inTabCloseMode) {
      setInTabCloseMode(false);
      frozenTabWidth.current = null;
    }
  }, [inTabCloseMode]);

  return (
    <div
      ref={stripRef}
      className="chrome-tab-strip"
      style={{ paddingLeft: 8, paddingRight: 8, gap: 4 }}
      onMouseLeave={handleStripMouseLeave}
    >
      {!sidebarExpanded && (
        <button onClick={() => setSidebarExpanded(true)} className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded hover:bg-black/10 transition-colors" style={{ alignSelf: 'center' }} title="Open navigation">
          <img src="/binomial-icon-logo.png" alt="Sentry" className="w-5 h-5 object-contain" />
        </button>
      )}

      {workspaceMenuSlot && <div className="flex-shrink-0" style={{ alignSelf: 'center' }}>{workspaceMenuSlot}</div>}
      {workspaceMenuSlot && <div className="w-px h-4 flex-shrink-0" style={{ alignSelf: 'center', background: 'var(--ct-divider)' }} />}

      <div ref={containerRef} className="chrome-tab-strip-scroll">
        <button
          onClick={openNewTab}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full transition-colors hover:bg-black/10 mx-1" title="Add new tab"
          style={{ alignSelf: 'center', color: 'var(--ct-inactive-text)' }}
        >
          <Plus className="w-3.5 h-3.5" />
        </button>

        {workspaceTabs.map((tab, index) => {
          const isActive = tab.id === activeTabId;

          return (
            <div
              key={tab.id}
              ref={el => { if (el) { tabRefs.current.set(tab.id, el); glow.ref(el); } }}
              onMouseDown={e => handleMouseDown(e, index)}
              onMouseEnter={e => { if (!isDraggingRef.current) { setHoveredTabId(tab.id); glow.onMouseEnter(e); } }}
              onMouseLeave={e => { if (!isDraggingRef.current) { setHoveredTabId(null); glow.onMouseLeave(e); } }}
              onMouseMove={!isDraggingRef.current ? glow.onMouseMove : undefined}
              title={tab.name.length > 10 ? tab.name : undefined}
              className={[
                'chrome-tab',
                isActive && 'chrome-tab--active',
              ].filter(Boolean).join(' ')}
              style={{
                // Tab closing mode: freeze width (tab_container_impl.cc:710-718)
                ...(inTabCloseMode && frozenTabWidth.current ? {
                  flex: '0 0 auto',
                  width: frozenTabWidth.current,
                  maxWidth: frozenTabWidth.current,
                } : {}),
              }}
              onClick={() => { if (!isDraggingRef.current) setActiveWorkspaceTab(tab.id); }}
            >
              {/* Glow overlay — glow_hover_controller.cc */}
              {!isActive && <div className="chrome-tab-glow" />}

              {/* Separator — tab_style.cc:21-24 */}
              {index < workspaceTabs.length - 1 && (
                <div className="chrome-tab-separator" style={{ opacity: separatorOpacities[index] ?? 1 }} />
              )}

              {/* Favicon removed — tabs have no icon */}

              {/* Title — layout_constants.cc:99 kTabPreTitlePadding=8 */}
              {renamingTabId === tab.id ? (
                <input
                  type="text" value={renamingTabName}
                  onChange={e => setRenamingTabName(e.target.value)}
                  onBlur={() => { if (renamingTabName.trim()) renameTab(tab.id, renamingTabName.trim()); setRenamingTabId(null); }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') { if (renamingTabName.trim()) renameTab(tab.id, renamingTabName.trim()); setRenamingTabId(null); }
                    else if (e.key === 'Escape') setRenamingTabId(null);
                  }}
                  className="chrome-tab-rename" autoFocus onClick={e => e.stopPropagation()}
                />
              ) : (
                <span className="chrome-tab-title" onDoubleClick={e => { e.stopPropagation(); setRenamingTabId(tab.id); setRenamingTabName(tab.name); }}>
                  {tab.name}
                </span>
              )}

              {/* Close button — layout_constants.cc:86 = 16px, tab_close_button.cc:45 */}
              <button onClick={e => { e.stopPropagation(); handleAnimatedClose(tab.id); }} className="chrome-tab-close">
                <X />
              </button>

              {/* Active tab bottom corners — tab_style_views.cc:400-427, extension_corner_radius=12 */}
              {isActive && (
                <div className="chrome-tab-corners">
                  <div className="chrome-tab-corner chrome-tab-corner--left" />
                  <div className="chrome-tab-corner chrome-tab-corner--right" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {rightSlot && <div ref={rightSlotRef} className="flex-shrink-0" style={{ alignSelf: 'center' }}>{rightSlot}</div>}
    </div>
  );
}
