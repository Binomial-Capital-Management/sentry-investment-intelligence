import { useRef, useState, useCallback, cloneElement, isValidElement, type ReactNode, type ReactElement, type FC } from 'react';
import { createPortal } from 'react-dom';

interface TooltipProps {
  children: ReactElement;
  label: string;
  side?: 'top' | 'bottom';
}

export const Tooltip: FC<TooltipProps> = ({ children, label, side = 'bottom' }) => {
  const childRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const [isVisible, setIsVisible] = useState(false);

  const updatePosition = useCallback(() => {
    if (!childRef.current || !tooltipRef.current) return;
    const rect = childRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const gap = 6;

    const top = side === 'top'
      ? rect.top - tooltipRect.height - gap
      : rect.bottom + gap;
    const left = rect.left + rect.width / 2 - tooltipRect.width / 2;
    setPos({ top, left });
  }, [side]);

  const handleMouseEnter = useCallback(() => {
    setIsVisible(true);
    updatePosition();
  }, [updatePosition]);

  const handleMouseLeave = useCallback(() => {
    setIsVisible(false);
  }, []);

  if (!isValidElement(children)) return children;

  const child = cloneElement(children as ReactElement<any>, {
    ref: childRef,
    onMouseEnter: (e: React.MouseEvent) => {
      handleMouseEnter();
      (children.props as any).onMouseEnter?.(e);
    },
    onMouseLeave: (e: React.MouseEvent) => {
      handleMouseLeave();
      (children.props as any).onMouseLeave?.(e);
    },
  });

  return (
    <>
      {child}
      {createPortal(
        <span
          ref={tooltipRef}
          className="fixed px-2 py-1 text-xs font-normal whitespace-nowrap text-white bg-black/80 rounded-md shadow-md backdrop-blur-sm pointer-events-none z-[99999] transition-opacity duration-150"
          style={{
            top: pos.top,
            left: pos.left,
            opacity: isVisible ? 1 : 0,
            visibility: isVisible ? 'visible' : 'hidden',
          }}
        >
          {label}
        </span>,
        document.body
      )}
    </>
  );
};
