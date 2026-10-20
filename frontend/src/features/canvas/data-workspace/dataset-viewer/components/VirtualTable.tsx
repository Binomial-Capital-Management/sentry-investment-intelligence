/**
 * VirtualTable - Virtualized table component for large datasets
 * 
 * Uses @tanstack/react-virtual to only render visible rows,
 * drastically reducing DOM elements and memory usage.
 * 
 * Uses div-based layout (not HTML table) because transform: translateY()
 * doesn't work correctly with table row layout algorithms.
 */

import React, { useRef, useMemo, useState, useEffect, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

// Columns that should wrap text
const WRAP_COLUMNS = ['text', 'title', 'content', 'description', 'summary', 'body', 'headline', 'snippet'];

// Columns that are images
const IMAGE_COLUMNS = ['image', 'images', 'photo', 'thumbnail', 'logo', 'icon', 'avatar', 'banner'];

// Columns that are URLs/links
const LINK_COLUMNS = ['url', 'link', 'href', 'source', 'website', 'site'];

// Format value for display
function formatValue(value: any): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
    if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
    if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (Math.abs(value) < 0.01 && value !== 0) return value.toExponential(2);
    if (Number.isInteger(value)) return value.toLocaleString();
    return value.toFixed(2);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '[]';
    if (typeof value[0] === 'object' && value[0] !== null) {
      return `[${value.length} items]`;
    }
    return value.map(v => formatValue(v)).join(', ');
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value);
    if (keys.length === 0) return '{}';
    if (keys.length <= 3) {
      return keys.map(k => `${k}: ${formatValue(value[k])}`).join(', ');
    }
    return `{${keys.length} fields}`;
  }
  return String(value);
}

// Check if string is an image URL
function isImageUrl(str: string): boolean {
  if (typeof str !== 'string') return false;
  const lower = str.toLowerCase();
  return (lower.startsWith('http://') || lower.startsWith('https://')) &&
    (lower.includes('.jpg') || lower.includes('.jpeg') || lower.includes('.png') || 
     lower.includes('.gif') || lower.includes('.webp') || lower.includes('.svg') ||
     lower.includes('image') || lower.includes('/img/') || lower.includes('/images/'));
}

// Check if string is a URL
function isUrl(str: string): boolean {
  if (typeof str !== 'string') return false;
  return str.startsWith('http://') || str.startsWith('https://');
}

// Render cell value with rich formatting
function renderCellValue(value: any, columnName: string): React.ReactNode {
  if (value === null || value === undefined) return <span className="text-slate-300">—</span>;
  
  if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
    const formatted = formatValue(value);
    return <span className="text-slate-600 font-mono text-xs" title={JSON.stringify(value, null, 2)}>{formatted}</span>;
  }
  
  const colLower = columnName.toLowerCase();
  const strValue = String(value);
  
  // Image columns or image URLs
  if (IMAGE_COLUMNS.some(c => colLower.includes(c)) || isImageUrl(strValue)) {
    return (
      <img 
        src={strValue} 
        alt="" 
        className="h-10 w-16 object-cover rounded"
        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
      />
    );
  }
  
  // URL/Link columns
  if (LINK_COLUMNS.some(c => colLower.includes(c)) || isUrl(strValue)) {
    const displayUrl = strValue.length > 40 ? strValue.substring(0, 40) + '...' : strValue;
    return (
      <a 
        href={strValue} 
        target="_blank" 
        rel="noopener noreferrer"
        className="text-blue-600 hover:text-blue-800 hover:underline"
        title={strValue}
      >
        {displayUrl}
      </a>
    );
  }
  
  // Text columns that should wrap (line-clamp handles truncation visually)
  if (WRAP_COLUMNS.some(c => colLower.includes(c))) {
    return <span className="line-clamp-3" title={strValue}>{strValue}</span>;
  }
  
  return formatValue(value);
}

// ============================================================================
// Canvas-based column width measurement
// ============================================================================

const FONT_SANS = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, system-ui, sans-serif";
const FONT_MONO = "'SF Mono', 'Cascadia Code', monospace";

const CELL_FONT = `14px ${FONT_SANS}`;
const HEADER_FONT = `500 12px ${FONT_SANS}`;
const MONO_FONT = `12px ${FONT_MONO}`;
const HEADER_LETTER_SPACING = 0.6; // tracking-wider at 12px ≈ 0.05em * 12
const CELL_PADDING = 24; // px-3 each side

