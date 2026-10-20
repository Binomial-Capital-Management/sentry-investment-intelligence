import React from 'react';
import type { ToolEvent } from '@/types';

interface ToolCallTimelineProps {
  events: ToolEvent[];
}

const STATUS_LABEL: Record<ToolEvent['status'], string> = {
  in_progress: 'In progress',
  completed: 'Completed',
  failed: 'Failed',
};

function formatTimestamp(ts: number | undefined) {
  if (!ts) return '';
  try {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
    }).format(new Date(ts));
  } catch {
    return '';
  }
}

function getIcon(toolType: ToolEvent['toolType']) {
  switch (toolType) {
    case 'code_interpreter':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7l-3 5 3 5M16 7l3 5-3 5M12 5v14" />
        </svg>
      );
    case 'mcp_call':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 9h16M4 15h16M9 4v16M15 4v16" />
        </svg>
      );
    case 'function_call':
    default:
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l-4 3 4 3M16 9l4 3-4 3" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16" />
        </svg>
      );
  }
}

const truncate = (text: string, length: number) => {
  if (!text) return '';
  return text.length > length ? `${text.slice(0, length)}…` : text;
};

export function ToolCallTimeline({ events }: ToolCallTimelineProps) {
  if (!events || events.length === 0) {
    return null;
  }

  console.log('[ToolCallTimeline] Rendering tool events:', events);

  return (
    <div className="tool-call-timeline rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-800">
      <style>{`
        .tool-call-timeline .tool-event {
          display: grid;
          grid-template-columns: auto 1fr auto;
          gap: 12px;
          padding: 10px 12px;
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.6);
          border-left: 3px solid transparent;
        }
        .tool-call-timeline .tool-icon {
          width: 28px;
          height: 28px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(37, 99, 235, 0.12);
          color: #1d4ed8;
        }
        .tool-call-timeline .tool-body {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .tool-call-timeline .tool-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .tool-call-timeline .tool-name {
          font-weight: 600;
          color: #1e3a8a;
        }
        .tool-call-timeline .tool-status {
          padding: 0 8px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 600;
        }
        .tool-call-timeline .tool-status.in_progress {
          background: rgba(37, 99, 235, 0.12);
          color: #1d4ed8;
        }
        .tool-call-timeline .tool-status.completed {
          background: rgba(16, 185, 129, 0.12);
          color: #047857;
        }
        .tool-call-timeline .tool-status.failed {
          background: rgba(239, 68, 68, 0.12);
          color: #b91c1c;
        }
        .tool-call-timeline .tool-args summary,
        .tool-call-timeline .tool-result summary {
          cursor: pointer;
          color: #1d4ed8;
          font-weight: 500;
        }
        .tool-call-timeline .tool-args pre,
        .tool-call-timeline .tool-result pre {
          margin-top: 6px;
          padding: 8px;
          background: rgba(15, 23, 42, 0.04);
          border-radius: 8px;
          font-size: 12px;
          white-space: pre-wrap;
          word-break: break-word;
          color: #0f172a;
        }
        .tool-call-timeline .tool-error {
          color: #b91c1c;
          font-weight: 500;
        }
        .tool-call-timeline .tool-meta {
          font-size: 11px;
          color: #1e3a8a;
          text-align: right;
        }
        .tool-call-timeline .tool-event-in_progress {
          border-left-color: #3b82f6;
          animation: timeline-shimmer 1.6s ease-in-out infinite;
        }
        .tool-call-timeline .tool-event-completed {
          border-left-color: #10b981;
          animation: timeline-fade-in 0.3s ease-in;
        }
        .tool-call-timeline .tool-event-failed {
          border-left-color: #ef4444;
        }
        @keyframes timeline-shimmer {
          0% { opacity: 0.65; }
          50% { opacity: 1; }
          100% { opacity: 0.65; }
        }
        @keyframes timeline-fade-in {
          0% { opacity: 0; transform: translateY(4px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div className="font-medium text-blue-900 mb-2">Tool Activity</div>
      <div className="space-y-2">
        {events.map((event) => {
          const statusClass =
            event.status === 'failed'
              ? 'tool-event tool-event-failed'
              : event.status === 'completed'
              ? 'tool-event tool-event-completed'
              : 'tool-event tool-event-in_progress';

          return (
            <div key={event.id} className={statusClass}>
              <div className="tool-icon">{getIcon(event.toolType)}</div>
              <div className="tool-body">
                <div className="tool-header">
                  <span className="tool-name">{event.toolName}</span>
                  <span className={`tool-status ${event.status}`}>{STATUS_LABEL[event.status]}</span>
                </div>
                {event.arguments && (
                  <details className="tool-args">
                    <summary>Inputs: {truncate(event.arguments, 120)}</summary>
                    <pre>{event.arguments}</pre>
                  </details>
                )}
                {event.result && event.status === 'completed' && (
                  <details className="tool-result">
                    <summary>Result preview</summary>
                    <pre>{event.result}</pre>
                  </details>
                )}
                {event.error && (
                  <div className="tool-error">Error: {event.error}</div>
                )}
              </div>
              <div className="tool-meta">
                {formatTimestamp(event.startTime)}
                {event.endTime ? ` → ${formatTimestamp(event.endTime)}` : ''}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
