/**
 * DataPrepToolbar - Microsoft Excel-style ribbon for data preparation
 */

import { useState, useRef, useEffect } from 'react';
import { Undo2, Redo2, ChevronDown, Sparkles, Scissors, CheckCircle2, Eraser, Search, Copy } from 'lucide-react';
import { HistoryManager, CellData } from './HistoryManager';

interface DataPrepToolbarProps {
  historyManager: HistoryManager;
  sheetData: CellData[][];
  onTrimAll: () => void;
  onFindReplace: () => void;
  onRemoveDuplicates: () => void;
  selectedCell: { row: number; col: number } | null;
}

export default function DataPrepToolbar({
  historyManager,
  sheetData,
  onTrimAll,
  onFindReplace,
  onRemoveDuplicates,
  selectedCell,
}: DataPrepToolbarProps) {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const cleanRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<HTMLDivElement>(null);
  const validateRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        cleanRef.current && !cleanRef.current.contains(e.target as Node) &&
        transformRef.current && !transformRef.current.contains(e.target as Node) &&
        validateRef.current && !validateRef.current.contains(e.target as Node)
      ) {
        setOpenDropdown(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleDropdown = (name: string) => {
    setOpenDropdown(openDropdown === name ? null : name);
  };

  const canUndo = historyManager.canUndo();
  const canRedo = historyManager.canRedo();
  const lastOperation = historyManager.getLastOperation();

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-slate-50 border-b border-slate-300 relative z-40">
      {/* Undo/Redo */}
      <div className="flex items-center gap-1 pr-3 border-r border-slate-300">
        <button
          onClick={() => historyManager.undo()}
          disabled={!canUndo}
          className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors group relative"
          title={canUndo ? `Undo ${lastOperation}` : 'Nothing to undo'}
        >
          <Undo2 size={16} className="text-slate-700" />
        </button>
        <button
          onClick={() => historyManager.redo()}
          disabled={!canRedo}
          className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={canRedo ? 'Redo' : 'Nothing to redo'}
        >
          <Redo2 size={16} className="text-slate-700" />
        </button>
      </div>

      {/* Clean Dropdown */}
      <div className="relative" ref={cleanRef}>
        <button
          onClick={() => toggleDropdown('clean')}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 rounded hover:bg-slate-200 transition-colors"
        >
          <Sparkles size={14} />
          Clean
          <ChevronDown size={12} className={`transition-transform ${openDropdown === 'clean' ? 'rotate-180' : ''}`} />
        </button>

        {openDropdown === 'clean' && (
          <div className="absolute top-full left-0 mt-1 w-80 bg-white border border-slate-300 rounded-lg shadow-xl z-50 py-2 animate-in slide-in-from-top-2 duration-150">
            <div className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Quick Actions
            </div>

            <button
              onClick={() => {
                console.log('Trim All clicked!');
                onTrimAll();
                setOpenDropdown(null);
              }}
              className="w-full px-3 py-2.5 text-left hover:bg-blue-50 transition-colors group"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 p-1.5 rounded-md bg-blue-100 group-hover:bg-blue-200 transition-colors">
                  <Eraser size={14} className="text-blue-600" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-slate-900">Trim All Whitespace</div>
                  <div className="text-xs text-slate-600 mt-0.5">Remove leading/trailing spaces from all cells</div>
                </div>
              </div>
            </button>

            <button
              onClick={() => {
                console.log('Find & Replace clicked!');
                onFindReplace();
                setOpenDropdown(null);
              }}
              className="w-full px-3 py-2.5 text-left hover:bg-green-50 transition-colors group"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 p-1.5 rounded-md bg-green-100 group-hover:bg-green-200 transition-colors">
                  <Search size={14} className="text-green-600" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-900">Find & Replace</span>
                    <span className="px-1.5 py-0.5 text-[10px] font-mono bg-slate-200 text-slate-700 rounded">Ctrl+H</span>
                  </div>
                  <div className="text-xs text-slate-600 mt-0.5">Search and replace text with regex support</div>
                </div>
              </div>
            </button>

            <button
              onClick={() => {
                onRemoveDuplicates();
                setOpenDropdown(null);
              }}
              className="w-full px-3 py-2.5 text-left hover:bg-purple-50 transition-colors group"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 p-1.5 rounded-md bg-purple-100 group-hover:bg-purple-200 transition-colors">
                  <Copy size={14} className="text-purple-600" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-slate-900">Remove Duplicates</div>
                  <div className="text-xs text-slate-600 mt-0.5">Keep unique rows based on selected columns</div>
                </div>
              </div>
            </button>

            <div className="border-t border-slate-200 my-2"></div>

            <div className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Coming Soon
            </div>

            <button
              disabled
              className="w-full px-3 py-2.5 text-left cursor-not-allowed opacity-50"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 p-1.5 rounded-md bg-slate-100">
                  <Eraser size={14} className="text-slate-400" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-slate-700">Remove Empty Rows</div>
                  <div className="text-xs text-slate-500 mt-0.5">Delete rows with no data</div>
                </div>
              </div>
            </button>
          </div>
        )}
      </div>

      {/* Transform Dropdown */}
      <div className="relative" ref={transformRef}>
        <button
          onClick={() => toggleDropdown('transform')}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 rounded hover:bg-slate-200 transition-colors"
        >
          <Scissors size={14} />
          Transform
          <ChevronDown size={12} className={`transition-transform ${openDropdown === 'transform' ? 'rotate-180' : ''}`} />
        </button>

        {openDropdown === 'transform' && (
          <div className="absolute top-full left-0 mt-1 w-56 bg-white border border-slate-300 rounded-lg shadow-lg z-50 py-1 animate-in slide-in-from-top-2 duration-150">
            <button
              disabled
              className="w-full px-4 py-2 text-left text-sm text-slate-400 cursor-not-allowed"
            >
              Split Column...
              <span className="ml-2 text-xs">(Coming soon)</span>
            </button>
            <button
              disabled
              className="w-full px-4 py-2 text-left text-sm text-slate-400 cursor-not-allowed"
            >
              Merge Columns...
              <span className="ml-2 text-xs">(Coming soon)</span>
            </button>
            <button
              disabled
              className="w-full px-4 py-2 text-left text-sm text-slate-400 cursor-not-allowed"
            >
              Change Case...
              <span className="ml-2 text-xs">(Coming soon)</span>
            </button>
          </div>
        )}
      </div>

      {/* Validate Dropdown */}
      <div className="relative" ref={validateRef}>
        <button
          onClick={() => toggleDropdown('validate')}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 rounded hover:bg-slate-200 transition-colors"
        >
          <CheckCircle2 size={14} />
          Validate
          <ChevronDown size={12} className={`transition-transform ${openDropdown === 'validate' ? 'rotate-180' : ''}`} />
        </button>

        {openDropdown === 'validate' && (
          <div className="absolute top-full left-0 mt-1 w-56 bg-white border border-slate-300 rounded-lg shadow-lg z-50 py-1 animate-in slide-in-from-top-2 duration-150">
            <button
              disabled
              className="w-full px-4 py-2 text-left text-sm text-slate-400 cursor-not-allowed"
            >
              Check Entity References...
              <span className="ml-2 text-xs">(Coming soon)</span>
            </button>
            <button
              disabled
              className="w-full px-4 py-2 text-left text-sm text-slate-400 cursor-not-allowed"
            >
              Highlight Duplicates
              <span className="ml-2 text-xs">(Coming soon)</span>
            </button>
            <button
              disabled
              className="w-full px-4 py-2 text-left text-sm text-slate-400 cursor-not-allowed"
            >
              Data Quality Report
              <span className="ml-2 text-xs">(Coming soon)</span>
            </button>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="ml-auto text-xs text-slate-600">
        {sheetData.length} rows × {sheetData[0]?.length || 0} cols
        {selectedCell && (
          <span className="ml-2">
            • Cell {String.fromCharCode(65 + selectedCell.col)}{selectedCell.row + 1}
          </span>
        )}
      </div>
    </div>
  );
}