const COL_MIN = 80;
const COL_MAX = 400;
const COL_TEXT_MAX = 300;
const COL_IMAGE = 88; // 64px img + padding

let _ctx: CanvasRenderingContext2D | null = null;
function getCtx(): CanvasRenderingContext2D {
  if (!_ctx) {
    _ctx = document.createElement('canvas').getContext('2d')!;
  }
  return _ctx;
}

function measureTextWidth(text: string, font: string, letterSpacing = 0): number {
  const ctx = getCtx();
  ctx.font = font;
  let w = ctx.measureText(text).width;
  if (letterSpacing && text.length > 1) {
    w += (text.length - 1) * letterSpacing;
  }
  return Math.ceil(w);
}

/** Returns the display string for a cell value (mirrors renderCellValue truncation) */
function getDisplayString(value: any, columnName: string): string {
  if (value === null || value === undefined) return '—';
  if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
    return formatValue(value);
  }
  const colLower = columnName.toLowerCase();
  const strValue = String(value);

  if (IMAGE_COLUMNS.some(c => colLower.includes(c)) || isImageUrl(strValue)) return '';
  if (LINK_COLUMNS.some(c => colLower.includes(c)) || isUrl(strValue)) {
    return strValue.length > 40 ? strValue.substring(0, 40) + '...' : strValue;
  }
  if (WRAP_COLUMNS.some(c => colLower.includes(c))) {
    return strValue.length > 200 ? strValue.substring(0, 200) + '...' : strValue;
  }
  return formatValue(value);
}

function computeColumnWidths(
  columns: string[],
  rows: Record<string, any>[],
  containerWidth: number,
): number[] {
  const widths = columns.map(col => {
    const colLower = col.toLowerCase();

    // Image columns: fixed width
    if (IMAGE_COLUMNS.some(c => colLower.includes(c))) return COL_IMAGE;

    const isTextCol = WRAP_COLUMNS.some(c => colLower.includes(c));
    const cap = isTextCol ? COL_TEXT_MAX : COL_MAX;

    // Measure header (+ 12px buffer for Canvas vs CSS rendering differences)
    const headerWidth = measureTextWidth(col.toUpperCase(), HEADER_FONT, HEADER_LETTER_SPACING) + CELL_PADDING + 12;

    // Find widest cell value
    let maxCellWidth = 0;

    if (rows.length <= 100) {
      // Small dataset: measure all
      for (const row of rows) {
        const val = row[col];
        const str = getDisplayString(val, col);
        if (!str) continue;
        const font = (Array.isArray(val) || (typeof val === 'object' && val !== null)) ? MONO_FONT : CELL_FONT;
        const w = measureTextWidth(str, font) + CELL_PADDING;
        if (w > maxCellWidth) maxCellWidth = w;
      }
    } else {
      // Large dataset: find longest string by length, measure only that
      let longestStr = '';
      let longestVal: any = null;
      for (const row of rows) {
        const val = row[col];
        const str = getDisplayString(val, col);
        if (str.length > longestStr.length) {
          longestStr = str;
          longestVal = val;
        }
      }
      if (longestStr) {
        const font = (Array.isArray(longestVal) || (typeof longestVal === 'object' && longestVal !== null)) ? MONO_FONT : CELL_FONT;
        maxCellWidth = measureTextWidth(longestStr, font) + CELL_PADDING;
      }
    }

    return Math.max(COL_MIN, Math.min(cap, Math.max(headerWidth, maxCellWidth)));
  });

  // Container fill: scale up proportionally if columns are narrower than container
  const totalIntrinsic = widths.reduce((s, w) => s + w, 0);
  if (containerWidth > 0 && totalIntrinsic < containerWidth) {
    const scale = containerWidth / totalIntrinsic;
    return widths.map((w, i) => {
      const colLower = columns[i].toLowerCase();
      if (IMAGE_COLUMNS.some(c => colLower.includes(c))) return COL_IMAGE;
      const isTextCol = WRAP_COLUMNS.some(c => colLower.includes(c));
      const cap = isTextCol ? COL_TEXT_MAX : COL_MAX;
      return Math.min(Math.ceil(w * scale), cap);
    });
  }

  return widths;
}

interface VirtualTableProps {
  columns: string[];
  rows: Record<string, any>[];
  /** Columns to highlight as join keys */
  joinKeyDisplay?: string[];
  /** Estimated row height in pixels */
  rowHeight?: number;
  /** Number of rows to render outside viewport */
  overscan?: number;
  /** Optional className for the container */
  className?: string;
}

