import React, { useState, useRef, useEffect } from "react";
import { EditApprovalMode } from "../../../../shared/types";
import { Tooltip } from "../../Tooltip";
import { HandIcon, FastForwardIcon, CheckmarkIcon } from "../shared";

const editModeLabels: Record<EditApprovalMode, string> = {
  ask: "Ask before edits",
  accept: "Accept all edits",
};

interface EditModeMenuProps {
  editApprovalMode: EditApprovalMode;
  onEditApprovalModeChange?: (mode: EditApprovalMode) => void;
}

export const EditModeMenu: React.FC<EditModeMenuProps> = ({ editApprovalMode, onEditApprovalModeChange }) => {
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

  const editModeIcons: Record<EditApprovalMode, React.ReactNode> = {
    ask: <HandIcon />,
    accept: <FastForwardIcon />,
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <Tooltip label={editModeLabels[editApprovalMode]} side="top">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="btn btn-ghost"
          style={{
            width: "32px", height: "32px", borderRadius: "6px",
            background: isOpen ? "hsl(var(--bg-300))" : undefined,
            color: "hsl(var(--text-300))",
          }}
          aria-label={editModeLabels[editApprovalMode]}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "16px", height: "16px" }}>
            {editModeIcons[editApprovalMode]}
          </div>
        </button>
      </Tooltip>

      {isOpen && (
        <div style={{
          position: "absolute", zIndex: 50, bottom: "100%", left: 0, marginBottom: "8px",
          background: "hsl(var(--bg-000))", border: "0.5px solid hsl(var(--border-300) / 15%)",
          borderRadius: "12px", boxShadow: "0 4px 12px 0 rgba(0,0,0,0.08)", padding: "6px", width: "240px",
        }}>
          {(["ask", "accept"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { onEditApprovalModeChange?.(m); setIsOpen(false); }}
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
                  color: "hsl(var(--text-300))", marginTop: "2px", flexShrink: 0, overflow: "visible",
                  width: m === "ask" ? "12px" : "16px", height: m === "ask" ? "12px" : "16px",
                }}>
                  {editModeIcons[m]}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="font-base" style={{ color: "hsl(var(--text-200))" }}>{editModeLabels[m]}</div>
                </div>
                {editApprovalMode === m && <CheckmarkIcon />}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
