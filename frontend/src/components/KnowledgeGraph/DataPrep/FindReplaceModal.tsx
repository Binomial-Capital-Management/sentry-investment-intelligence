/**
 * FindReplaceModal - Excel-style Find & Replace with preview
 * Microsoft pattern: Settings panel (left) + Preview panel (right)
 */

import { useState, useMemo } from 'react';
import { X, Search, ArrowRight } from 'lucide-react';
import { CellData } from './HistoryManager';

interface FindReplaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  sheetData: CellData[][];
  onApply: (newData: CellData[][], description: string) => void;
}

interface Match {
  row: number;
  col: number;
  oldValue: string;
  newValue: string;
}

export default function FindReplaceModal({
  isOpen,
  sheetData,
  onClose,
  onApply,
}: FindReplaceModalProps) {
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [matchCase, setMatchCase] = useState(false);
  const [matchWholeCell, setMatchWholeCell] = useState(false);
  const [useRegex, setUseRegex] = useState(false);

  // Helper function to escape regex special characters
  const escapeRegex = (str: string) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  // Preview matches
  const matches = useMemo(() => {
    if (!findText) return [];

    const results: Match[] = [];

    sheetData.forEach((row, rowIdx) => {
      row.forEach((cell, colIdx) => {
        if (cell.value == null) return;

        const cellValue = String(cell.value);
        let found = false;

        if (useRegex) {
          try {
            const regex = new RegExp(findText, matchCase ? 'g' : 'gi');
            if (regex.test(cellValue)) {
              found = true;
            }
          } catch (e) {
            // Invalid regex, skip
            return;
          }
        } else {
          const searchValue = matchCase ? cellValue : cellValue.toLowerCase();
          const searchTerm = matchCase ? findText : findText.toLowerCase();

          if (matchWholeCell) {
            found = searchValue === searchTerm;
          } else {
            found = searchValue.includes(searchTerm);
          }
        }

        if (found) {
          let newValue: string;
          if (useRegex) {
            try {
              const regex = new RegExp(findText, matchCase ? 'g' : 'gi');
              newValue = cellValue.replace(regex, replaceText);
            } catch {
              newValue = cellValue;
            }
          } else if (matchWholeCell) {
            newValue = replaceText;
          } else {
            if (matchCase) {
              newValue = cellValue.replace(new RegExp(escapeRegex(findText), 'g'), replaceText);
            } else {
              newValue = cellValue.replace(new RegExp(escapeRegex(findText), 'gi'), replaceText);
            }
          }

          results.push({
            row: rowIdx,
            col: colIdx,
            oldValue: cellValue,
            newValue,
          });
        }
      });
    });

    return results;
  }, [sheetData, findText, replaceText, matchCase, matchWholeCell, useRegex]);

  const handleApply = () => {
    if (matches.length === 0) return;

    const newData = sheetData.map((row, rowIdx) =>
      row.map((cell, colIdx) => {
        const match = matches.find(m => m.row === rowIdx && m.col === colIdx);
        if (match) {
          return { ...cell, value: match.newValue };
        }
        return cell;
      }),
    );

    onApply(newData, `Find & Replace: "${findText}" → "${replaceText}" (${matches.length} cell${matches.length !== 1 ? 's' : ''})`);
    onClose();
  };

  const getCellAddress = (row: number, col: number) => {
    return `${String.fromCharCode(65 + col)}${row + 1}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl w-[900px] max-h-[80vh] flex flex-col animate-in slide-in-from-top-4 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-300">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Find and Replace</h3>
            <p className="text-sm text-slate-600 mt-0.5">Search and replace text across all cells</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-md transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Settings Panel (Left) */}
          <div className="w-80 p-6 border-r border-slate-200 bg-slate-50">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Find what:
                </label>
                <input
                  type="text"
                  value={findText}
                  onChange={(e) => setFindText(e.target.value)}
                  placeholder="Enter text to find"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Replace with:
                </label>
                <input
                  type="text"
                  value={replaceText}
                  onChange={(e) => setReplaceText(e.target.value)}
                  placeholder="Enter replacement text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="pt-2 space-y-2">
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={matchCase}
                    onChange={(e) => setMatchCase(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  Match case
                </label>

                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={matchWholeCell}
                    onChange={(e) => setMatchWholeCell(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  Match entire cell contents
                </label>

                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useRegex}
                    onChange={(e) => setUseRegex(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  Use regular expressions
                </label>
              </div>

              <div className="pt-4 border-t border-slate-300">
                <div className="flex items-center gap-2 text-sm">
                  <Search size={16} className="text-slate-500" />
                  <span className="text-slate-600">
                    {matches.length} match{matches.length !== 1 ? 'es' : ''} found
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Preview Panel (Right) */}
          <div className="flex-1 flex flex-col">
            <div className="px-6 py-3 bg-slate-100 border-b border-slate-200">
              <h4 className="text-sm font-semibold text-slate-700">Preview Changes</h4>
              <p className="text-xs text-slate-600 mt-0.5">
                {matches.length > 0
                  ? `${matches.length} cell${matches.length !== 1 ? 's' : ''} will be modified`
                  : 'No matches found'
                }
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {matches.length === 0 ? (
                <div className="flex items-center justify-center h-full text-slate-500">
                  <div className="text-center">
                    <Search size={48} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">Enter search text to see preview</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {matches.slice(0, 100).map((match, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-white border border-slate-200 rounded-md hover:border-blue-300 transition-colors"
                    >
                      <div className="flex items-start gap-2 mb-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-blue-100 text-blue-700 text-xs font-mono font-semibold">
                          {getCellAddress(match.row, match.col)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-slate-700 font-medium break-all">{match.oldValue}</span>
                        <ArrowRight size={14} className="text-slate-400 shrink-0" />
                        <span className="text-green-700 font-medium break-all">{match.newValue}</span>
                      </div>
                    </div>
                  ))}
                  {matches.length > 100 && (
                    <div className="text-center text-sm text-slate-500 py-2">
                      ... and {matches.length - 100} more changes
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-300 bg-slate-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 rounded-md transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleApply}
            disabled={matches.length === 0}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
          >
            Replace {matches.length > 0 && `${matches.length}`} Match{matches.length !== 1 ? 'es' : ''}
          </button>
        </div>
      </div>
    </div>
  );
}
