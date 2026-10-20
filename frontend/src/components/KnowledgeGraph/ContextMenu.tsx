/**
 * ContextMenu - Excel-style right-click context menu
 * Microsoft pattern: Context-sensitive actions based on selection
 */

import { useEffect, useRef } from 'react';
import { Plus, Trash2, Copy, Clipboard, Scissors } from 'lucide-react';

interface ContextMenuProps {
  x: number;
  y: number;
  onClose: () => void;
  selectedCell: { row: number; col: number } | null;
  onInsertRowAbove: () => void;
  onInsertRowBelow: () => void;
  onInsertColumnLeft: () => void;
  onInsertColumnRight: () => void;
  onDeleteRow: () => void;
  onDeleteColumn: () => void;
  onClearContents: () => void;
  onDuplicateRow: () => void;
  onCopy: () => void;
  onCut: () => void;
  onPaste: () => void;
}

export default function ContextMenu({
  x,
  y,
  onClose,
  selectedCell,
  onInsertRowAbove,
  onInsertRowBelow,
  onInsertColumnLeft,
  onInsertColumnRight,
  onDeleteRow,
  onDeleteColumn,
  onClearContents,
  onDuplicateRow,
  onCopy,
  onCut,
  onPaste,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  // Adjust position if menu goes off screen
  useEffect(() => {
    if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let adjustedX = x;
      let adjustedY = y;

      if (rect.right > viewportWidth) {
        adjustedX = viewportWidth - rect.width - 10;
      }

      if (rect.bottom > viewportHeight) {
        adjustedY = viewportHeight - rect.height - 10;
      }

      menuRef.current.style.left = `${adjustedX}px`;
      menuRef.current.style.top = `${adjustedY}px`;
    }
  }, [x, y]);

  const handleAction = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <div
      ref={menuRef}
      className="fixed bg-white border border-slate-300 rounded-lg shadow-2xl z-[200] py-1 min-w-[220px] animate-in fade-in zoom-in-95 duration-100"
      style={{ left: x, top: y }}
    >
      {/* Copy/Cut/Paste */}
      <div className="py-1">
        <button
          onClick={() => handleAction(onCut)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Scissors size={14} className="text-slate-600" />
          <span>Cut</span>
          <span className="ml-auto text-xs text-slate-500">Ctrl+X</span>
        </button>
        <button
          onClick={() => handleAction(onCopy)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Copy size={14} className="text-slate-600" />
          <span>Copy</span>
          <span className="ml-auto text-xs text-slate-500">Ctrl+C</span>
        </button>
        <button
          onClick={() => handleAction(onPaste)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Clipboard size={14} className="text-slate-600" />
          <span>Paste</span>
          <span className="ml-auto text-xs text-slate-500">Ctrl+V</span>
        </button>
      </div>

      <div className="border-t border-slate-200 my-1"></div>

      {/* Insert */}
      <div className="py-1">
        <div className="px-4 py-1 text-xs font-semibold text-slate-500 uppercase">Insert</div>
        <button
          onClick={() => handleAction(onInsertRowAbove)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Plus size={14} className="text-slate-600" />
          <span>Insert Row Above</span>
        </button>
        <button
          onClick={() => handleAction(onInsertRowBelow)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Plus size={14} className="text-slate-600" />
          <span>Insert Row Below</span>
        </button>
        <button
          onClick={() => handleAction(onInsertColumnLeft)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Plus size={14} className="text-slate-600" />
          <span>Insert Column Left</span>
        </button>
        <button
          onClick={() => handleAction(onInsertColumnRight)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-3"
        >
          <Plus size={14} className="text-slate-600" />
          <span>Insert Column Right</span>
        </button>
      </div>

      <div className="border-t border-slate-200 my-1"></div>

      {/* Delete */}
      <div className="py-1">
        <button
          onClick={() => handleAction(onDeleteRow)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-3"
        >
          <Trash2 size={14} />
          <span>Delete Row {selectedCell && selectedCell.row + 1}</span>
        </button>
        <button
          onClick={() => handleAction(onDeleteColumn)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-3"
        >
          <Trash2 size={14} />
          <span>Delete Column {selectedCell && String.fromCharCode(65 + selectedCell.col)}</span>
        </button>
      </div>

      <div className="border-t border-slate-200 my-1"></div>

      {/* Other */}
      <div className="py-1">
        <button
          onClick={() => handleAction(onClearContents)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100"
        >
          Clear Contents
        </button>
        <button
          onClick={() => handleAction(onDuplicateRow)}
          className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100"
        >
          Duplicate Row
        </button>
      </div>
    </div>
  );
}
