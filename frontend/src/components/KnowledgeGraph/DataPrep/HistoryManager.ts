/**
 * HistoryManager - Undo/Redo stack for Excel-like operations
 * Microsoft Excel pattern: snapshot-based undo with operation descriptions
 */

export interface CellData {
  value: string | number | null;
  merged?: boolean;
  mergeSpan?: { rows: number; cols: number };
  isMergedCopy?: boolean;
}

export interface Operation {
  type: 'trim' | 'find_replace' | 'remove_duplicates' | 'delete_row' | 'delete_column' | 'edit_cell' | 'custom' | 'insert_row' | 'insert_column' | 'duplicate_row' | 'clear' | 'cut' | 'paste' | 'sort' | 'filter';
  description: string;
  timestamp: number;
  beforeData: CellData[][];
  afterData: CellData[][];
}

export class HistoryManager {
  private undoStack: Operation[] = [];
  private redoStack: Operation[] = [];
  private maxHistory: number = 100;
  private currentData: CellData[][];
  private onDataChange: (data: CellData[][]) => void;

  constructor(initialData: CellData[][], onDataChange: (data: CellData[][]) => void) {
    this.currentData = initialData;
    this.onDataChange = onDataChange;
  }

  /**
   * Execute an operation and add it to history
   */
  execute(operation: Omit<Operation, 'beforeData' | 'afterData' | 'timestamp'>, newData: CellData[][]) {
    const op: Operation = {
      ...operation,
      beforeData: this.deepCopy(this.currentData),
      afterData: this.deepCopy(newData),
      timestamp: Date.now(),
    };

    this.undoStack.push(op);
    this.redoStack = []; // Clear redo stack on new operation

    // Limit history size
    if (this.undoStack.length > this.maxHistory) {
      this.undoStack.shift();
    }

    this.currentData = newData;
    this.onDataChange(newData);
  }

  /**
   * Undo last operation
   */
  undo(): boolean {
    if (this.undoStack.length === 0) return false;

    const op = this.undoStack.pop()!;
    this.redoStack.push(op);

    this.currentData = this.deepCopy(op.beforeData);
    this.onDataChange(this.currentData);

    return true;
  }

  /**
   * Redo last undone operation
   */
  redo(): boolean {
    if (this.redoStack.length === 0) return false;

    const op = this.redoStack.pop()!;
    this.undoStack.push(op);

    this.currentData = this.deepCopy(op.afterData);
    this.onDataChange(this.currentData);

    return true;
  }

  /**
   * Get undo stack for history display
   */
  getUndoStack(): Operation[] {
    return [...this.undoStack];
  }

  /**
   * Get redo stack
   */
  getRedoStack(): Operation[] {
    return [...this.redoStack];
  }

  /**
   * Check if undo is available
   */
  canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  /**
   * Check if redo is available
   */
  canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  /**
   * Get last operation description
   */
  getLastOperation(): string | null {
    if (this.undoStack.length === 0) return null;
    return this.undoStack[this.undoStack.length - 1].description;
  }

  /**
   * Clear all history
   */
  clear() {
    this.undoStack = [];
    this.redoStack = [];
  }

  /**
   * Deep copy data to prevent mutations
   */
  private deepCopy(data: CellData[][]): CellData[][] {
    return data.map(row =>
      row.map(cell => ({ ...cell })),
    );
  }

  /**
   * Update current data reference (for external changes)
   */
  updateCurrentData(data: CellData[][]) {
    this.currentData = data;
  }
}
