import { useState, useEffect } from 'react';
import sentryIcon from '@/assets/binomial-icon-logo.png';

const LOADER_TEXTS = [
  'Thinking...',
  'Gathering data...',
  'Analyzing...',
  'Processing...',
  'Preparing response...',
  'Synthesizing...',
];

interface LoadingIndicatorProps {
  statusMessage?: string;
}

export function LoadingIndicator({ statusMessage }: LoadingIndicatorProps) {
  const [textIdx, setTextIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTextIdx((i) => (i + 1) % LOADER_TEXTS.length), 2500);
    return () => clearInterval(id);
  }, []);

  const displayText = statusMessage || LOADER_TEXTS[textIdx];

  return (
    <div className="thinking-indicator">
      <img src={sentryIcon} alt="" width={18} height={18} className="pulse-icon thinking-icon" />
      <span className="thinking-text">{displayText}</span>
    </div>
  );
}
