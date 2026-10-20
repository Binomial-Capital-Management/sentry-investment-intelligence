/**
 * ThinkingSection - Collapsible component for agent reasoning
 * 
 * Shows a bold title as clickable header with expandable detailed reasoning content.
 * Default state is collapsed.
 * 
 * Wrapped in React.memo to prevent unnecessary re-renders during rapid thinking updates.
 */

import React, { memo } from "react";
import { ThinkingSection as ThinkingSectionType } from "../../../../shared/types";

/* ── Icons ── */

const ChevronRight = ({ rotated }: { rotated: boolean }) => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{
      transform: rotated ? "rotate(90deg)" : "rotate(0deg)",
      transition: "transform 0.2s ease",
      flexShrink: 0,
      opacity: 0.6,
    }}
  >
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const ThinkingIcon = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#8b5cf6"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ flexShrink: 0 }}
  >
    <circle cx="12" cy="12" r="3" />
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
  </svg>
);

/* ── Component ── */

interface ThinkingSectionProps {
  section: ThinkingSectionType;
  onToggle: () => void;
}

export const ThinkingSection = memo(function ThinkingSection({
  section,
  onToggle,
}: ThinkingSectionProps) {
  const isExpanded = !section.collapsed;

  return (
    <div className="collapsible-section">
      {/* Header */}
      <button
        className="collapsible-header"
        onClick={onToggle}
      >
        <span className={`collapsible-chevron ${isExpanded ? "expanded" : ""}`}>
          <ChevronRight rotated={isExpanded} />
        </span>
        <ThinkingIcon />
        <span className="collapsible-title truncate">
          {section.title}
        </span>
      </button>

      {/* Expanded Content */}
      {isExpanded && section.content && (
        <div className="collapsible-content">
          {section.content}
        </div>
      )}
    </div>
  );
});

export default ThinkingSection;
