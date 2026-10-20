import React from 'react';

interface ReasoningPanelProps {
  content?: string;
  isStreaming?: boolean;
}

export function ReasoningPanel({ content, isStreaming }: ReasoningPanelProps) {
  const hasContent = typeof content === 'string' && content.trim().length > 0;
  if (!hasContent && !isStreaming) {
    return null;
  }

  console.log('[ReasoningPanel] Render', { hasContent, isStreaming, content });

  console.log('[ReasoningPanel component] creating panel', { hasContent, isStreaming });
  return (
    <details
      open={isStreaming}
      aria-label="Model reasoning trace"
      className="reasoning-panel rounded-md border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700"
    >
      <style>{`
        .reasoning-panel summary {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-weight: 600;
          color: #1f2937;
        }
        .reasoning-panel summary::-webkit-details-marker {
          display: none;
        }
        .reasoning-panel .pulse-dot {
          width: 8px;
          height: 8px;
          border-radius: 999px;
          background: #3b82f6;
          display: inline-flex;
          animation: pulse 1.2s ease-in-out infinite;
        }
        .reasoning-panel .checkmark {
          color: #047857;
          font-weight: 700;
        }
        .reasoning-panel pre {
          margin-top: 10px;
          padding: 10px;
          background: rgba(15, 23, 42, 0.04);
          border-radius: 8px;
          font-size: 12px;
          white-space: pre-wrap;
          word-break: break-word;
          color: #0f172a;
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.45; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
      <summary>
        {isStreaming ? (
          <>
            <span className="pulse-dot" />
            <span>Model reasoning…</span>
          </>
        ) : (
          <>
            <span className="checkmark">✓</span>
            <span>Reasoning concluded</span>
          </>
        )}
      </summary>
      {hasContent && (
        <pre>{content}</pre>
      )}
    </details>
  );
}
