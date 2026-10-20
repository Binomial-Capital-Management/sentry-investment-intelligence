/**
 * IndexStatus — Shows workbook indexing state.
 */

import React from "react";
import { AgentStatus } from "../../shared/types";

interface IndexStatusProps {
  status: AgentStatus;
  workbookId: string | null;
}

export const IndexStatus: React.FC<IndexStatusProps> = ({ status, workbookId }) => {
  let label = "Not indexed";
  let color = "#999";

  if (status === "indexing" || status === "re_indexing") {
    label = "Indexing...";
    color = "#8764B8";
  } else if (workbookId) {
    label = "Indexed";
    color = "#107C10";
  }

  return (
    <div style={styles.container}>
      <span style={{ ...styles.dot, background: color }} />
      <span style={{ ...styles.label, color }}>{label}</span>
    </div>
  );
};

const styles = {
  container: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "4px 8px",
    fontSize: "11px",
  },
  dot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    display: "inline-block",
  },
  label: {
    fontWeight: 500,
  },
};
