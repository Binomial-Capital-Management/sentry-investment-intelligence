import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { X, Square, CheckSquare, Maximize2, Minimize2 } from 'lucide-react';
import * as XLSX from 'xlsx';
import ParsedPreview from './ParsedPreview';
import DetectionSummary from './DetectionSummary';
import CellAnnotation from './CellAnnotation';
import { autoDetectStructure, calculateOverallConfidence, DetectionResult } from '../../utils/tableDetection';
import { HistoryManager, DataPrepToolbar, StatusBar, FindReplaceModal, RemoveDuplicatesModal } from './DataPrep';
import ContextMenu from './ContextMenu';
import ColumnFilterMenu from './ColumnFilterMenu';

interface ExcelPreviewModalProps {
  file: File | null;
  isOpen: boolean;
  onClose: () => void;
  onStartParsing: (selections: TableSelections) => void;
  onRawDataChange?: (data: any[][]) => void;
  initialSelections?: TableSelections;  // Pre-loaded selections (e.g., from saved table)
  initialRawData?: any[][];  // Pre-loaded raw data (bypasses file reading)
}

export interface TableSelections {
  headerCells: Set<string>; // "row,col" format
  identifierCells: Set<string>; // "row,col" format
  dataRegion: {
    startRow: number;
    endRow: number;
    startCol: number;
    endCol: number;
  } | null;
}

interface CellData {
  value: string | number | null;
  merged?: boolean;
  mergeSpan?: { rows: number; cols: number };
  isMergedCopy?: boolean;
}

interface MergeRegion {
  s: { r: number; c: number };
  e: { r: number; c: number };
}

