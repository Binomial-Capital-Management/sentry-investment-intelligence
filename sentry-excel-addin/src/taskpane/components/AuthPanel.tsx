/**
 * AuthPanel — API key entry for MVP auth.
 */

import React, { useState } from "react";
import { getApiKey, setApiKey } from "../../shared/auth";

interface AuthPanelProps {
  onAuthenticated: () => void;
}

export const AuthPanel: React.FC<AuthPanelProps> = ({ onAuthenticated }) => {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) {
      setError("API key required");
      return;
    }
    setApiKey(trimmed);
    onAuthenticated();
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Sentry</h2>
      <p style={styles.subtitle}>Enter your API key to get started.</p>

      <form onSubmit={handleSubmit} style={styles.form}>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="sk-..."
          style={styles.input}
        />
        {error && <p style={styles.error}>{error}</p>}
        <button type="submit" style={styles.button}>
          Connect
        </button>
      </form>
    </div>
  );
};

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    padding: "24px",
  },
  title: {
    fontSize: "20px",
    margin: "0 0 4px",
    color: "#0078D4",
  },
  subtitle: {
    fontSize: "13px",
    color: "#666",
    margin: "0 0 20px",
  },
  form: {
    width: "100%",
    display: "flex",
    flexDirection: "column" as const,
    gap: "8px",
  },
  input: {
    padding: "10px",
    border: "1px solid #CCC",
    borderRadius: "4px",
    fontSize: "13px",
  },
  button: {
    padding: "10px",
    background: "#0078D4",
    color: "#FFF",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
  },
  error: {
    color: "#A4262C",
    fontSize: "12px",
    margin: 0,
  },
};
