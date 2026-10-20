import React, { useState, useRef, useEffect } from "react";
import { InteractionMode } from "../../../../shared/types";
import { Tooltip } from "../../Tooltip";
import { CheckmarkIcon } from "../shared";

const modeIcons: Record<InteractionMode, React.ReactNode> = {
  agent: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><path d="M18.178 8c5.096 0 5.096 8 0 8-5.095 0-7.133-8-12.739-8-4.585 0-4.585 8 0 8 5.606 0 7.644-8 12.74-8z"/></svg>,
  plan: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><circle cx="7.5" cy="7.5" r="1.5"/><circle cx="16.5" cy="7.5" r="1.5"/><circle cx="7.5" cy="16.5" r="1.5"/><circle cx="16.5" cy="16.5" r="1.5"/><line x1="9" y1="7.5" x2="15" y2="7.5"/><line x1="9" y1="16.5" x2="15" y2="16.5"/></svg>,
  ask: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
};

const modeLabels: Record<InteractionMode, string> = {
  agent: "Agent",
  plan: "Plan",
  ask: "Ask",
};

interface ModeMenuProps {
  mode: InteractionMode;
  onModeChange: (mode: InteractionMode) => void;
}

export const ModeMenu: React.FC<ModeMenuProps> = ({ mode, onModeChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <Tooltip label={modeLabels[mode]} side="top">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="btn btn-ghost"
          style={{
            width: "32px", height: "32px", borderRadius: "6px",
            background: isOpen ? "hsl(var(--bg-300))" : undefined,
            color: "hsl(var(--text-300))",
          }}
          aria-label={`Mode: ${modeLabels[mode]}`}
        >
          {modeIcons[mode]}
        </button>
      </Tooltip>

      {isOpen && (
        <div style={{
          position: "absolute", zIndex: 50, bottom: "100%", left: 0, marginBottom: "8px",
          background: "hsl(var(--bg-000))", border: "0.5px solid hsl(var(--border-300) / 15%)",
          borderRadius: "12px", boxShadow: "0 4px 12px 0 rgba(0,0,0,0.08)", padding: "6px", width: "200px",
        }}>
          {(["agent", "plan", "ask"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { onModeChange(m); setIsOpen(false); }}
              style={{
                width: "100%", padding: "8px", textAlign: "left", borderRadius: "8px",
                transition: "background-color 150ms", background: "transparent", border: "none", cursor: "pointer",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--bg-200))"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "hsl(var(--text-300))", marginTop: "2px", flexShrink: 0,
                  width: "16px", height: "16px", overflow: "visible",
                }}>
                  {modeIcons[m]}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="font-base" style={{ color: "hsl(var(--text-200))" }}>{modeLabels[m]}</div>
                </div>
                {mode === m && <CheckmarkIcon />}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
