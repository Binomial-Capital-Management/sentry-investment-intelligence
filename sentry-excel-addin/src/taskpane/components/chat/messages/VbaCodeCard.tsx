import React, { useState, useCallback } from "react";
import { AgentMessage } from "../../../../shared/types";
import { highlightVba } from "../../../utils/vba-highlight";
import { Copy, Check } from "../shared";

interface VbaCodeCardProps {
  msg: AgentMessage;
  index: number;
}

export const VbaCodeCard: React.FC<VbaCodeCardProps> = ({ msg, index }) => {
  const [copyFeedback, setCopyFeedback] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const vba = msg.vbaCode;
  if (!vba) return null;

  const handleCopy = useCallback(async () => {
    try { await navigator.clipboard.writeText(vba.code); } catch { /* fallback */ }
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  }, [vba.code]);

  return (
    <div style={{ marginBottom: "12px" }}>
      {/* AI badge */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
        <div style={{
          width: "20px", height: "20px", borderRadius: "50%", background: "#dbeafe",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <span style={{ fontSize: "10px", fontWeight: 700, color: "#2563eb" }}>AI</span>
        </div>
        <span style={{ fontSize: "12px", fontWeight: 500, color: "#6b7280" }}>Assistant</span>
      </div>

      <div style={{ paddingLeft: "28px" }}>
        {/* Purpose text */}
        <div style={{ fontSize: "13px", color: "#374151", lineHeight: "1.5", marginBottom: "8px" }}>
          {vba.purpose}
        </div>

        {/* Code card */}
        <div style={{
          background: "#eff6ff", border: "1px solid #bfdbfe",
          borderRadius: "8px", overflow: "hidden", marginBottom: "8px",
        }}>
          {/* Header bar */}
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "6px 12px", borderBottom: "1px solid #bfdbfe", background: "#dbeafe",
          }}>
            <span style={{ fontSize: "11px", fontWeight: 600, color: "#1e40af" }}>{vba.title}</span>
            <button
              onClick={handleCopy}
              style={{
                display: "flex", alignItems: "center", gap: "4px",
                padding: "2px 8px", borderRadius: "4px",
                background: copyFeedback ? "#059669" : "#3b82f6",
                color: "#fff", border: "none", fontSize: "10px", fontWeight: 500,
                cursor: "pointer", transition: "background 0.2s",
              }}
            >
              {copyFeedback ? <><Check /> Copied</> : <><Copy /> Copy</>}
            </button>
          </div>

          {/* Syntax-colored code */}
          <pre style={{
            margin: 0, padding: "10px 12px",
            fontFamily: "'Cascadia Code', 'Fira Code', Consolas, monospace",
            fontSize: "11px", lineHeight: "1.55", color: "#1e293b",
            whiteSpace: "pre", overflowX: "auto", maxHeight: "320px", overflowY: "auto",
          }} dangerouslySetInnerHTML={{ __html: highlightVba(vba.code) }} />
        </div>

        {/* Instructions (collapsible) */}
        <button
          onClick={() => setExpanded((p) => !p)}
          style={{
            display: "flex", alignItems: "center", gap: "5px", width: "100%",
            padding: "4px 0", background: "transparent", border: "none",
            fontSize: "11px", fontWeight: 500, color: "#6b7280", cursor: "pointer",
            textAlign: "left",
          }}
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
            style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.15s" }}>
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          How to use this macro
        </button>
        {expanded && (
          <div style={{
            fontSize: "12px", color: "#4b5563", lineHeight: "1.6",
            padding: "6px 0 2px 15px", whiteSpace: "pre-wrap",
          }}>
            {vba.instructions}
          </div>
        )}
      </div>
    </div>
  );
};
