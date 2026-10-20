import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface UserMessageProps {
  content: string;
}

export function UserMessage({ content }: UserMessageProps) {
  const [copied, setCopied] = useState(false);
  const [hovered, setHovered] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div
      style={{ marginBottom: '0.75rem', animation: 'fadeSlideIn 0.2s ease-out' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
        <div
          style={{
            maxWidth: '85%',
            borderRadius: 12,
            padding: '0.75rem 1.25rem',
            backgroundColor: 'hsl(var(--cc-bg-300))',
            boxShadow: '0px 4px 24px 0px rgba(0, 0, 0, 0.02)',
            color: 'hsl(var(--cc-text-000))',
            fontFamily: 'var(--cc-font-ui)',
            fontSize: '0.875rem',
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {content}
        </div>

        {/* Hover action buttons */}
        <div
          style={{
            display: 'flex',
            gap: '0.125rem',
            opacity: hovered ? 1 : 0,
            transition: 'opacity 0.15s ease',
          }}
        >
          <button
            onClick={handleCopy}
            className="cc-btn-ghost"
            title={copied ? 'Copied' : 'Copy'}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 24,
              height: 24,
              background: 'transparent',
              border: 'none',
              borderRadius: 'var(--cc-radius-sm)',
              color: copied ? 'hsl(var(--cc-accent-main-000))' : 'hsl(var(--cc-text-500))',
              cursor: 'pointer',
            }}
          >
            {copied ? <Check style={{ width: 12, height: 12 }} /> : <Copy style={{ width: 12, height: 12 }} />}
          </button>
        </div>
      </div>
    </div>
  );
}
