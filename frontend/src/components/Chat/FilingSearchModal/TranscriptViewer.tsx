/**
 * Transcript viewer component with parsing and formatting
 */

import React from 'react';

// =============================================================================
// Transcript Parsing Utilities
// =============================================================================

// Parse and format earnings call transcript
const parseTranscript = (content: string) => {
  // Split by speaker pattern: "Name:" at start of line or after newline
  const speakerPattern = /^([A-Z][a-zA-Z\s\.]+?):\s*/gm;
  const parts: { speaker: string; text: string }[] = [];
  
  let lastIndex = 0;
  let match;
  let lastSpeaker = '';
  
  while ((match = speakerPattern.exec(content)) !== null) {
    if (lastSpeaker && match.index > lastIndex) {
      const text = content.slice(lastIndex, match.index).trim();
      if (text) {
        parts.push({ speaker: lastSpeaker, text });
      }
    }
    lastSpeaker = match[1].trim();
    lastIndex = match.index + match[0].length;
  }
  
  if (lastSpeaker && lastIndex < content.length) {
    const text = content.slice(lastIndex).trim();
    if (text) {
      parts.push({ speaker: lastSpeaker, text });
    }
  }
  
  if (parts.length === 0 && content.trim()) {
    return [{ speaker: '', text: content.trim() }];
  }
  
  return parts;
};

// Split text into paragraphs (by double newline or long single sentences)
const formatParagraphs = (text: string) => {
  // First try splitting by double newlines
  let paragraphs = text.split(/\n\s*\n/).filter(p => p.trim());
  
  // If only one paragraph and it's long, try to break it up
  if (paragraphs.length === 1 && paragraphs[0].length > 500) {
    // Split by sentence endings followed by space and capital letter
    const sentences = paragraphs[0].split(/(?<=[.!?])\s+(?=[A-Z])/);
    // Group into ~3-4 sentence chunks
    paragraphs = [];
    let current = '';
    sentences.forEach((s, i) => {
      current += (current ? ' ' : '') + s;
      if ((i + 1) % 4 === 0 || i === sentences.length - 1) {
        paragraphs.push(current);
        current = '';
      }
    });
  }
  
  return paragraphs;
};

// =============================================================================
// Transcript Viewer Component
// =============================================================================

interface TranscriptViewerProps {
  content: string;
  expanded?: boolean;
}

export const TranscriptViewer: React.FC<TranscriptViewerProps> = ({ content, expanded }) => {
  const parts = React.useMemo(() => parseTranscript(content), [content]);
  
  return (
    <div style={{ 
      flex: 1,
      overflow: 'auto', 
      padding: expanded ? '32px 56px' : '20px 24px',
      background: '#fff',
    }}>
      {parts.map((part, idx) => {
        const paragraphs = formatParagraphs(part.text);
        return (
          <div key={idx} style={{ marginBottom: expanded ? '28px' : '20px' }}>
            {part.speaker && (
              <div style={{
                marginBottom: '8px',
                paddingBottom: '6px',
                borderBottom: '1px solid #e5e5e5',
              }}>
                <span style={{
                  fontSize: expanded ? '14px' : '13px',
                  fontWeight: 600,
                  color: '#1a1a1a',
                }}>
                  {part.speaker}
                </span>
              </div>
            )}
            <div style={{
              fontSize: expanded ? '15px' : '13px',
              lineHeight: '1.75',
              color: '#333',
            }}>
              {paragraphs.map((para, pIdx) => (
                <p key={pIdx} style={{ 
                  margin: 0,
                  marginBottom: pIdx < paragraphs.length - 1 ? (expanded ? '16px' : '12px') : 0,
                }}>
                  {para}
                </p>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
