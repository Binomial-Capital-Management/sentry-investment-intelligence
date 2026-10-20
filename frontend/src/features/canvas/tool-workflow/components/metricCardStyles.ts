import { C } from '@/features/canvas/data-workspace/chart/creator/tokens';

export const sentimentAccents = {
  positive: { bg: 'hsl(152 60% 97%)', accent: 'hsl(152 55% 40%)' },
  negative: { bg: 'hsl(0 55% 97%)',   accent: 'hsl(0 55% 44%)' },
  neutral:  { bg: C.bgSubtle,         accent: C.textMuted },
  warning:  { bg: 'hsl(38 60% 97%)',  accent: 'hsl(38 55% 40%)' },
  info:     { bg: 'hsl(217 60% 97%)', accent: 'hsl(217 55% 44%)' },
} as const;

export type Sentiment = keyof typeof sentimentAccents;

export const cardStyle = (s: Sentiment) => {
  const a = sentimentAccents[s] || sentimentAccents.neutral;
  return {
    wrapper: {
      background: a.bg,
      border: C.border,
      borderRadius: '0.75rem',
      padding: 'clamp(0.5rem, 5cqi, 1rem) clamp(0.625rem, 6cqi, 1.25rem)',
      containerType: 'inline-size',
    } as React.CSSProperties,
    label: {
      fontWeight: 600,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
      fontSize: 'clamp(0.5rem, 6cqi, 0.688rem)',
      color: a.accent,
    } as React.CSSProperties,
    value: {
      fontSize: 'clamp(0.875rem, 14cqi, 1.5rem)',
      fontWeight: 700,
      color: s === 'neutral' ? C.text : a.accent,
      marginTop: '0.25rem',
      lineHeight: 1.2,
    } as React.CSSProperties,
  };
};
