/**
 * RemoveDuplicatesModal - Excel-style remove duplicates with column selection
 */

import { useState, useMemo } from 'react';
import { X, Trash2, AlertCircle } from 'lucide-react';
import { CellData } from './HistoryManager';

interface RemoveDuplicatesModalProps {
  isOpen: boolean;
  onClose: () => void;
  sheetData: CellData[][];
  onApply: (newData: CellData[][], description: string) => void;
}

export default function RemoveDuplicatesModal({
  isOpen,
  sheetData,
  onClose,
  onApply,
}: RemoveDuplicatesModalProps) {
  const [selectedColumns, setSelectedColumns] = useState<Set<number>>(new Set([0])); // Default to first column

  const columnNames = useMemo(() => {
    if (sheetData.length === 0) return [];
    return sheetData[0].map((_, idx) => String.fromCharCode(65 + idx));
  }, [sheetData]);

  // Find duplicates based on selected columns
  const { duplicateRows, uniqueData } = useMemo(() => {
    if (selectedColumns.size === 0 || sheetData.length === 0) {
      return { duplicateRows: [], uniqueData: sheetData };
    }

    const seen = new Map<string, number>(); // key -> first occurrence row index
    const duplicates: number[] = [];
    const unique: CellData[][] = [];

    sheetData.forEach((row, rowIdx) => {
      // Create key from selected columns
      const key = Array.from(selectedColumns)
        .map(colIdx => {
          const value = row[colIdx]?.value;
          return value == null ? '' : String(value).toLowerCase().trim();
        })
        .join('|');

      if (seen.has(key)) {
        duplicates.push(rowIdx);
      } else {
        seen.set(key, rowIdx);
        unique.push(row);
      }
    });

    return { duplicateRows: duplicates, uniqueData: unique };
  }, [sheetData, selectedColumns]);

  const toggleColumn = (colIdx: number) => {
    const newSelected = new Set(selectedColumns);
    if (newSelected.has(colIdx)) {
      if (newSelected.size > 1) { // Keep at least one column selected
        newSelected.delete(colIdx);
      }
    } else {
      newSelected.add(colIdx);
    }
    setSelectedColumns(newSelected);
  };

  const selectAll = () => {
    setSelectedColumns(new Set(columnNames.map((_, idx) => idx)));
  };

  const deselectAll = () => {
    setSelectedColumns(new Set([0])); // Keep at least first column
  };

  const handleApply = () => {
    if (duplicateRows.length === 0) {
      onClose();
      return;
    }

    const columnList = Array.from(selectedColumns)
      .map(idx => columnNames[idx])
      .join(', ');

    onApply(
      uniqueData,
      `Removed ${duplicateRows.length} duplicate row${duplicateRows.length !== 1 ? 's' : ''} (by ${columnList})`,
    );
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl w-[800px] max-h-[80vh] flex flex-col animate-in slide-in-from-top-4 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-300">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Remove Duplicates</h3>
            <p className="text-sm text-slate-600 mt-0.5">Select columns to check for duplicate values</p>
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
          {/* Column Selection (Left) */}
          <div className="w-80 p-6 border-r border-slate-200 bg-slate-50">
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-slate-700">Columns to check:</h4>
                  <div className="flex gap-1">
                    <button
                      onClick={selectAll}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                    >
                      All
                    </button>
                    <span className="text-slate-400">|</span>
                    <button
                      onClick={deselectAll}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                    >
                      None
                    </button>
                  </div>
                </div>

                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {columnNames.map((colName, idx) => (
                    <label
                      key={idx}
                      className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer p-2 rounded hover:bg-slate-100"
                    >
                      <input
                        type="checkbox"
                        checked={selectedColumns.has(idx)}
                        onChange={() => toggleColumn(idx)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-mono font-semibold">{colName}</span>
                      <span className="text-slate-500">Column {idx + 1}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-300">
                <div className="flex items-start gap-2 text-sm">
                  <AlertCircle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                  <span className="text-slate-600">
                    Rows with matching values in selected columns will be removed (keeping first occurrence)
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Preview (Right) */}
          <div className="flex-1 flex flex-col">
            <div className="px-6 py-3 bg-slate-100 border-b border-slate-200">
              <h4 className="text-sm font-semibold text-slate-700">Preview</h4>
              <p className="text-xs text-slate-600 mt-0.5">
                {duplicateRows.length > 0
                  ? `${duplicateRows.length} duplicate row${duplicateRows.length !== 1 ? 's' : ''} will be removed`
                  : 'No duplicates found'
                }
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {duplicateRows.length === 0 ? (
                <div className="flex items-center justify-center h-full text-slate-500">
                  <div className="text-center">
                    <Trash2 size={48} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No duplicate rows found</p>
                    <p className="text-xs text-slate-400 mt-1">Try selecting different columns</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="bg-white border border-slate-200 rounded-md p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-semibold text-slate-700">Summary</span>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <div className="text-2xl font-bold text-slate-900">{sheetData.length}</div>
                        <div className="text-xs text-slate-600 mt-1">Total Rows</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-red-600">{duplicateRows.length}</div>
                        <div className="text-xs text-slate-600 mt-1">Duplicates</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-green-600">{uniqueData.length}</div>
                        <div className="text-xs text-slate-600 mt-1">Remaining</div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white border border-slate-200 rounded-md p-4">
                    <h5 className="text-sm font-semibold text-slate-700 mb-3">Duplicate rows to remove:</h5>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {duplicateRows.slice(0, 50).map((rowIdx) => (
                        <div
                          key={rowIdx}
                          className="flex items-center gap-2 p-2 bg-red-50 border border-red-200 rounded text-xs"
                        >
                          <span className="font-mono font-semibold text-red-700">Row {rowIdx + 1}</span>
                          <span className="text-slate-600">
                            {Array.from(selectedColumns).map(colIdx => {
                              const value = sheetData[rowIdx]?.[colIdx]?.value;
                              return value == null ? '' : String(value);
                            }).filter(Boolean).join(' | ')}
                          </span>
                        </div>
                      ))}
                      {duplicateRows.length > 50 && (
                        <div className="text-center text-sm text-slate-500 py-2">
                          ... and {duplicateRows.length - 50} more rows
                        </div>
                      )}
                    </div>
                  </div>
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
            disabled={duplicateRows.length === 0}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
          >
            Remove {duplicateRows.length > 0 && `${duplicateRows.length}`} Duplicate{duplicateRows.length !== 1 ? 's' : ''}
          </button>
        </div>
      </div>
    </div>
  );
}
