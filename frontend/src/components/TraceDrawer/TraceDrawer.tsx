import { useMemo, useState } from 'react';
import type { ReasoningTrace, ReasoningTraceStep } from '@/types';

interface TraceDrawerProps {
  trace: ReasoningTrace;
  onClose: () => void;
}

function formatMs(ms?: number): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms} ms`;
  const seconds = (ms / 1000).toFixed(2);
  return `${seconds}s`;
}

function StepItem({ step, index }: { step: ReasoningTraceStep; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const summary = useMemo(() => {
    const name = step.name || `Step ${index + 1}`;
    const duration = formatMs(step.durationMs);
    return `${name} · ${duration}`;
  }, [step, index]);

  const hasDetails = Boolean(step.inputs || step.outputs || step.error);

  return (
    <div className="rounded-md" style={{ boxShadow: '0 0 0 1px var(--border) inset', background: 'color-mix(in oklab, var(--bg-surface), white 1%)' }}>
      <button
        type="button"
        className="w-full flex items-center justify-between p-3 text-left"
        style={{ color: 'var(--text-primary)' }}
        onClick={() => hasDetails && setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-6 h-6 text-xs font-medium rounded-full" style={{ background: 'color-mix(in oklab, var(--bg-subtle), white 6%)', color: 'var(--text-secondary)' }}>
            {index + 1}
          </span>
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{summary}</span>
        </div>
        {hasDetails && (
          <svg
            className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            style={{ color: 'var(--text-secondary)' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          {step.error && (
            <div className="p-2 rounded text-sm" style={{ color: 'var(--danger)', background: 'color-mix(in oklab, var(--bg-surface), white 2%)', boxShadow: '0 0 0 1px var(--border) inset' }}>
              {step.error}
            </div>
          )}
          {step.inputs && (
            <div>
              <div className="text-xs font-semibold mb-1" style={{ color: 'var(--text-secondary)' }}>Inputs</div>
              <pre className="text-xs p-2 rounded overflow-auto" style={{ background: 'color-mix(in oklab, var(--bg-subtle), white 6%)', boxShadow: '0 0 0 1px var(--border) inset', color: 'var(--text-primary)' }}>
                {JSON.stringify(step.inputs, null, 2)}
              </pre>
            </div>
          )}
          {step.outputs && (
            <div>
              <div className="text-xs font-semibold mb-1" style={{ color: 'var(--text-secondary)' }}>Outputs</div>
              <pre className="text-xs p-2 rounded overflow-auto" style={{ background: 'color-mix(in oklab, var(--bg-subtle), white 6%)', boxShadow: '0 0 0 1px var(--border) inset', color: 'var(--text-primary)' }}>
                {JSON.stringify(step.outputs, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const TraceDrawer = ({ trace, onClose }: TraceDrawerProps) => {
  const total = formatMs(trace.totalDurationMs);
  const handoffCount = trace.handoffs?.length ?? 0;

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(trace, null, 2));
    } catch {
      /* no-op */
    }
  };

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-label="Close trace overlay" />
      <div className="absolute right-0 top-0 h-full w-full max-w-xl z-50 flex flex-col" role="dialog" aria-modal="true" aria-label="Reasoning trace" style={{ background: 'var(--bg-surface)', boxShadow: '-1px 0 0 0 var(--border) inset' }}>
        <div className="p-4 flex items-center justify-between" style={{ boxShadow: '0 -1px 0 0 var(--border) inset' }}>
          <div>
            <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>Reasoning Trace</div>
            <div className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{trace.steps.length} steps · {total}</div>
          </div>
          <div className="flex items-center gap-2">
            {handoffCount > 0 && (
              <span className="px-2 py-1 text-xs rounded" style={{ background: 'color-mix(in oklab, var(--accent), white 85%)', color: 'color-mix(in oklab, var(--accent), black 30%)' }}>{handoffCount} handoffs</span>
            )}
            <button
              type="button"
              onClick={copyJson}
              className="px-2 py-1 text-xs rounded"
              style={{ boxShadow: '0 0 0 1px var(--border) inset', color: 'var(--text-secondary)' }}
              aria-label="Copy trace JSON"
            >
              Copy JSON
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded"
              style={{ color: 'var(--text-secondary)' }}
              aria-label="Close trace"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ color: 'var(--text-secondary)' }}>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        <div className="p-4 space-y-3 overflow-auto">
          {trace.steps.map((step, idx) => (
            <StepItem key={idx} step={step} index={idx} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default TraceDrawer;
