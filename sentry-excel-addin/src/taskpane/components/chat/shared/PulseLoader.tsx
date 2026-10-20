import React, { useState, useEffect, useRef } from "react";

const LOADER_TEXTS = [
  "Thinking...",
  "Gathering data...",
  "Analyzing...",
  "Processing...",
  "Preparing response...",
  "Synthesizing...",
];

export const PulseLoader: React.FC<{ label?: string }> = ({ label }) => {
  const [textIdx, setTextIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTextIdx((i) => (i + 1) % LOADER_TEXTS.length), 2500);
    return () => clearInterval(id);
  }, []);

  // Dev-only elapsed timer: tracks seconds since label last changed
  const labelChangedAt = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    labelChangedAt.current = Date.now();
    setElapsed(0);
  }, [label]);

  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - labelChangedAt.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [label]);

  const displayText = label || LOADER_TEXTS[textIdx];
  return (
    <div className="thinking-indicator">
      <img
        className="pulse-icon thinking-icon"
        src={require("../../../../assets/binomial-icon-logo.png")}
        alt="Sentry"
        style={{ width: "24px", height: "24px", objectFit: "contain" }}
      />
      <span className="thinking-text">
        {displayText}
        {process.env.NODE_ENV === "development" && label && elapsed > 0 && (
          <span className="thinking-elapsed"> {elapsed}s</span>
        )}
      </span>
    </div>
  );
};
