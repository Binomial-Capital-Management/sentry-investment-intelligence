/**
 * ActionConfirmationCard - Inline card for confirming destructive AI agent actions
 * Renders within the chat message list (not as a modal overlay)
 */

import { Trash2, RefreshCw, AlertCircle, Check } from 'lucide-react';
import type { AgentAction } from '../../types';

interface ActionConfirmationCardProps {
  action: AgentAction;
  onConfirm: () => void;
  onCancel: () => void;
}

const ACTION_INFO: Record<string, {
  title: string;
  icon: React.ElementType;
  variant: 'danger' | 'warning';
  getMessage: (action: any) => string;
}> = {
  remove_dataset: {
    title: 'Remove Dataset',
    icon: Trash2,
    variant: 'danger',
    getMessage: (action) => `Remove "${action.dataset_id}" from workspace?`,
  },
  clear_workspace: {
    title: 'Clear Workspace',
    icon: Trash2,
    variant: 'danger',
    getMessage: () => 'Clear all datasets from workspace?',
  },
  modify_process_tickers: {
    title: 'Modify Portfolio',
    icon: RefreshCw,
    variant: 'warning',
    getMessage: (action) => `Change tickers to: ${action.tickers?.join(', ')}?`,
  },
};

export function ActionConfirmationCard({
  action,
  onConfirm,
  onCancel,
}: ActionConfirmationCardProps) {
  const info = ACTION_INFO[action.type] || {
    title: 'Confirm Action',
    icon: AlertCircle,
    variant: 'warning' as const,
    getMessage: () => `Allow AI to perform: ${action.type}?`,
  };

  const Icon = info.icon;
  const isDanger = info.variant === 'danger';

  return (
    <div style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
      <div style={{
        backgroundColor: 'hsl(var(--cc-bg-000))',
        borderRadius: 'var(--cc-radius-lg)',
        border: `1px solid ${isDanger ? 'hsl(var(--cc-danger-900))' : 'hsl(40 80% 90%)'}`,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.5rem 0.75rem',
          backgroundColor: isDanger ? 'hsl(var(--cc-danger-900))' : 'hsl(40 80% 95%)',
          borderBottom: `1px solid ${isDanger ? 'hsl(var(--cc-danger-900))' : 'hsl(40 80% 90%)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Icon style={{
              width: 14,
              height: 14,
              color: isDanger ? 'hsl(var(--cc-danger-100))' : 'hsl(40 80% 45%)',
            }} />
            <span style={{
              fontFamily: 'var(--cc-font-ui)',
              fontSize: '0.688rem',
              fontWeight: 500,
              color: isDanger ? 'hsl(var(--cc-danger-000))' : 'hsl(40 80% 30%)',
            }}>
              {info.title}
            </span>
          </div>
          <span style={{
            fontFamily: 'var(--cc-font-ui)',
            fontSize: '0.625rem',
            color: 'hsl(var(--cc-text-500))',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            AI Request
          </span>
        </div>

        {/* Body */}
        <div style={{
          padding: '0.625rem 0.75rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
        }}>
          <p style={{
            fontFamily: 'var(--cc-font-ui)',
            fontSize: '0.688rem',
            color: 'hsl(var(--cc-text-300))',
            flex: 1,
            margin: 0,
          }}>
            {info.getMessage(action)}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
            <button
              onClick={onCancel}
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
              Cancel
            </button>
            <button
              onClick={onConfirm}
              style={{
                padding: '0.25rem 0.75rem',
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.688rem',
                fontWeight: 500,
                backgroundColor: isDanger ? 'hsl(var(--cc-danger-100))' : 'hsl(40 80% 50%)',
                color: 'hsl(var(--cc-oncolor-100))',
                border: 'none',
                borderRadius: 'var(--cc-radius-md)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                transition: 'background-color 0.15s ease',
              }}
            >
              <Check style={{ width: 12, height: 12 }} />
              Allow
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
