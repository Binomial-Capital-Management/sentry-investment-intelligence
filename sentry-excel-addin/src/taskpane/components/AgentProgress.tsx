/**
 * AgentProgress — Shows step-by-step execution progress.
 */

import React from "react";
import { AgentPlan, AgentStatus } from "../../shared/types";

interface AgentProgressProps {
  plan: AgentPlan | null;
  currentStep: number;
  status: AgentStatus;
}

export const AgentProgress: React.FC<AgentProgressProps> = ({
  plan,
  currentStep,
  status,
}) => {
  if (!plan || status === "idle" || status === "planning") return null;

  const isExecuting = status === "executing" || status === "writing_excel" || status === "validating";

  return (
    <div style={styles.container}>
      {plan.steps.map((step, i) => {
        let icon = "○";
        let color = "#999";

        if (i < currentStep) {
          icon = "✓";
          color = "#107C10";
        } else if (i === currentStep && isExecuting) {
          icon = "▶";
          color = "#0078D4";
        }

        return (
          <div key={i} style={{ ...styles.step, color }}>
            <span style={styles.icon}>{icon}</span>
            <span>Step {step.step_number}: {step.description}</span>
          </div>
        );
      })}

      {status === "re_indexing" && (
        <div style={{ ...styles.step, color: "#8764B8" }}>
          <span style={styles.icon}>↻</span>
          <span>Updating workbook index...</span>
        </div>
      )}

      {status === "done" && (
        <div style={{ ...styles.step, color: "#107C10" }}>
          <span style={styles.icon}>✓</span>
          <span>Complete</span>
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    padding: "8px",
    borderTop: "1px solid #E1E1E1",
    fontSize: "12px",
  },
  step: {
    display: "flex",
    alignItems: "center",
    padding: "3px 0",
    gap: "6px",
  },
  icon: {
    width: "16px",
    textAlign: "center" as const,
    fontWeight: 600,
  },
};
