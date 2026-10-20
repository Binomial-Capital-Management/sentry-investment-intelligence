import { Check } from 'lucide-react';
import type { PendingUpdate } from '../../types';

interface PendingUpdateCardProps {
  pendingUpdate: PendingUpdate;
  applyingUpdate: boolean;
  onApply: () => void;
  onDismiss: () => void;
}

export function PendingUpdateCard({
  pendingUpdate,
  applyingUpdate,
  onApply,
  onDismiss,
}: PendingUpdateCardProps) {
  return (
    <div style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
      <div style={{
        backgroundColor: 'hsl(var(--cc-bg-000))',
        borderRadius: 'var(--cc-radius-lg)',
        border: '1px solid hsl(var(--cc-border-300) / 15%)',
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.5rem 0.75rem',
          backgroundColor: 'hsl(var(--cc-bg-200))',
          borderBottom: '1px solid hsl(var(--cc-border-300) / 15%)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: 'hsl(142 71% 45%)',
            }} />
            <span style={{
              fontFamily: 'var(--cc-font-ui)',
              fontSize: '0.688rem',
              fontWeight: 500,
              color: 'hsl(var(--cc-text-200))',
            }}>
              Analysis Complete
            </span>
          </div>
          <span style={{
            fontFamily: 'var(--cc-font-ui)',
            fontSize: '0.625rem',
            color: 'hsl(var(--cc-text-500))',
          }}>
            {pendingUpdate.tickers.join(', ')}
          </span>
        </div>
        <div style={{
          padding: '0.625rem 0.75rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <p style={{
            fontFamily: 'var(--cc-font-ui)',
            fontSize: '0.688rem',
            color: 'hsl(var(--cc-text-400))',
            margin: 0,
          }}>
            Ready to update <span style={{ color: 'hsl(var(--cc-text-200))', fontWeight: 500 }}>{pendingUpdate.toolId}</span>
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              onClick={onDismiss}
              className="cc-btn-ghost"
              style={{
                padding: '0.25rem 0.625rem',
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.688rem',
                color: 'hsl(var(--cc-text-400))',
                background: 'transparent',
                border: 'none',
                borderRadius: 'var(--cc-radius-md)',
                cursor: 'pointer',
              }}
            >
              Dismiss
            </button>
            <button
              onClick={onApply}
              disabled={applyingUpdate}
              style={{
                padding: '0.25rem 0.75rem',
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.688rem',
                fontWeight: 500,
                backgroundColor: 'hsl(var(--cc-accent-main-000))',
                color: 'hsl(var(--cc-oncolor-100))',
                border: 'none',
                borderRadius: 'var(--cc-radius-md)',
                cursor: applyingUpdate ? 'not-allowed' : 'pointer',
                opacity: applyingUpdate ? 0.5 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                transition: 'background-color 0.15s ease',
              }}
            >
              {applyingUpdate ? (
                <>
                  <div style={{
                    width: 12,
                    height: 12,
                    border: '2px solid rgba(255,255,255,0.3)',
                    borderTopColor: 'white',
                    borderRadius: '50%',
                    animation: 'spin 0.6s linear infinite',
                  }} />
                  Applying...
                </>
              ) : (
                <>
                  <Check style={{ width: 12, height: 12 }} />
                  Apply
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
