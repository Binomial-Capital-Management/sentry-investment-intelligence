import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

// Claude theme CSS
import "./styles/claude-theme.css";
import "./styles/claude-components.css";

/* global Office */

const render = () => {
  const container = document.getElementById("root");
  if (container) {
    const root = createRoot(container);
    root.render(<App />);
  }
};

try {
  Office.onReady(() => {
    render();
  });
} catch (e) {
  // Office.js not yet loaded — fallback for dev/browser testing
  console.warn("Office.onReady failed, rendering directly:", e);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
}
