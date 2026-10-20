/**
 * PlanPreview — Shows the agent's plan before execution.
 * User can approve or reject.
 */

import React from "react";
import { AgentPlan } from "../../shared/types";

interface PlanPreviewProps {
  plan: AgentPlan;
  onApprove: () => void;
  visible: boolean;
}

export const PlanPreview: React.FC<PlanPreviewProps> = ({ plan, onApprove, visible }) => {
  if (!visible || !plan) return null;

  return (
    <div style={styles.overlay}>
      <div style={styles.card}>
        <h3 style={styles.title}>Agent Plan</h3>
        <p style={styles.summary}>{plan.summary}</p>

        <div style={styles.stepList}>
          {plan.steps.map((step, i) => (
            <div key={i} style={styles.step}>
              <strong>Step {step.step_number}:</strong> {step.description}
              <span style={styles.sheet}> [{step.sheet}]</span>
              <span style={styles.ops}> ({step.operations.length} operations)</span>
            </div>
          ))}
        </div>

        {plan.data_requests.length > 0 && (
          <div style={styles.dataReqs}>
            <em>Agent needs to read {plan.data_requests.length} additional range(s) first.</em>
          </div>
        )}

        <div style={styles.actions}>
          <button onClick={onApprove} style={styles.approveBtn}>
            Approve & Execute
          </button>
        </div>
      </div>
    </div>
  );
};

const styles = {
  overlay: {
    position: "absolute" as const,
    inset: 0,
    background: "rgba(0,0,0,0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "12px",
    zIndex: 10,
  },
  card: {
    background: "#FFF",
    borderRadius: "8px",
    padding: "16px",
    maxHeight: "80%",
    overflowY: "auto" as const,
    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
    width: "100%",
  },
  title: {
    margin: "0 0 8px",
    fontSize: "15px",
  },
  summary: {
    margin: "0 0 12px",
    fontSize: "13px",
    color: "#333",
  },
  stepList: {
    marginBottom: "12px",
  },
  step: {
    padding: "6px 0",
    fontSize: "12px",
    borderBottom: "1px solid #F0F0F0",
  },
  sheet: {
    color: "#0078D4",
    fontSize: "11px",
  },
  ops: {
    color: "#888",
    fontSize: "11px",
  },
  dataReqs: {
    fontSize: "12px",
    color: "#A4262C",
    marginBottom: "12px",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
  },
  approveBtn: {
    padding: "8px 20px",
    background: "#107C10",
    color: "#FFF",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "13px",
  },
};