/**
 * Virtualized table using div-based layout.
 * 
 * HTML tables don't work well with transform positioning,
 * so we use divs styled to look like a table.
 */
/** Row detail panel — slides up from bottom, resizable from top */
function RowDetailPanel({ row, columns, onClose, isOpen, height, onHeightChange }: {
  row: Record<string, any> | null;
  columns: string[];
  onClose: () => void;
  isOpen: boolean;
  height: number;
  onHeightChange: (h: number) => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    const container = panelRef.current?.parentElement;
    if (!container) return;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const rect = container.getBoundingClientRect();
      const pct = ((rect.bottom - ev.clientY) / rect.height) * 100;
      onHeightChange(Math.max(20, Math.min(85, pct)));
    };
    const onUp = () => {
      dragging.current = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, []);

  return (
    <div
      ref={panelRef}
      className="absolute bottom-0 left-0 right-0 z-30 bg-white flex flex-col shadow-[0_-4px_24px_rgba(0,0,0,0.08)] rounded-t-xl ease-out"
      style={{
        height: `${height}%`,
        borderTop: '1px solid hsl(30 3.3% 11.8% / 15%)',
        transform: isOpen ? 'translateY(0)' : 'translateY(100%)',
        transition: dragging.current ? 'none' : 'transform 0.3s ease-out',
      }}
    >
      {/* Header with integrated resize handle */}
      <div className="flex-shrink-0 relative" style={{ height: 44, borderBottom: '1px solid hsl(30 3.3% 11.8% / 10%)' }}>
        {/* Resize handle at top */}
        <div
          onMouseDown={onResizeStart}
          className="absolute top-0 left-0 right-0 flex justify-center pt-1.5 cursor-row-resize group z-10"
        >
          <div className="w-8 h-1 bg-slate-200 rounded-full group-hover:bg-slate-400 transition-colors" />
        </div>
        {/* Centered title + close */}
        <div className="h-full px-4 flex items-center justify-between">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Row Detail</span>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      {row && (
        <div className="flex-1 overflow-y-auto min-h-0 p-4 flex flex-col gap-4">
          {columns.filter(c => !c.startsWith('_')).map(col => {
            const value = row[col];
            if (value === null || value === undefined) return null;
            const strValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
            const isUrl = typeof value === 'string' && (value.startsWith('http://') || value.startsWith('https://'));
            return (
              <div key={col}>
                <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1">{col}</div>
                {isUrl ? (
                  <a href={strValue} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline break-all">{strValue}</a>
                ) : (
                  <div className="text-sm text-slate-700 whitespace-pre-wrap break-words">{strValue}</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export const VirtualTable: React.FC<VirtualTableProps> = ({
  columns,
  rows,
  joinKeyDisplay = [],
  rowHeight = 35,
  overscan = 20,
  className = '',
}) => {
  const parentRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const [selectedRowIdx, setSelectedRowIdx] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailRow, setDetailRow] = useState<Record<string, any> | null>(null);
  const [detailHeight, setDetailHeight] = useState(55);
  const detailTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const openDetail = useCallback((idx: number) => {
    clearTimeout(detailTimerRef.current);
    setSelectedRowIdx(idx);
    setDetailRow(rows[idx]);
    // Delay to allow mount before transition
    requestAnimationFrame(() => setDetailOpen(true));
  }, [rows]);

  const closeDetail = useCallback(() => {
    setDetailOpen(false);
    setSelectedRowIdx(null);
    detailTimerRef.current = setTimeout(() => setDetailRow(null), 300);
  }, []);
  
  // Filter out internal columns (starting with _)
  const visibleColumns = useMemo(() => 
    columns.filter(c => !c.startsWith('_')),
    [columns]
  );
  
  // Track container width for proportional fill
  const [containerWidth, setContainerWidth] = useState(0);
  useEffect(() => {
    const el = parentRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) setContainerWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Auto-show scrollbar on scroll, hide after idle + sync header horizontal scroll
  useEffect(() => {
    const el = parentRef.current;
    const header = headerRef.current;
    if (!el) return;
    let timer: ReturnType<typeof setTimeout>;
    const onScroll = () => {
      el.classList.add('is-scrolling');
      clearTimeout(timer);
      timer = setTimeout(() => el.classList.remove('is-scrolling'), 800);
      if (header) header.scrollLeft = el.scrollLeft;
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => { el.removeEventListener('scroll', onScroll); clearTimeout(timer); };
  }, []);

  // Auto-size columns based on content
  const colWidths = useMemo(
    () => computeColumnWidths(visibleColumns, rows, containerWidth),
    [visibleColumns, rows, containerWidth],
  );
  const totalWidth = useMemo(
    () => colWidths.reduce((s, w) => s + w, 0),
    [colWidths],
  );

  // Use taller rows when wrap columns (text, title, etc.) are present
  const hasWrapColumns = useMemo(
    () => visibleColumns.some(col => WRAP_COLUMNS.some(c => col.toLowerCase().includes(c))),
    [visibleColumns],
  );
  const effectiveRowHeight = hasWrapColumns ? Math.max(rowHeight, 76) : rowHeight;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => effectiveRowHeight,
    overscan,
  });

  const virtualRows = virtualizer.getVirtualItems();

  // Early return for empty state
  if (rows.length === 0) {
    return (
      <div className={`flex items-center justify-center p-8 text-slate-400 text-sm ${className}`}>
        No data to display
      </div>
    );
  }

  return (
    <div className={`flex flex-col relative ${className}`}>
      {/* Header — outside scroll container, syncs horizontally */}
      <div ref={headerRef} className="overflow-hidden flex-shrink-0" style={{ backgroundColor: 'hsl(30 3.3% 11.8% / 4%)', borderBottom: '1px solid hsl(30 3.3% 11.8% / 10%)' }}>
        <div className="flex" style={{ minWidth: `${totalWidth}px` }}>
          {visibleColumns.map((col, colIdx) => (
            <div
              key={col}
              className={`flex-shrink-0 px-3 py-2 text-xs font-medium uppercase tracking-wider text-left overflow-hidden whitespace-nowrap text-ellipsis ${
                joinKeyDisplay.includes(col)
                  ? 'text-blue-600 bg-blue-50/50'
                  : 'text-slate-500'
              }`}
              style={{ width: `${colWidths[colIdx]}px`, minWidth: `${colWidths[colIdx]}px`, maxWidth: `${colWidths[colIdx]}px` }}
              title={col}
            >
              {col}
              {joinKeyDisplay.includes(col) && (
                <span className="ml-1 text-[9px] text-blue-400">●</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Scrollable body — scrollbar only covers data rows */}
      <div
        ref={parentRef}
        className="flex-1 overflow-auto scrollbar-auto"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize() + (detailOpen ? (parentRef.current?.clientHeight ?? 0) * detailHeight / 100 : 0)}px`,
            width: `${totalWidth}px`,
            position: 'relative',
          }}
        >
          {virtualRows.map((virtualRow) => {
            const row = rows[virtualRow.index];
            const dataRowIdx = virtualRow.index;

            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                className={`flex absolute left-0 right-0 cursor-pointer transition-colors ${
                  selectedRowIdx === dataRowIdx
                    ? 'bg-blue-50 ring-1 ring-inset ring-blue-200'
                    : dataRowIdx % 2 === 0
                      ? 'bg-white hover:bg-slate-50'
                      : 'bg-slate-50/50 hover:bg-slate-100/50'
                }`}
                style={{
                  height: `${virtualRow.size}px`,
                  top: `${virtualRow.start}px`,
                }}
                onClick={() => selectedRowIdx === dataRowIdx ? closeDetail() : openDetail(dataRowIdx)}
              >
                {visibleColumns.map((col, colIdx) => {
                  const colLower = col.toLowerCase();
                  const shouldWrap = WRAP_COLUMNS.some(c => colLower.includes(c));

                  return (
                    <div
                      key={col}
                      className={`flex-shrink-0 px-3 py-2 text-sm overflow-hidden ${shouldWrap ? '' : 'whitespace-nowrap text-ellipsis'} ${
                        joinKeyDisplay.includes(col)
                          ? 'text-slate-800 font-medium'
                          : 'text-slate-600'
                      }`}
                      style={{ width: `${colWidths[colIdx]}px`, minWidth: `${colWidths[colIdx]}px`, maxWidth: `${colWidths[colIdx]}px` }}
                    >
                      {renderCellValue(row[col], col)}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Row detail panel */}
      {detailRow && (
        <RowDetailPanel
          row={detailRow}
          columns={columns}
          onClose={closeDetail}
          isOpen={detailOpen}
          height={detailHeight}
          onHeightChange={setDetailHeight}
        />
      )}
    </div>
  );
};

export default VirtualTable;