export default function ExcelPreviewModal({
  file,
  isOpen,
  onClose,
  onStartParsing,
  onRawDataChange,
  initialSelections,
  initialRawData,
}: ExcelPreviewModalProps) {
  const [sheetData, setSheetData] = useState<CellData[][]>([]);
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [currentSheet, setCurrentSheet] = useState<number>(0);
  const [workbookData, setWorkbookData] = useState<any>(null);
  const [selections, setSelections] = useState<TableSelections>({
    headerCells: new Set<string>(),
    identifierCells: new Set<string>(),
    dataRegion: null,
  });
  const [selectionMode, setSelectionMode] = useState<'header' | 'identifier' | 'data'>('header');
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{row: number; col: number} | null>(null);
  const [dragEnd, setDragEnd] = useState<{row: number; col: number} | null>(null);
  const dragEndRef = useRef<{row: number; col: number} | null>(null);
  const [editingCell, setEditingCell] = useState<{row: number; col: number} | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [lastClickedCell, setLastClickedCell] = useState<{row: number; col: number} | null>(null);
  const [selectedCell, setSelectedCell] = useState<{row: number; col: number} | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Column sizing state
  const [columnWidths, setColumnWidths] = useState<Record<number, number>>({});
  const [resizingCol, setResizingCol] = useState<number | null>(null);
  const [resizeStartX, setResizeStartX] = useState<number>(0);
  const [resizeStartWidth, setResizeStartWidth] = useState<number>(0);
  const [resizeTooltipWidth, setResizeTooltipWidth] = useState<number | null>(null);

  // Auto-scroll state
  const [autoScrollDirection, setAutoScrollDirection] = useState<{x: number; y: number}>({ x: 0, y: 0 });
  const autoScrollRef = useRef<number | null>(null);

  // Fullscreen mode state
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Auto-detection state
  const [detectionResult, setDetectionResult] = useState<DetectionResult | null>(null);
  const [showDetectionSummary, setShowDetectionSummary] = useState(true);
  const [manualAdjustmentMode, setManualAdjustmentMode] = useState(false);

  // History manager for undo/redo
  const [historyManager] = useState(() => new HistoryManager(sheetData, setSheetData));

  // Data prep modal states
  const [showFindReplace, setShowFindReplace] = useState(false);
  const [showRemoveDuplicates, setShowRemoveDuplicates] = useState(false);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);

  // Column filter menu state
  const [columnFilter, setColumnFilter] = useState<{ columnIndex: number; x: number; y: number } | null>(null);

  // Clipboard state
  const [clipboard, setClipboard] = useState<CellData[][] | null>(null);
  const [clipboardMode, setClipboardMode] = useState<'copy' | 'cut' | null>(null);

  const applyRawData = useCallback((rawValues: any[][], selectionsOverride?: TableSelections | null) => {
    const rows: CellData[][] = rawValues.map(row =>
      row.map(value => ({
        value: value ?? null,
        merged: false,
        isMergedCopy: false,
      })),
    );

    setSheetData(rows);
    onRawDataChange?.(rawValues);

    if (selectionsOverride) {
      setSelections({
        headerCells: new Set(selectionsOverride.headerCells),
        identifierCells: new Set(selectionsOverride.identifierCells),
        dataRegion: selectionsOverride.dataRegion ? { ...selectionsOverride.dataRegion } : null,
      });
      setShowDetectionSummary(false);
      setManualAdjustmentMode(true);  // Show selectors for saved tables
      const detected = autoDetectStructure(rawValues);
      setDetectionResult(detected);
    } else {
      const detected = autoDetectStructure(rawValues);
      setDetectionResult(detected);

      const headerCells = new Set<string>();
      detected.headers.rows.forEach(row => {
        for (let col = 0; col < rawValues[0]?.length || 0; col++) {
          headerCells.add(`${row},${col}`);
        }
      });

      const identifierCells = new Set<string>();
      detected.identifiers.columns.forEach(col => {
        for (let row = 0; row < rawValues.length; row++) {
          identifierCells.add(`${row},${col}`);
        }
      });

      setSelections({
        headerCells,
        identifierCells,
        dataRegion: detected.dataRegion,
      });
      setShowDetectionSummary(true);
      setManualAdjustmentMode(false);
    }
  }, [onRawDataChange]);

  // Load workbook and sheet names
  useEffect(() => {
    if (!isOpen) return;

    if (initialRawData) {
      console.log('Using pre-loaded raw data, skipping file read');
      setSheetNames(['Sheet1']);
      setCurrentSheet(0);
      setWorkbookData(null);
      applyRawData(initialRawData, initialSelections);
      return;
    }

    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const data = e.target?.result;
        const workbook = XLSX.read(data, { type: 'binary' });
        setWorkbookData(workbook);
        setSheetNames(workbook.SheetNames);
        setCurrentSheet(0);
      };
      reader.readAsBinaryString(file);
    }
  }, [file, isOpen, initialRawData, initialSelections, applyRawData]);

  // Load current sheet data
  useEffect(() => {
    if (workbookData && sheetNames.length > 0) {
      const sheet = workbookData.Sheets[sheetNames[currentSheet]];

      // Get range and merge info
      const range = XLSX.utils.decode_range(sheet['!ref'] || 'A1');
      const merges: MergeRegion[] = sheet['!merges'] || [];

      // Initialize 2D array
      const rows: CellData[][] = [];
      for (let row = range.s.r; row <= range.e.r; row++) {
        const rowData: CellData[] = [];
        for (let col = range.s.c; col <= range.e.c; col++) {
          const cellAddress = XLSX.utils.encode_cell({ r: row, c: col });
          const cell = sheet[cellAddress];
          rowData.push({
            value: cell ? cell.v : null,
            merged: false,
            isMergedCopy: false,
          });
        }
        rows.push(rowData);
      }

      // Forward-fill merged cells with source value
      for (const merge of merges) {
        const sourceValue = rows[merge.s.r]?.[merge.s.c]?.value;
        for (let row = merge.s.r; row <= merge.e.r; row++) {
          for (let col = merge.s.c; col <= merge.e.c; col++) {
            // Safety check: ensure cell exists
            if (!rows[row] || !rows[row][col]) continue;

            if (row === merge.s.r && col === merge.s.c) {
              // Mark source cell
              rows[row][col].merged = true;
              rows[row][col].mergeSpan = {
                rows: merge.e.r - merge.s.r + 1,
                cols: merge.e.c - merge.s.c + 1,
              };
            } else {
              // Forward-fill value to spanned cells
              rows[row][col].value = sourceValue;
              rows[row][col].isMergedCopy = true;
            }
          }
        }
      }

      setSheetData(rows);

      // Extract raw values for database storage
      const rawData = rows.map(row => row.map(cell => cell.value));
      onRawDataChange?.(rawData);

      // Use initialSelections if provided (e.g., loading saved table), otherwise auto-detect
      if (initialSelections) {
        console.log('Using pre-loaded selections:', initialSelections);
        setSelections(initialSelections);
        setShowDetectionSummary(false);  // Skip summary, go straight to editor
        setManualAdjustmentMode(true);  // Show selectors for saved tables

        // Still run detection for the summary stats (but don't apply it)
        const detected = autoDetectStructure(rawData);
        setDetectionResult(detected);
      } else {
        // Auto-detect table structure
        const detected = autoDetectStructure(rawData);
        setDetectionResult(detected);

        // Apply auto-detected selections
        const headerCells = new Set<string>();
        detected.headers.rows.forEach(row => {
          for (let col = 0; col < rawData[0]?.length || 0; col++) {
            headerCells.add(`${row},${col}`);
          }
        });

        const identifierCells = new Set<string>();
        detected.identifiers.columns.forEach(col => {
          for (let row = 0; row < rawData.length; row++) {
            identifierCells.add(`${row},${col}`);
          }
        });

        setSelections({
          headerCells,
          identifierCells,
          dataRegion: detected.dataRegion,
        });

        setShowDetectionSummary(true);
        setManualAdjustmentMode(false);
      }
    }
  }, [workbookData, sheetNames, currentSheet, onRawDataChange]);

  // Handle cell click for header/identifier selection (row/column based)
  const handleCellClick = (rowIndex: number, colIndex: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDragging) return;

    const cellKey = `${rowIndex},${colIndex}`;
    const wasAlreadySelected = selectedCell?.row === rowIndex && selectedCell?.col === colIndex;

    // Update selected cell for navigation (doesn't affect selections)
    setSelectedCell({ row: rowIndex, col: colIndex });
    setLastClickedCell({ row: rowIndex, col: colIndex });

    // In data mode: single-click on already-selected cell starts editing
    if (selectionMode === 'data' && wasAlreadySelected && !editingCell) {
      setEditingCell({ row: rowIndex, col: colIndex });
      setEditValue(String(sheetData[rowIndex]?.[colIndex]?.value || ''));
      return;
    }

    // Header mode: Toggle ENTIRE ROW
    if (selectionMode === 'header') {
      const newCells = new Set(selections.headerCells);
      const numCols = sheetData[0]?.length || 0;

      // Check if the clicked cell is already marked as header
      const isMarked = newCells.has(cellKey);

      // Toggle entire row based on clicked cell's current state
      for (let col = 0; col < numCols; col++) {
        const key = `${rowIndex},${col}`;
        if (isMarked) {
          newCells.delete(key);
        } else {
          newCells.add(key);
        }
      }
      setSelections(prev => ({ ...prev, headerCells: newCells }));
    }
    // Identifier mode: Toggle ENTIRE COLUMN
    else if (selectionMode === 'identifier') {
      const newCells = new Set(selections.identifierCells);
      const numRows = sheetData.length;

      // Check if the clicked cell is already marked as identifier
      const isMarked = newCells.has(cellKey);

      // Toggle entire column based on clicked cell's current state
      for (let row = 0; row < numRows; row++) {
        const key = `${row},${colIndex}`;
        if (isMarked) {
          newCells.delete(key);
        } else {
          newCells.add(key);
        }
      }
      setSelections(prev => ({ ...prev, identifierCells: newCells }));
    }
    // Data mode: only dragging creates data region, clicking just navigates
  };

  // Handle double-click for cell editing
  const handleDoubleClick = (rowIndex: number, colIndex: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingCell({ row: rowIndex, col: colIndex });
    setEditValue(String(sheetData[rowIndex]?.[colIndex]?.value || ''));
  };

  // Save edited cell value
  const saveEdit = () => {
    if (editingCell && sheetData[editingCell.row]?.[editingCell.col]) {
      const newData = [...sheetData];
      newData[editingCell.row][editingCell.col] = {
        ...newData[editingCell.row][editingCell.col],
        value: editValue,
      };
      setSheetData(newData);
    }
    setEditingCell(null);
    setEditValue('');
  };

  // Cancel editing
  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue('');
  };

  // Rectangle selection for ALL modes (headers, identifiers, data)
  const handleMouseDown = (rowIndex: number, colIndex: number, e: React.MouseEvent) => {
    e.preventDefault(); // Prevent text selection during drag
    e.stopPropagation();

    setIsDragging(true);
    setDragStart({ row: rowIndex, col: colIndex });
    setDragEnd({ row: rowIndex, col: colIndex });
  };

  const handleMouseMove = (rowIndex: number, colIndex: number, e: React.MouseEvent) => {
    if (isDragging) {
      e.preventDefault();
      setDragEnd({ row: rowIndex, col: colIndex });

      // Calculate auto-scroll direction
      const container = scrollContainerRef.current;
      if (container) {
        const rect = container.getBoundingClientRect();
        const THRESHOLD = 80;
        let scrollX = 0;
        let scrollY = 0;

        // Vertical scrolling
        if (e.clientY < rect.top + THRESHOLD) {
          scrollY = -1;
        } else if (e.clientY > rect.bottom - THRESHOLD) {
          scrollY = 1;
        }

        // Horizontal scrolling
        if (e.clientX < rect.left + THRESHOLD) {
          scrollX = -1;
        } else if (e.clientX > rect.right - THRESHOLD) {
          scrollX = 1;
        }

        setAutoScrollDirection({ x: scrollX, y: scrollY });
      }
    }
  };

  const handleMouseUp = () => {
    // Use dragEndRef for most current position
    const currentDragEnd = dragEndRef.current || dragEnd;

    if (isDragging && dragStart && currentDragEnd) {
      const startRow = Math.min(dragStart.row, currentDragEnd.row);
      const endRow = Math.max(dragStart.row, currentDragEnd.row);
      const startCol = Math.min(dragStart.col, currentDragEnd.col);
      const endCol = Math.max(dragStart.col, currentDragEnd.col);

      if (selectionMode === 'data') {
        // Save data region
        setSelections(prev => ({
          ...prev,
          dataRegion: { startRow, endRow, startCol, endCol },
        }));
      } else if (selectionMode === 'header') {
        // Add all cells in rectangle to headers
        const newCells = new Set(selections.headerCells);
        for (let r = startRow; r <= endRow; r++) {
          for (let c = startCol; c <= endCol; c++) {
            newCells.add(`${r},${c}`);
          }
        }
        setSelections(prev => ({ ...prev, headerCells: newCells }));
      } else if (selectionMode === 'identifier') {
        // Add all cells in rectangle to identifiers
        const newCells = new Set(selections.identifierCells);
        for (let r = startRow; r <= endRow; r++) {
          for (let c = startCol; c <= endCol; c++) {
            newCells.add(`${r},${c}`);
          }
        }
        setSelections(prev => ({ ...prev, identifierCells: newCells }));
      }
    }
    setIsDragging(false);
    setDragStart(null);
    setDragEnd(null);
    dragEndRef.current = null;
    setAutoScrollDirection({ x: 0, y: 0 });
  };

  // Continuous auto-scroll effect
  useEffect(() => {
    if (autoScrollDirection.x === 0 && autoScrollDirection.y === 0) {
      if (autoScrollRef.current) {
        cancelAnimationFrame(autoScrollRef.current);
        autoScrollRef.current = null;
      }
      return;
    }

    const scroll = () => {
      const container = scrollContainerRef.current;
      if (container && isDragging) {
        // Balanced scroll speeds
        const VERTICAL_SPEED = 8;
        const HORIZONTAL_SPEED = 12;
        container.scrollTop += autoScrollDirection.y * VERTICAL_SPEED;
        container.scrollLeft += autoScrollDirection.x * HORIZONTAL_SPEED;
        autoScrollRef.current = requestAnimationFrame(scroll);
      }
    };

    autoScrollRef.current = requestAnimationFrame(scroll);

    return () => {
      if (autoScrollRef.current) {
        cancelAnimationFrame(autoScrollRef.current);
      }
    };
  }, [autoScrollDirection, isDragging]);

  // Global mouse move handler for better drag detection
  useEffect(() => {
    if (!isDragging) return;

    const handleGlobalMouseMove = (e: MouseEvent) => {
      const container = scrollContainerRef.current;
      if (!container || !dragStart) return;

      const rect = container.getBoundingClientRect();
      const THRESHOLD = 100; // Distance from edge to trigger auto-scroll

      // Calculate auto-scroll direction
      let scrollX = 0;
      let scrollY = 0;
      if (e.clientY < rect.top + THRESHOLD) scrollY = -1;
      else if (e.clientY > rect.bottom - THRESHOLD) scrollY = 1;
      if (e.clientX < rect.left + THRESHOLD) scrollX = -1;
      else if (e.clientX > rect.right - THRESHOLD) scrollX = 1;

      setAutoScrollDirection({ x: scrollX, y: scrollY });

      // Find the actual element under the mouse
      const element = document.elementFromPoint(e.clientX, e.clientY);
      if (!element) return;

      // Find the closest TD or TH element
      const cell = element.closest('td, th');
      if (!cell) return;

      // Get row and column from data attributes
      const rowAttr = cell.getAttribute('data-row');
      const colAttr = cell.getAttribute('data-col');

      if (rowAttr !== null && colAttr !== null) {
        const row = parseInt(rowAttr, 10);
        const col = parseInt(colAttr, 10);

        // Skip header cells completely
        if (row === -1 || col === -1) return;

        // Update drag end position
        setDragEnd({ row, col });
        dragEndRef.current = { row, col };
      }
    };

    const handleGlobalMouseUp = () => {
      handleMouseUp();
    };

    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [isDragging, sheetData, columnWidths]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Exit fullscreen with Escape (highest priority)
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
        return;
      }

      // Cancel drag with Escape
      if (e.key === 'Escape' && isDragging) {
        setIsDragging(false);
        setDragStart(null);
        setDragEnd(null);
        dragEndRef.current = null;
        setAutoScrollDirection({ x: 0, y: 0 });
        return;
      }

      // F2 key - Start editing selected cell (Excel standard)
      if (e.key === 'F2' && !editingCell && selectedCell) {
        e.preventDefault();
        setEditingCell(selectedCell);
        setEditValue(String(sheetData[selectedCell.row]?.[selectedCell.col]?.value || ''));
        return;
      }

      // Arrow key navigation
      if (!editingCell && selectedCell && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
        const { row, col } = selectedCell;
        const maxRow = sheetData.length - 1;
        const maxCol = (sheetData[0]?.length || 1) - 1;

        let newRow = row;
        let newCol = col;

        if (e.key === 'ArrowUp' && row > 0) newRow = row - 1;
        if (e.key === 'ArrowDown' && row < maxRow) newRow = row + 1;
        if (e.key === 'ArrowLeft' && col > 0) newCol = col - 1;
        if (e.key === 'ArrowRight' && col < maxCol) newCol = col + 1;

        setSelectedCell({ row: newRow, col: newCol });
        setLastClickedCell({ row: newRow, col: newCol });
        return;
      }

      // Enter key - move down
      if (e.key === 'Enter' && !editingCell && selectedCell) {
        e.preventDefault();
        const maxRow = sheetData.length - 1;
        if (selectedCell.row < maxRow) {
          const newRow = selectedCell.row + 1;
          setSelectedCell({ row: newRow, col: selectedCell.col });
          setLastClickedCell({ row: newRow, col: selectedCell.col });
        }
        return;
      }

      // Tab key - move right (Shift+Tab for left)
      if (e.key === 'Tab' && !editingCell && selectedCell) {
        e.preventDefault();
        const maxCol = (sheetData[0]?.length || 1) - 1;

        if (e.shiftKey) {
          // Move left
          if (selectedCell.col > 0) {
            const newCol = selectedCell.col - 1;
            setSelectedCell({ row: selectedCell.row, col: newCol });
            setLastClickedCell({ row: selectedCell.row, col: newCol });
          }
        } else {
          // Move right
          if (selectedCell.col < maxCol) {
            const newCol = selectedCell.col + 1;
            setSelectedCell({ row: selectedCell.row, col: newCol });
            setLastClickedCell({ row: selectedCell.row, col: newCol });
          }
        }
        return;
      }

      // Delete key - clear cell content
      if (e.key === 'Delete' && !editingCell && selectedCell) {
        e.preventDefault();
        const newData = [...sheetData];
        newData[selectedCell.row][selectedCell.col] = {
          value: null,
          merged: false,
          isMergedCopy: false,
        };
        setSheetData(newData);
        return;
      }

      // Ctrl/Cmd + A - Select all in data mode
      if ((e.ctrlKey || e.metaKey) && e.key === 'a' && selectionMode === 'data') {
        e.preventDefault();
        const numRows = sheetData.length;
        const numCols = sheetData[0]?.length || 0;
        setSelections(prev => ({
          ...prev,
          dataRegion: { startRow: 0, endRow: numRows - 1, startCol: 0, endCol: numCols - 1 },
        }));
        return;
      }

      // Ctrl+A - Select all data
      if ((e.ctrlKey || e.metaKey) && e.key === 'a' && !editingCell) {
        e.preventDefault();
        if (selectionMode === 'data') {
          const numRows = sheetData.length;
          const numCols = sheetData[0]?.length || 0;
          setSelections(prev => ({
            ...prev,
            dataRegion: { startRow: 0, endRow: numRows - 1, startCol: 0, endCol: numCols - 1 },
          }));
        }
        return;
      }

      // Delete selected cells
      if (e.key === 'Delete' && !editingCell) {
        e.preventDefault();
        const newData = [...sheetData];

        // Delete data region cells
        if (selections.dataRegion) {
          const { startRow, endRow, startCol, endCol } = selections.dataRegion;
          for (let r = startRow; r <= endRow; r++) {
            for (let c = startCol; c <= endCol; c++) {
              if (newData[r] && newData[r][c]) {
                newData[r][c] = { value: null, merged: false, isMergedCopy: false };
              }
            }
          }
        }

        // Delete header cells
        selections.headerCells.forEach(key => {
          const [r, c] = key.split(',').map(Number);
          if (newData[r] && newData[r][c]) {
            newData[r][c] = { value: null, merged: false, isMergedCopy: false };
          }
        });

        // Delete identifier cells
        selections.identifierCells.forEach(key => {
          const [r, c] = key.split(',').map(Number);
          if (newData[r] && newData[r][c]) {
            newData[r][c] = { value: null, merged: false, isMergedCopy: false };
          }
        });

        setSheetData(newData);
      }

      // Copy (Ctrl+C or Cmd+C)
      if ((e.ctrlKey || e.metaKey) && e.key === 'c' && !editingCell) {
        e.preventDefault();
        let copyText = '';

        if (selections.dataRegion) {
          const { startRow, endRow, startCol, endCol } = selections.dataRegion;
          for (let r = startRow; r <= endRow; r++) {
            const rowValues = [];
            for (let c = startCol; c <= endCol; c++) {
              rowValues.push(sheetData[r]?.[c]?.value?.toString() || '');
            }
            copyText += rowValues.join('\t') + '\n';
          }
        }

        navigator.clipboard.writeText(copyText);
      }

      // Paste (Ctrl+V or Cmd+V)
      if ((e.ctrlKey || e.metaKey) && e.key === 'v' && !editingCell && lastClickedCell) {
        e.preventDefault();
        navigator.clipboard.readText().then(text => {
          const rows = text.split('\n').filter(r => r.trim());
          const newData = [...sheetData];

          rows.forEach((row, rOffset) => {
            const cells = row.split('\t');
            cells.forEach((cellValue, cOffset) => {
              const targetRow = lastClickedCell.row + rOffset;
              const targetCol = lastClickedCell.col + cOffset;

              if (newData[targetRow] && newData[targetRow][targetCol]) {
                newData[targetRow][targetCol] = {
                  value: cellValue,
                  merged: false,
                  isMergedCopy: false,
                };
              }
            });
          });

          setSheetData(newData);
        });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDragging, editingCell, selections, sheetData, lastClickedCell, isFullscreen]);

  // Check if cell is in drag selection - use ref for most current value
  const isInDragSelection = useCallback((rowIndex: number, colIndex: number) => {
    // Use dragEndRef for the most up-to-date position
    const currentDragEnd = dragEndRef.current || dragEnd;

    if (!isDragging || !dragStart || !currentDragEnd) return false;
    const minRow = Math.min(dragStart.row, currentDragEnd.row);
    const maxRow = Math.max(dragStart.row, currentDragEnd.row);
    const minCol = Math.min(dragStart.col, currentDragEnd.col);
    const maxCol = Math.max(dragStart.col, currentDragEnd.col);
    return rowIndex >= minRow && rowIndex <= maxRow && colIndex >= minCol && colIndex <= maxCol;
  }, [isDragging, dragStart, dragEnd]);

  // Check if cell is in saved data region
  const isInDataRegion = (rowIndex: number, colIndex: number) => {
    const region = selections.dataRegion;
    if (!region) return false;
    return rowIndex >= region.startRow && rowIndex <= region.endRow &&
           colIndex >= region.startCol && colIndex <= region.endCol;
  };

  const getCellClassName = (rowIndex: number, colIndex: number) => {
    const classes = ['px-2.5 py-1.5 text-sm border-r border-b transition-all group whitespace-nowrap relative font-normal'];
    const cellKey = `${rowIndex},${colIndex}`;
    const isSelected = selectedCell?.row === rowIndex && selectedCell?.col === colIndex;

    // Excel-like border colors
    const defaultBorder = 'border-slate-300';
    const selectBorder = 'border-[var(--sentry-blue)]';

    // Zebra striping for alternating rows
    const isEvenRow = rowIndex % 2 === 0;

    // Priority: selected cell > dragging > saved selections
    if (isSelected && !editingCell) {
      classes.push(`bg-white ring-2 ring-[var(--sentry-blue)] ring-inset z-10 ${selectBorder} shadow-sm`);
    } else if (isInDragSelection(rowIndex, colIndex)) {
      // Show drag selection with mode-specific colors
      if (selectionMode === 'header') {
        classes.push('bg-green-100 border-green-400 border-2');
      } else if (selectionMode === 'identifier') {
        classes.push('bg-blue-100 border-blue-400 border-2');
      } else if (selectionMode === 'data') {
        classes.push('bg-purple-100 border-purple-400 border-2');
      }
    } else if (isInDataRegion(rowIndex, colIndex)) {
      classes.push(`bg-purple-50 border-purple-300 ${defaultBorder}`);
    } else if (selections.headerCells.has(cellKey)) {
      classes.push(`bg-green-50 border-green-300 ${defaultBorder}`);
    } else if (selections.identifierCells.has(cellKey)) {
      classes.push(`bg-blue-100 border-blue-400 ${defaultBorder}`);
    } else {
      // Alternating row colors (zebra striping) + hover effect
      const baseColor = isEvenRow ? 'bg-white' : 'bg-slate-50';
      const hoverColor = isEvenRow ? 'hover:bg-blue-50' : 'hover:bg-blue-100';
      classes.push(`${baseColor} ${hoverColor} ${defaultBorder}`);
    }

    // Cursor styles
    classes.push('cursor-cell select-none');

    return classes.join(' ');
  };

  // Column resizing handlers
  const handleResizeStart = (colIndex: number, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setResizingCol(colIndex);
    setResizeStartX(e.clientX);
    const currentWidth = columnWidths[colIndex] || 100;
    setResizeStartWidth(currentWidth);
  };

  // Auto-fit column width on double-click
  const handleAutoFitColumn = (colIndex: number, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Calculate max content width for this column
    let maxWidth = 60; // Minimum width
    sheetData.forEach(row => {
      const cellValue = row[colIndex]?.value?.toString() || '';
      // Rough estimate: 8px per character + padding
      const estimatedWidth = cellValue.length * 8 + 24;
      maxWidth = Math.max(maxWidth, estimatedWidth);
    });

    // Cap at 400px to prevent extremely wide columns
    maxWidth = Math.min(maxWidth, 400);

    setColumnWidths(prev => ({ ...prev, [colIndex]: maxWidth }));
  };

  useEffect(() => {
    if (resizingCol === null) return;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - resizeStartX;
      const newWidth = Math.max(60, resizeStartWidth + delta); // Min 60px
      setColumnWidths(prev => ({ ...prev, [resizingCol]: newWidth }));
      setResizeTooltipWidth(newWidth); // Show tooltip with current width
    };

    const handleMouseUp = () => {
      setResizingCol(null);
      setResizeTooltipWidth(null); // Hide tooltip
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [resizingCol, resizeStartX, resizeStartWidth]);

  // Add row to the bottom
  const addRow = () => {
    const numCols = sheetData[0]?.length || 0;
    const newRow: CellData[] = Array(numCols).fill(null).map(() => ({
      value: null,
      merged: false,
      isMergedCopy: false,
    }));
    setSheetData([...sheetData, newRow]);
  };

  // Add column to the right
  const addColumn = () => {
    const newData = sheetData.map(row => [
      ...row,
      { value: null, merged: false, isMergedCopy: false },
    ]);
    setSheetData(newData);
  };

  // Delete selected row
  const deleteRow = (rowIndex: number) => {
    if (sheetData.length <= 1) return; // Don't delete last row
    const newData = sheetData.filter((_, idx) => idx !== rowIndex);
    setSheetData(newData);

    // Clear selections that reference this row
    const newHeaderCells = new Set<string>();
    selections.headerCells.forEach(key => {
      const [row, col] = key.split(',').map(Number);
      if (row !== rowIndex) {
        // Shift rows down if after deleted row
        const newRow = row > rowIndex ? row - 1 : row;
        newHeaderCells.add(`${newRow},${col}`);
      }
    });

    const newIdentifierCells = new Set<string>();
    selections.identifierCells.forEach(key => {
      const [row, col] = key.split(',').map(Number);
      if (row !== rowIndex) {
        const newRow = row > rowIndex ? row - 1 : row;
        newIdentifierCells.add(`${newRow},${col}`);
      }
    });

    setSelections(prev => ({
      headerCells: newHeaderCells,
      identifierCells: newIdentifierCells,
      dataRegion: prev.dataRegion,
    }));
  };

  // Delete selected column
  const deleteColumn = (colIndex: number) => {
    if (sheetData[0]?.length <= 1) return; // Don't delete last column
    const newData = sheetData.map(row =>
      row.filter((_, idx) => idx !== colIndex),
    );
    setSheetData(newData);

    // Clear selections that reference this column
    const newHeaderCells = new Set<string>();
    selections.headerCells.forEach(key => {
      const [row, col] = key.split(',').map(Number);
      if (col !== colIndex) {
        const newCol = col > colIndex ? col - 1 : col;
        newHeaderCells.add(`${row},${newCol}`);
      }
    });

    const newIdentifierCells = new Set<string>();
    selections.identifierCells.forEach(key => {
      const [row, col] = key.split(',').map(Number);
      if (col !== colIndex) {
        const newCol = col > colIndex ? col - 1 : col;
        newIdentifierCells.add(`${row},${newCol}`);
      }
    });

    setSelections(prev => ({
      headerCells: newHeaderCells,
      identifierCells: newIdentifierCells,
      dataRegion: prev.dataRegion,
    }));
  };

  // Select entire row (only in data mode, with Ctrl/Cmd key)
  const handleRowClick = (rowIndex: number, e: React.MouseEvent) => {
    e.stopPropagation();

    // Only change data region if Ctrl/Cmd is held
    if (selectionMode === 'data' && (e.ctrlKey || e.metaKey)) {
      const numCols = sheetData[0]?.length || 0;
      setSelections(prev => ({
        ...prev,
        dataRegion: { startRow: rowIndex, endRow: rowIndex, startCol: 0, endCol: numCols - 1 },
      }));
    }
    setSelectedCell({ row: rowIndex, col: 0 });
  };

  // Select entire column (only in data mode, with Ctrl/Cmd key)
  const handleColumnClick = (colIndex: number, e: React.MouseEvent) => {
    e.stopPropagation();

    // Only change data region if Ctrl/Cmd is held
    if (selectionMode === 'data' && (e.ctrlKey || e.metaKey)) {
      const numRows = sheetData.length;
      setSelections(prev => ({
        ...prev,
        dataRegion: { startRow: 0, endRow: numRows - 1, startCol: colIndex, endCol: colIndex },
      }));
    }
    setSelectedCell({ row: 0, col: colIndex });
  };

  // Get cell address (e.g., "B5")
  const getCellAddress = (row: number, col: number) => {
    const colLetter = String.fromCharCode(65 + (col % 26)) + (col >= 26 ? String.fromCharCode(65 + Math.floor(col / 26) - 1) : '');
    return `${colLetter}${row + 1}`;
  };

  // Select all cells (corner cell click)
  const handleSelectAll = () => {
    if (selectionMode === 'data') {
      const numRows = sheetData.length;
      const numCols = sheetData[0]?.length || 0;
      setSelections(prev => ({
        ...prev,
        dataRegion: { startRow: 0, endRow: numRows - 1, startCol: 0, endCol: numCols - 1 },
      }));
    }
  };

  // Detect if cell value is a number
  const isNumeric = (value: any): boolean => {
    if (value === null || value === undefined || value === '') return false;
    return !isNaN(Number(value)) && !isNaN(parseFloat(String(value)));
  };

  // Format cell value for display
  const formatCellValue = (value: any): string => {
    if (value === null || value === undefined) return '';

    const str = String(value);

    // Check for percentage (contains % symbol)
    if (str.includes('%')) {
      return str;
    }

    // Check for currency (starts with $ or contains currency symbols)
    if (str.match(/^[\$€£¥]/) || str.match(/[\$€£¥]/)) {
      const num = parseFloat(str.replace(/[^\d.-]/g, ''));
      if (!isNaN(num)) {
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 2,
        }).format(num);
      }
      return str;
    }

    // Format regular numbers with thousands separator
    if (isNumeric(value)) {
      const num = Number(value);
      // If it has decimals, show up to 2 decimal places
      if (num % 1 !== 0) {
        return new Intl.NumberFormat('en-US', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        }).format(num);
      }
      // Integer - add thousands separator
      return new Intl.NumberFormat('en-US').format(num);
    }

    return str;
  };

  // Get text alignment class based on cell value
  const getCellAlignment = (value: any): string => {
    if (isNumeric(value)) return 'text-right';
    return 'text-left';
  };

  // Convert sheetData to simple 2D array for ParsedPreview
  const rawDataArray = useMemo(() => {
    return sheetData.map(row => row.map(cell => cell.value));
  }, [sheetData]);

  // Data prep operations
  const handleTrimAll = () => {
    console.log('handleTrimAll called, sheetData rows:', sheetData.length);
    const newData = sheetData.map(row =>
      row.map(cell => ({
        ...cell,
        value: typeof cell.value === 'string' ? cell.value.trim() : cell.value,
      })),
    );

    console.log('Executing trim operation through history manager');
    historyManager.execute(
      {
        type: 'trim',
        description: 'Trim all cells',
      },
      newData,
    );
    console.log('Trim operation complete');
  };

  const handleApplyFindReplace = (newData: CellData[][], description: string) => {
    historyManager.execute(
      {
        type: 'find_replace',
        description,
      },
      newData,
    );
  };

  const handleApplyRemoveDuplicates = (newData: CellData[][], description: string) => {
    historyManager.execute(
      {
        type: 'remove_duplicates',
        description,
      },
      newData,
    );
  };

  // Context Menu Handlers
  const handleInsertRowAbove = () => {
    if (!selectedCell) return;
    const newData = [...sheetData];
    const emptyRow = Array(newData[0].length).fill(null).map(() => ({ value: null }));
    newData.splice(selectedCell.row, 0, emptyRow);
    historyManager.execute({ type: 'insert_row', description: `Insert row above ${selectedCell.row + 1}` }, newData);
    setContextMenu(null);
  };

  const handleInsertRowBelow = () => {
    if (!selectedCell) return;
    const newData = [...sheetData];
    const emptyRow = Array(newData[0].length).fill(null).map(() => ({ value: null }));
    newData.splice(selectedCell.row + 1, 0, emptyRow);
    historyManager.execute({ type: 'insert_row', description: `Insert row below ${selectedCell.row + 1}` }, newData);
    setContextMenu(null);
  };

  const handleInsertColumnLeft = () => {
    if (!selectedCell) return;
    const newData = sheetData.map(row => {
      const newRow = [...row];
      newRow.splice(selectedCell.col, 0, { value: null });
      return newRow;
    });
    historyManager.execute({ type: 'insert_column', description: `Insert column left of ${selectedCell.col + 1}` }, newData);
    setContextMenu(null);
  };

  const handleInsertColumnRight = () => {
    if (!selectedCell) return;
    const newData = sheetData.map(row => {
      const newRow = [...row];
      newRow.splice(selectedCell.col + 1, 0, { value: null });
      return newRow;
    });
    historyManager.execute({ type: 'insert_column', description: `Insert column right of ${selectedCell.col + 1}` }, newData);
    setContextMenu(null);
  };

  const handleContextDeleteRow = () => {
    if (!selectedCell) return;
    const newData = sheetData.filter((_, idx) => idx !== selectedCell.row);
    historyManager.execute({ type: 'delete_row', description: `Delete row ${selectedCell.row + 1}` }, newData);
    setContextMenu(null);
  };

  const handleContextDeleteColumn = () => {
    if (!selectedCell) return;
    const newData = sheetData.map(row => row.filter((_, idx) => idx !== selectedCell.col));
    historyManager.execute({ type: 'delete_column', description: `Delete column ${selectedCell.col + 1}` }, newData);
    setContextMenu(null);
  };

  const handleClearContents = () => {
    if (!selectedCell) return;
    const newData = sheetData.map((row, rowIdx) =>
      row.map((cell, colIdx) =>
        rowIdx === selectedCell.row && colIdx === selectedCell.col ? { value: null } : cell,
      ),
    );
    historyManager.execute({ type: 'clear', description: 'Clear cell contents' }, newData);
    setContextMenu(null);
  };

  const handleDuplicateRow = () => {
    if (!selectedCell) return;
    const newData = [...sheetData];
    const duplicatedRow = sheetData[selectedCell.row].map(cell => ({ ...cell }));
    newData.splice(selectedCell.row + 1, 0, duplicatedRow);
    historyManager.execute({ type: 'duplicate_row', description: `Duplicate row ${selectedCell.row + 1}` }, newData);
    setContextMenu(null);
  };

  const handleCopy = () => {
    if (!selectedCell) return;
    const copiedData = [[sheetData[selectedCell.row][selectedCell.col]]];
    setClipboard(copiedData);
    setClipboardMode('copy');
    setContextMenu(null);
  };

  const handleCut = () => {
    if (!selectedCell) return;
    const copiedData = [[sheetData[selectedCell.row][selectedCell.col]]];
    setClipboard(copiedData);
    setClipboardMode('cut');
    const newData = sheetData.map((row, rowIdx) =>
      row.map((cell, colIdx) =>
        rowIdx === selectedCell.row && colIdx === selectedCell.col ? { value: null } : cell,
      ),
    );
    historyManager.execute({ type: 'cut', description: 'Cut cell' }, newData);
    setContextMenu(null);
  };

  const handlePaste = () => {
    if (!selectedCell || !clipboard) return;
    const newData = sheetData.map((row, rowIdx) =>
      row.map((cell, colIdx) => {
        if (rowIdx === selectedCell.row && colIdx === selectedCell.col) {
          return { ...clipboard[0][0] };
        }
        return cell;
      }),
    );
    historyManager.execute({ type: 'paste', description: 'Paste cell' }, newData);
    if (clipboardMode === 'cut') {
      setClipboard(null);
      setClipboardMode(null);
    }
    setContextMenu(null);
  };

  const handleCellRightClick = (e: React.MouseEvent, row: number, col: number) => {
    e.preventDefault();
    setSelectedCell({ row, col });
    setContextMenu({ x: e.clientX, y: e.clientY });
  };

  // Column Filter Handlers
  const handleColumnFilterClick = (e: React.MouseEvent, colIdx: number) => {
    e.stopPropagation();
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    setColumnFilter({
      columnIndex: colIdx,
      x: rect.left,
      y: rect.bottom + 4,
    });
  };

  const handleColumnSort = (colIdx: number, direction: 'asc' | 'desc') => {
    const newData = [...sheetData];
    newData.sort((a, b) => {
      const aVal = a[colIdx]?.value;
      const bVal = b[colIdx]?.value;

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return direction === 'asc' ? 1 : -1;
      if (bVal == null) return direction === 'asc' ? -1 : 1;

      const aStr = String(aVal);
      const bStr = String(bVal);

      return direction === 'asc'
        ? aStr.localeCompare(bStr, undefined, { numeric: true })
        : bStr.localeCompare(aStr, undefined, { numeric: true });
    });

    historyManager.execute({ type: 'sort', description: `Sort column ${colIdx + 1} ${direction}` }, newData);
    setColumnFilter(null);
  };

  const handleColumnFilter = (colIdx: number, selectedValues: Set<string>) => {
    const newData = sheetData.filter(row => {
      const cellValue = row[colIdx]?.value;
      const valueStr = cellValue == null ? '(Blank)' : String(cellValue);
      return selectedValues.has(valueStr);
    });

    historyManager.execute({ type: 'filter', description: `Filter column ${colIdx + 1}` }, newData);
    setColumnFilter(null);
  };

  // Update history manager and propagate raw data when sheet data changes
  useEffect(() => {
    historyManager.updateCurrentData(sheetData);
    const rawValues = sheetData.map(row => row.map(cell => cell.value));
    onRawDataChange?.(rawValues);
  }, [sheetData, historyManager, onRawDataChange]);

  // Keyboard shortcuts for data prep
  useEffect(() => {
    const handleDataPrepShortcuts = (e: KeyboardEvent) => {
      // Ctrl+H - Find & Replace
      if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault();
        setShowFindReplace(true);
        return;
      }

      // Ctrl+Z - Undo
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        historyManager.undo();
        return;
      }

      // Ctrl+Y or Ctrl+Shift+Z - Redo
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        historyManager.redo();
        return;
      }
    };

    window.addEventListener('keydown', handleDataPrepShortcuts);
    return () => window.removeEventListener('keydown', handleDataPrepShortcuts);
  }, [historyManager]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className={`w-[95vw] max-w-[1800px] flex flex-col h-[95vh] bg-white rounded-lg shadow-2xl ${resizingCol !== null ? 'cursor-col-resize' : ''} relative overflow-hidden`}>
      {/* Resize width tooltip */}
      {resizeTooltipWidth !== null && (
        <div className="fixed z-50 px-2 py-1 bg-slate-800 text-white text-xs rounded shadow-lg pointer-events-none" style={{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }}>
          {resizeTooltipWidth}px
        </div>
      )}
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--sentry-gray-300)]">
        <div>
          <h3 className="text-lg font-semibold text-[var(--sentry-navy)]">
            Configure Table Structure
          </h3>
          <p className="text-sm text-[var(--sentry-gray-600)] mt-1">
            💡 <strong>Excel shortcuts</strong>: Arrow keys/Enter/Tab to navigate • Click twice or F2 to edit • Ctrl+C/V to copy/paste • Delete to clear • Drag edges to resize • <span className="text-[var(--sentry-blue)] font-medium">Drag cells to select data region</span>
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-[var(--sentry-gray-200)] rounded-md transition-colors"
        >
          <X size={20} />
        </button>
      </div>


      {/* Auto-Detection Summary */}
      {showDetectionSummary && detectionResult && (
        <div className="p-4 border-b border-[var(--sentry-gray-300)]">
          <DetectionSummary
            headerCount={detectionResult.headers.rows.length}
            identifierCount={detectionResult.identifiers.columns.length}
            dataRowCount={detectionResult.dataRegion.endRow - detectionResult.dataRegion.startRow + 1}
            confidence={calculateOverallConfidence(detectionResult)}
            onAccept={() => {
              console.log('Confirm & Parse clicked - selections:', {
                headerCells: selections.headerCells.size,
                identifierCells: selections.identifierCells.size,
                dataRegion: selections.dataRegion,
                identifierCellsSample: Array.from(selections.identifierCells).slice(0, 5),
              });
              setShowDetectionSummary(false);
              onStartParsing(selections);
            }}
            onAdjust={() => {
              setShowDetectionSummary(false);
              setManualAdjustmentMode(true);
            }}
          />
        </div>
      )}

      {/* Manual Adjustment Panel (collapsible) */}
      {manualAdjustmentMode && (
        <div className="flex items-center gap-2 p-4 border-b border-[var(--sentry-gray-300)]">
          {/* Edit buttons */}
          <div className="flex gap-1 mr-4 border-r pr-4 border-slate-300">
            <button
              onClick={addRow}
              className="px-3 py-1 text-xs bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors"
              title="Add row at bottom"
            >
              + Row
            </button>
            <button
              onClick={addColumn}
              className="px-3 py-1 text-xs bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors"
              title="Add column at right"
            >
              + Column
            </button>
            {selectedCell && (
              <>
                <button
                  onClick={() => deleteRow(selectedCell.row)}
                  className="px-3 py-1 text-xs bg-white border border-red-300 text-red-600 rounded hover:bg-red-50 transition-colors"
                  title={`Delete row ${selectedCell.row + 1}`}
                  disabled={sheetData.length <= 1}
                >
                  - Row {selectedCell.row + 1}
                </button>
                <button
                  onClick={() => deleteColumn(selectedCell.col)}
                  className="px-3 py-1 text-xs bg-white border border-red-300 text-red-600 rounded hover:bg-red-50 transition-colors"
                  title={`Delete column ${String.fromCharCode(65 + selectedCell.col)}`}
                  disabled={sheetData[0]?.length <= 1}
                >
                  - Col {String.fromCharCode(65 + selectedCell.col)}
                </button>
              </>
            )}
          </div>

          <button
            onClick={() => setSelectionMode('header')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors
              ${selectionMode === 'header'
                ? 'bg-green-500 text-white'
                : 'bg-[var(--sentry-gray-200)] text-[var(--sentry-navy)] hover:bg-[var(--sentry-gray-300)]'
              }
            `}
          >
            <CheckSquare size={16} />
            Headers ({selections.headerCells.size})
          </button>
          <button
            onClick={() => setSelectionMode('identifier')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors
              ${selectionMode === 'identifier'
                ? 'bg-blue-500 text-white'
                : 'bg-[var(--sentry-gray-200)] text-[var(--sentry-navy)] hover:bg-[var(--sentry-gray-300)]'
              }
            `}
          >
            <CheckSquare size={16} />
            Identifiers ({selections.identifierCells.size})
          </button>
          <button
            onClick={() => setSelectionMode('data')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors
              ${selectionMode === 'data'
                ? 'bg-purple-500 text-white'
                : 'bg-[var(--sentry-gray-200)] text-[var(--sentry-navy)] hover:bg-[var(--sentry-gray-300)]'
              }
            `}
          >
            <Square size={16} />
            Data Region {selections.dataRegion ? '✓' : ''}
          </button>
          {selections.dataRegion && (
            <button
              onClick={() => setSelections(prev => ({ ...prev, dataRegion: null }))}
              className="px-3 py-2 rounded-md text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              Clear Region
            </button>
          )}
          <button
            onClick={() => setSelections({
              headerCells: new Set(),
              identifierCells: new Set(),
              dataRegion: null,
            })}
            className="px-3 py-2 rounded-md text-sm text-slate-600 hover:bg-slate-100 transition-colors border border-slate-300"
            title="Clear all selections and start fresh"
          >
            Clear All
          </button>
          <div className="flex-1" />
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="flex items-center gap-2 px-3 py-2 rounded-md text-sm bg-[var(--sentry-gray-200)] text-[var(--sentry-navy)] hover:bg-[var(--sentry-gray-300)] transition-colors"
            title={isFullscreen ? 'Exit fullscreen (Esc)' : 'Expand to fullscreen'}
          >
            {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            {isFullscreen ? 'Exit Fullscreen' : 'Expand'}
          </button>
          <p className="text-xs text-[var(--sentry-gray-500)]">
            {selectionMode === 'header' && 'Click any cell to toggle entire row as header'}
            {selectionMode === 'identifier' && 'Click any cell to toggle entire column as identifier'}
            {selectionMode === 'data' && 'Drag to select data region (Esc to cancel)'}
          </p>
        </div>
      )}

      {/* Data Prep Toolbar */}
      <DataPrepToolbar
        historyManager={historyManager}
        sheetData={sheetData}
        onTrimAll={handleTrimAll}
        onFindReplace={() => setShowFindReplace(true)}
        onRemoveDuplicates={() => setShowRemoveDuplicates(true)}
        selectedCell={selectedCell}
      />

        {/* Split-screen: Raw Grid + Parsed Preview */}
        <div className={`flex-1 ${isFullscreen ? 'flex' : 'grid grid-cols-2'} gap-4 p-4 overflow-hidden`}>
          {/* Excel-like Grid */}
          <div ref={scrollContainerRef} className={`border border-slate-300 rounded-lg overflow-auto bg-white shadow-sm ${isFullscreen ? 'flex-1' : ''}`}>
              <table className="border-collapse table-auto" onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
                <thead className="sticky top-0 z-20 bg-white border-b border-slate-300">
                  <tr>
                    {/* Corner cell - click to select all */}
                    <th
                      onClick={handleSelectAll}
                      className="w-12 h-9 bg-gradient-to-br from-slate-50 to-slate-100 border-r border-b border-slate-300 sticky left-0 z-30 cursor-pointer hover:bg-slate-200 transition-colors shadow-sm"
                      title="Click to select all (or Ctrl+A)"
                    >
                      <div className="flex items-center justify-center text-slate-400 hover:text-slate-700 transition-colors">
                        <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor">
                          <path d="M0 0h5v5H0zM7 0h5v5H7zM0 7h5v5H0zM7 7h5v5H7z"/>
                        </svg>
                      </div>
                    </th>
                    {/* Column letters A, B, C, ... */}
                    {sheetData[0]?.map((_, colIndex) => {
                      const width = columnWidths[colIndex] || 100;
                      return (
                        <th
                          key={colIndex}
                          data-row={-1}
                          data-col={colIndex}
                          onClick={(e) => handleColumnClick(colIndex, e)}
                          className="h-9 px-3 text-[11px] font-semibold text-slate-700 bg-gradient-to-b from-slate-50 to-slate-100 border-r border-b border-slate-300 text-center whitespace-nowrap relative group cursor-pointer hover:bg-slate-200 transition-colors shadow-sm"
                          style={{
                            width: `${width}px`,
                            minWidth: `${width}px`,
                            maxWidth: `${width}px`,
                          }}
                          title={`Ctrl+Click to select entire column ${String.fromCharCode(65 + (colIndex % 26))}`}
                        >
                          <div className="flex items-center justify-center gap-1">
                            <span>
                              {String.fromCharCode(65 + (colIndex % 26))}
                              {colIndex >= 26 && String.fromCharCode(65 + Math.floor(colIndex / 26) - 1)}
                            </span>
                            {/* Filter/Sort dropdown button */}
                            <button
                              onClick={(e) => handleColumnFilterClick(e, colIndex)}
                              className="opacity-0 group-hover:opacity-100 hover:bg-slate-300 rounded p-0.5 transition-all"
                              title="Filter & Sort"
                            >
                              <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor">
                                <path d="M0 2h12L7 8v3l-2 1V8L0 2z"/>
                              </svg>
                            </button>
                          </div>
                          {/* Resize handle */}
                          <div
                            onMouseDown={(e) => handleResizeStart(colIndex, e)}
                            onDoubleClick={(e) => handleAutoFitColumn(colIndex, e)}
                            className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-blue-500 group-hover:bg-blue-300 transition-colors z-20"
                            title="Drag to resize • Double-click to auto-fit"
                          />
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {sheetData.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {/* Row number */}
                      <td
                        data-row={rowIndex}
                        data-col={-1}
                        onClick={(e) => handleRowClick(rowIndex, e)}
                        className="w-12 min-h-[32px] px-2 text-[11px] font-semibold text-slate-700 bg-gradient-to-r from-slate-50 to-slate-100 border-r border-b border-slate-300 text-center sticky left-0 z-10 cursor-pointer hover:bg-slate-200 transition-colors shadow-sm"
                        style={{ pointerEvents: isDragging ? 'none' : 'auto' }}
                        title={`Ctrl+Click to select entire row ${rowIndex + 1}`}
                      >
                        {rowIndex + 1}
                      </td>
                      {row.map((cell, colIndex) => {
                        const isEditing = editingCell?.row === rowIndex && editingCell?.col === colIndex;
                        const width = columnWidths[colIndex] || 100;
                        return (
                          <td
                            key={colIndex}
                            data-row={rowIndex}
                            data-col={colIndex}
                            className={`${getCellClassName(rowIndex, colIndex)} ${getCellAlignment(cell.value)}`}
                            style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                            onClick={(e) => handleCellClick(rowIndex, colIndex, e)}
                            onDoubleClick={(e) => handleDoubleClick(rowIndex, colIndex, e)}
                            onMouseDown={(e) => handleMouseDown(rowIndex, colIndex, e)}
                            onMouseMove={(e) => handleMouseMove(rowIndex, colIndex, e)}
                            onContextMenu={(e) => handleCellRightClick(e, rowIndex, colIndex)}
                          >
                            {isEditing ? (
                              <input
                                type="text"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onBlur={saveEdit}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    saveEdit();
                                  }
                                  if (e.key === 'Escape') {
                                    e.preventDefault();
                                    cancelEdit();
                                  }
                                }}
                                className="w-full h-full absolute inset-0 px-2.5 py-1.5 text-sm border-0 outline-none bg-white ring-2 ring-inset ring-[var(--sentry-blue)]"
                                autoFocus
                                onClick={(e) => e.stopPropagation()}
                              />
                            ) : (
                              <div className="min-w-[60px] relative group flex items-center gap-2">
                                <span className="flex-1">{formatCellValue(cell.value)}</span>
                                {cell.isMergedCopy && (
                                  <span className="text-xs text-[var(--sentry-gray-400)] ml-1">
                                    ↖
                                  </span>
                                )}
                                {/* Cell annotations for headers and identifiers */}
                                {selections.headerCells.has(`${rowIndex},${colIndex}`) && (
                                  <CellAnnotation
                                    type="header"
                                    onRemove={() => {
                                      const newCells = new Set(selections.headerCells);
                                      newCells.delete(`${rowIndex},${colIndex}`);
                                      setSelections(prev => ({ ...prev, headerCells: newCells }));
                                    }}
                                    tooltip="Header cell - click to remove"
                                  />
                                )}
                                {selections.identifierCells.has(`${rowIndex},${colIndex}`) && (
                                  <CellAnnotation
                                    type="identifier"
                                    onRemove={() => {
                                      const newCells = new Set(selections.identifierCells);
                                      newCells.delete(`${rowIndex},${colIndex}`);
                                      setSelections(prev => ({ ...prev, identifierCells: newCells }));
                                    }}
                                    tooltip="ID column - click to remove"
                                  />
                                )}
                                {/* Edit hint for selected cell in data mode */}
                                {selectedCell?.row === rowIndex && selectedCell?.col === colIndex && selectionMode === 'data' && (
                                  <span className="absolute right-1 top-1 text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
                                    ✎
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
          </div>

          {/* Right: Parsed Preview (hidden in fullscreen) */}
          {!isFullscreen && (
            <div className="border border-[var(--sentry-gray-300)] rounded-lg overflow-hidden flex flex-col">
              <div className="p-2 bg-[var(--sentry-gray-100)] border-b border-[var(--sentry-gray-300)]">
                <p className="text-sm font-medium text-[var(--sentry-navy)]">
                  Parsed Output Preview
                </p>
              </div>
              <div className="flex-1 overflow-auto p-2">
                <ParsedPreview rawData={rawDataArray} selections={selections} />
              </div>
            </div>
          )}
        </div>

      {/* Sheet Tabs - Excel style at bottom */}
      {sheetNames.length > 1 && (
        <div className="flex items-center gap-1 px-2 py-1 bg-slate-100 border-t border-[var(--sentry-gray-300)] overflow-x-auto">
          {sheetNames.map((name, index) => (
            <button
              key={index}
              onClick={() => setCurrentSheet(index)}
              className={`px-4 py-1.5 text-xs font-medium transition-all border-r border-slate-300 ${
                currentSheet === index
                  ? 'bg-white text-slate-900 border-t-2 border-t-[var(--sentry-blue)] -mt-px'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      {/* Status Bar - Excel style */}
      <div className="flex items-center gap-4 px-4 py-1.5 bg-slate-50 border-t border-[var(--sentry-gray-300)] text-xs">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-700">
            {selectedCell ? getCellAddress(selectedCell.row, selectedCell.col) : 'No cell selected'}
          </span>
          {selectedCell && sheetData[selectedCell.row]?.[selectedCell.col]?.value && (
            <span className="text-slate-500">
              | {String(sheetData[selectedCell.row][selectedCell.col].value)}
            </span>
          )}
        </div>
        <div className="flex-1" />
        <span className="text-slate-500">
          {sheetData.length} rows × {sheetData[0]?.length || 0} columns
        </span>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between p-4 border-t border-[var(--sentry-gray-300)] bg-white">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelections({ headerCells: new Set(), identifierCells: new Set(), dataRegion: null })}
            className="px-4 py-2 rounded-md bg-[var(--sentry-gray-200)] text-[var(--sentry-navy)] hover:bg-[var(--sentry-gray-300)] transition-colors text-sm"
          >
            Clear All
          </button>
          <span className="text-xs text-slate-500">
            {selections.headerCells.size > 0 && `${selections.headerCells.size} headers`}
            {selections.identifierCells.size > 0 && ` • ${selections.identifierCells.size} identifiers`}
            {selections.dataRegion && ' • Data region selected'}
          </span>
        </div>
        <button
          onClick={() => onStartParsing(selections)}
          disabled={selections.headerCells.size === 0}
          className="px-6 py-2 rounded-md bg-[var(--sentry-blue)] text-white hover:bg-[var(--sentry-blue)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
        >
          Confirm & Parse
        </button>
      </div>

      {/* Status Bar */}
      <StatusBar
        historyManager={historyManager}
        totalRows={sheetData.length}
        totalCols={sheetData[0]?.length || 0}
        selectedCellsCount={selectedCell ? 1 : 0}
        selectedCellsData={selectedCell ? [sheetData[selectedCell.row]?.[selectedCell.col]?.value] : []}
      />

      {/* Data Prep Modals */}
      <FindReplaceModal
        isOpen={showFindReplace}
        onClose={() => setShowFindReplace(false)}
        sheetData={sheetData}
        onApply={handleApplyFindReplace}
      />

      <RemoveDuplicatesModal
        isOpen={showRemoveDuplicates}
        onClose={() => setShowRemoveDuplicates(false)}
        sheetData={sheetData}
        onApply={handleApplyRemoveDuplicates}
      />

      {/* Context Menu */}
      {contextMenu && selectedCell && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
          selectedCell={selectedCell}
          onInsertRowAbove={handleInsertRowAbove}
          onInsertRowBelow={handleInsertRowBelow}
          onInsertColumnLeft={handleInsertColumnLeft}
          onInsertColumnRight={handleInsertColumnRight}
          onDeleteRow={handleContextDeleteRow}
          onDeleteColumn={handleContextDeleteColumn}
          onClearContents={handleClearContents}
          onDuplicateRow={handleDuplicateRow}
          onCopy={handleCopy}
          onCut={handleCut}
          onPaste={handlePaste}
        />
      )}

      {/* Column Filter Menu */}
      {columnFilter && (
        <ColumnFilterMenu
          columnIndex={columnFilter.columnIndex}
          columnData={sheetData.map(row => row[columnFilter.columnIndex])}
          onClose={() => setColumnFilter(null)}
          onSort={(direction) => handleColumnSort(columnFilter.columnIndex, direction)}
          onFilter={(selectedValues) => handleColumnFilter(columnFilter.columnIndex, selectedValues)}
          position={{ x: columnFilter.x, y: columnFilter.y }}
        />
      )}
      </div>
    </div>
  );
}
