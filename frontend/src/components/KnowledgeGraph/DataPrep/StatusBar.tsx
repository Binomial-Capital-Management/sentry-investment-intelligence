/**
 * StatusBar - Excel-style status bar at bottom of modal
 */

import { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronUp, Clock } from 'lucide-react';
import { HistoryManager } from './HistoryManager';

interface StatusBarProps {
  historyManager: HistoryManager;
  totalRows: number;
  totalCols: number;
  selectedCellsCount: number;
  selectedCellsData?: any[]; // Array of selected cell values for quick stats
}

export default function StatusBar({
  historyManager,
  totalRows,
  totalCols,
  selectedCellsCount,
  selectedCellsData = [],
}: StatusBarProps) {
  const [showHistory, setShowHistory] = useState(false);
  const historyRef = useRef<HTMLDivElement>(null);

  const undoStack = historyManager.getUndoStack();

  // Calculate quick stats for numeric selections (Excel-style)
  const quickStats = useMemo(() => {
    if (selectedCellsData.length === 0) return null;

    const numericValues = selectedCellsData
      .filter(val => val != null && !isNaN(Number(val)))
      .map(val => Number(val));

    if (numericValues.length === 0) {
      // Non-numeric: show count and unique count
      const uniqueValues = new Set(selectedCellsData.filter(v => v != null));
      return {
        count: selectedCellsData.length,
        unique: uniqueValues.size,
        isNumeric: false,
      };
    }

    // Numeric: show sum, average, min, max, count
    const sum = numericValues.reduce((a, b) => a + b, 0);
    const avg = sum / numericValues.length;
    const min = Math.min(...numericValues);
    const max = Math.max(...numericValues);

    return {
      count: numericValues.length,
      sum: sum.toLocaleString(undefined, { maximumFractionDigits: 2 }),
      average: avg.toLocaleString(undefined, { maximumFractionDigits: 2 }),
      min: min.toLocaleString(undefined, { maximumFractionDigits: 2 }),
      max: max.toLocaleString(undefined, { maximumFractionDigits: 2 }),
      isNumeric: true,
    };
  }, [selectedCellsData]);

  // Close history dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (historyRef.current && !historyRef.current.contains(e.target as Node)) {
        setShowHistory(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="flex items-center justify-between px-4 py-1.5 bg-slate-100 border-t border-slate-300 text-xs text-slate-700">
      {/* Left side - Stats */}
      <div className="flex items-center gap-4">
        <span className="font-medium">
          {totalRows.toLocaleString()} rows × {totalCols} columns
        </span>
        {selectedCellsCount > 0 && (
          <>
            <span className="text-slate-400">•</span>
            <span>{selectedCellsCount.toLocaleString()} cell{selectedCellsCount !== 1 ? 's' : ''} selected</span>
          </>
        )}
        {/* Quick Stats - Excel style */}
        {quickStats && (
          <>
            <span className="text-slate-400">•</span>
            {quickStats.isNumeric ? (
              <div className="flex items-center gap-3">
                <span title="Sum">Sum: <span className="font-semibold">{quickStats.sum}</span></span>
                <span title="Average">Avg: <span className="font-semibold">{quickStats.average}</span></span>
                <span title="Count">Count: <span className="font-semibold">{quickStats.count}</span></span>
                <span title="Min">Min: <span className="font-semibold">{quickStats.min}</span></span>
                <span title="Max">Max: <span className="font-semibold">{quickStats.max}</span></span>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <span>Count: <span className="font-semibold">{quickStats.count}</span></span>
                <span>Unique: <span className="font-semibold">{quickStats.unique}</span></span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Right side - History */}
      <div className="relative" ref={historyRef}>
        {undoStack.length > 0 ? (
          <>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-slate-200 transition-colors"
            >
              <Clock size={12} />
              <span>{undoStack.length} operation{undoStack.length !== 1 ? 's' : ''}</span>
              <ChevronUp size={12} className={`transition-transform ${showHistory ? '' : 'rotate-180'}`} />
            </button>

            {showHistory && (
              <div className="absolute bottom-full right-0 mb-1 w-72 max-h-64 overflow-y-auto bg-white border border-slate-300 rounded-lg shadow-lg z-50 animate-in slide-in-from-bottom-2 duration-150">
                <div className="sticky top-0 bg-slate-50 px-3 py-2 border-b border-slate-200">
                  <span className="text-xs font-semibold text-slate-700">Edit History</span>
                </div>
                <div className="py-1">
                  {[...undoStack].reverse().map((op, idx) => (
                    <div
                      key={idx}
                      className="px-3 py-2 hover:bg-slate-50 border-b border-slate-100 last:border-b-0"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm text-slate-700 flex-1">
                          {op.description}
                        </span>
                        <span className="text-xs text-slate-500 shrink-0">
                          {formatTimestamp(op.timestamp)}
                        </span>
                      </div>
                      <div className="mt-0.5 text-xs text-slate-500">
                        Type: <span className="font-mono">{op.type}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <span className="text-slate-500">Ready</span>
        )}
      </div>
    </div>
  );
}
