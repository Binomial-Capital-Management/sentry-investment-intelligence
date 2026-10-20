/**
 * Lightweight markdown renderer for agent messages.
 * Handles: **bold**, *italic*, `code`, headers, lists, line breaks.
 * No external dependencies — keeps the add-in bundle small.
 */

import React from "react";

interface SimpleMarkdownProps {
  content: string;
  style?: React.CSSProperties;
}

/** Parse inline formatting: **bold**, *italic*, `code` */
function parseInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      nodes.push(<strong key={match.index} style={{ fontWeight: 600 }}>{match[2]}</strong>);
    } else if (match[3]) {
      nodes.push(<em key={match.index}>{match[3]}</em>);
    } else if (match[4]) {
      nodes.push(
        <code key={match.index} style={{
          background: "#f3f4f6", padding: "1px 4px", borderRadius: "3px",
          fontSize: "0.9em", fontFamily: "monospace",
        }}>
          {match[4]}
        </code>
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : [text];
}

/** Render a single line as a block element */
function renderLine(line: string, idx: number): React.ReactNode {
  const trimmed = line.trimStart();

  if (trimmed.startsWith("### ")) {
    return (
      <div key={idx} style={{ fontWeight: 600, fontSize: "13px", color: "#111827", margin: "8px 0 4px" }}>
        {parseInline(trimmed.slice(4))}
      </div>
    );
  }
  if (trimmed.startsWith("## ")) {
    return (
      <div key={idx} style={{ fontWeight: 700, fontSize: "14px", color: "#111827", margin: "10px 0 4px" }}>
        {parseInline(trimmed.slice(3))}
      </div>
    );
  }
  if (trimmed.startsWith("# ")) {
    return (
      <div key={idx} style={{ fontWeight: 700, fontSize: "15px", color: "#111827", margin: "12px 0 6px" }}>
        {parseInline(trimmed.slice(2))}
      </div>
    );
  }

  if (/^[-•]\s/.test(trimmed)) {
    return (
      <div key={idx} style={{ display: "flex", gap: "6px", margin: "2px 0", paddingLeft: "4px" }}>
        <span style={{ color: "#6b7280", flexShrink: 0 }}>•</span>
        <span>{parseInline(trimmed.slice(2))}</span>
      </div>
    );
  }

  const numMatch = trimmed.match(/^(\d+)[.)]\s/);
  if (numMatch) {
    return (
      <div key={idx} style={{ display: "flex", gap: "6px", margin: "2px 0", paddingLeft: "4px" }}>
        <span style={{ color: "#6b7280", flexShrink: 0, minWidth: "16px", textAlign: "right" }}>{numMatch[1]}.</span>
        <span>{parseInline(trimmed.slice(numMatch[0].length))}</span>
      </div>
    );
  }

  if (/^---+$/.test(trimmed) || /^\*\*\*+$/.test(trimmed)) {
    return <hr key={idx} style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "8px 0" }} />;
  }

  if (!trimmed) {
    return <div key={idx} style={{ height: "6px" }} />;
  }

  return (
    <div key={idx} style={{ margin: "2px 0" }}>
      {parseInline(line)}
    </div>
  );
}

export const SimpleMarkdown: React.FC<SimpleMarkdownProps> = ({ content, style }) => {
  if (!content) return null;

  const lines = content.split("\n");

  return (
    <div style={{
      fontSize: "14px", color: "#1f2937", lineHeight: "1.625",
      wordBreak: "break-word",
      ...style,
    }}>
      {lines.map((line, i) => renderLine(line, i))}
    </div>
  );
};
