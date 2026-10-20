import React, { useRef, useState, useCallback } from "react";

interface TooltipProps {
  children: React.ReactNode;
  label: string;
  side?: "top" | "bottom";
}

export const Tooltip: React.FC<TooltipProps> = ({ children, label, side = "top" }) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const [isVisible, setIsVisible] = useState(false);

  const updatePosition = useCallback(() => {
    if (!wrapperRef.current || !tooltipRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const gap = 6;
    
    let top: number;
    if (side === "top") {
      top = rect.top - tooltipRect.height - gap;
    } else {
      top = rect.bottom + gap;
    }
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

  return (
    <div 
      className="claude-tooltip-wrapper" 
      ref={wrapperRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
    >
      {children}
      <span 
        className="claude-tooltip" 
        ref={tooltipRef}
        style={{ 
          top: pos.top, 
          left: pos.left,
          opacity: isVisible ? 1 : 0,
          visibility: isVisible ? 'visible' : 'hidden',
        }}
      >
        {label}
      </span>
    </div>
  );
};
