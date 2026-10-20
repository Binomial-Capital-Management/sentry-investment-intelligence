import React from "react";
import { AgentMessage } from "../../../../shared/types";
import { PulseLoader, PlayIcon, UndoIcon, XIcon } from "../shared";

interface PlanCardProps {
  msg: AgentMessage;
  index: number;
  onBuildPlan?: (messageIndex: number) => void;
  onUndoPlan?: (messageIndex: number) => void;
  onRejectPlan?: (messageIndex: number) => void;
}

export const PlanCard: React.FC<PlanCardProps> = ({ msg, index, onBuildPlan, onUndoPlan, onRejectPlan }) => {
  if (!msg.plan) return null;

  return (
    <div style={{ marginBottom: "12px", paddingLeft: "28px" }}>
      <div style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: "10px",
        padding: "14px 16px",
        boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
      }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
          <div style={{
            width: "18px", height: "18px", borderRadius: "4px", background: "#374151",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#374151" }}>
            Execution Plan
          </span>
          {msg.planStatus === "building" && (
            <span style={{ fontSize: "10px", color: "#2563eb", fontWeight: 500, marginLeft: "auto" }}>Executing...</span>
          )}
          {msg.planStatus === "built" && (
            <span style={{ fontSize: "10px", color: "#059669", fontWeight: 500, marginLeft: "auto" }}>Complete</span>
          )}
          {msg.planStatus === "undone" && (
            <span style={{ fontSize: "10px", color: "#d97706", fontWeight: 500, marginLeft: "auto" }}>Undone</span>
          )}
          {msg.planStatus === "rejected" && (
            <span style={{ fontSize: "10px", color: "#dc2626", fontWeight: 500, marginLeft: "auto" }}>Rejected</span>
          )}
        </div>

        {/* Summary */}
        <div style={{ fontSize: "13px", color: "#374151", lineHeight: "1.5", marginBottom: "10px" }}>
          {msg.content}
        </div>

        {/* Steps preview */}
        <div style={{ marginBottom: "12px" }}>
          {msg.plan.steps.slice(0, 6).map((step, si) => (
            <div key={si} style={{
              display: "flex", alignItems: "flex-start", gap: "8px",
              padding: "4px 0", fontSize: "11px", color: "#4b5563",
            }}>
              <span style={{
                width: "16px", height: "16px", borderRadius: "50%",
                background: "#e5e7eb", color: "#374151",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "9px", fontWeight: 700, flexShrink: 0, marginTop: "1px",
              }}>{si + 1}</span>
              <span style={{ flex: 1 }}>
                <strong style={{ color: "#374151" }}>{step.sheet}</strong>
                {step.target_range ? ` [${step.target_range}]` : ""} — {step.description}
              </span>
            </div>
          ))}
          {msg.plan.steps.length > 6 && (
            <div style={{ fontSize: "10px", color: "#6b7280", paddingLeft: "24px", marginTop: "4px" }}>
              +{msg.plan.steps.length - 6} more steps
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {msg.planStatus === "pending" && (
            <>
              <button
                onClick={() => onBuildPlan?.(index)}
                style={{
                  display: "flex", alignItems: "center", gap: "5px",
                  padding: "6px 14px", borderRadius: "6px",
                  background: "#111827", color: "#fff", border: "none",
                  fontSize: "11px", fontWeight: 600, cursor: "pointer",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#1f2937"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "#111827"; }}
              >
                <PlayIcon /> Build
              </button>
              <button
                onClick={() => onRejectPlan?.(index)}
                style={{
                  display: "flex", alignItems: "center", gap: "5px",
                  padding: "6px 14px", borderRadius: "6px",
                  background: "transparent", color: "#6b7280", border: "1px solid #d1d5db",
                  fontSize: "11px", fontWeight: 500, cursor: "pointer",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#f9fafb"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                <XIcon /> Reject
              </button>
            </>
          )}
          {msg.planStatus === "building" && (
            <PulseLoader label="Executing..." />
          )}
          {msg.planStatus === "built" && (
            <button
              onClick={() => onUndoPlan?.(index)}
              style={{
                display: "flex", alignItems: "center", gap: "5px",
                padding: "6px 14px", borderRadius: "6px",
                background: "transparent", color: "#d97706", border: "1px solid #fbbf24",
                fontSize: "11px", fontWeight: 500, cursor: "pointer",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#fffbeb"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <UndoIcon /> Undo
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
