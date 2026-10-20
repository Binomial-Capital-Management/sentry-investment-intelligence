import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';

interface UsePanelResizeOptions {
  panelRef: RefObject<HTMLDivElement | null>;
  initialWidth?: number;
  minWidth?: number;
  onResize?: (width: number) => void;
}

interface UsePanelResizeReturn {
  panelWidth: number;
  isResizing: boolean;
  startResize: (e: React.MouseEvent) => void;
}

export function usePanelResize({
  panelRef,
  initialWidth = 480,
  minWidth = 300,
  onResize,
}: UsePanelResizeOptions): UsePanelResizeReturn {
  const [panelWidth, setPanelWidth] = useState(initialWidth);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<{ startX: number; startWidth: number; maxAvailable: number } | null>(null);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const panel = panelRef.current;
    const container = panel?.parentElement;
    if (!container || !panel) return;

    // Measure the flex container's content area (excluding padding)
    const containerStyle = getComputedStyle(container);
    const contentWidth = container.clientWidth
      - parseFloat(containerStyle.paddingLeft)
      - parseFloat(containerStyle.paddingRight);
    const gap = parseFloat(containerStyle.gap) || 0;

    // Sum up sibling widths; flex-grow siblings can shrink to ~0 (min-w-0)
    const children = Array.from(container.children) as HTMLElement[];
    let siblingsFixedWidth = 0;
    let hasFlexGrowSibling = false;
    for (const child of children) {
      if (child === panel) continue;
      const childStyle = getComputedStyle(child);
      if (parseFloat(childStyle.flexGrow) > 0) {
        hasFlexGrowSibling = true;
      } else {
        siblingsFixedWidth += child.offsetWidth;
      }
    }

    const totalGaps = gap * Math.max(0, children.length - 1);
    // Reserve a minimum sliver for flex-grow siblings (e.g. the data table)
    const minFlexSpace = hasFlexGrowSibling ? 48 : 0;
    const maxAvailable = contentWidth - siblingsFixedWidth - totalGaps - minFlexSpace;

    setIsResizing(true);
    resizeRef.current = { startX: e.clientX, startWidth: panelWidth, maxAvailable };
    // Signal to hide charts during resize
    document.documentElement.dataset.resizing = 'true';
  }, [panelWidth, panelRef]);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeRef.current) return;
      // Panel is on the right, handle is on the left edge — dragging left = wider
      const delta = resizeRef.current.startX - e.clientX;
      const newWidth = Math.max(minWidth, Math.min(resizeRef.current.maxAvailable, resizeRef.current.startWidth + delta));
      setPanelWidth(newWidth);
      if (onResize) {
        onResize(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      resizeRef.current = null;
      // Signal resize complete - show charts again
      delete document.documentElement.dataset.resizing;
      // Trigger Plotly resize
      requestAnimationFrame(() => {
        window.dispatchEvent(new Event('resize'));
      });
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, minWidth, onResize]);

  return {
    panelWidth,
    isResizing,
    startResize,
  };
}
