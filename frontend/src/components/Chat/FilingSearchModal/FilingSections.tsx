/**
 * Filing list section components
 */

import React from 'react';
import { Filing, Transcript, listStyles, formatDate, getPeriodLabel, formatPeriodEnd } from '../../Filings';

// =============================================================================
// Filing Section
// =============================================================================

interface FilingSectionProps { 
  title: string; 
  filings: Filing[]; 
  previewFiling: Filing | null;
  onToggle: (id: string) => void;
  onPreview: (f: Filing) => void;
  showPeriod?: boolean;
  defaultExpanded?: boolean;
}

export const FilingSection: React.FC<FilingSectionProps> = ({ 
  title, 
  filings, 
  previewFiling, 
  onToggle, 
  onPreview, 
  showPeriod, 
  defaultExpanded = true 
}) => {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);
  
  return (
    <div style={{ marginBottom: '4px' }}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          ...listStyles.sectionHeader,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          border: 'none',
          cursor: 'pointer',
          background: '#f9f9f9',
        }}
      >
        <span>{title} ({filings.length})</span>
        <span style={{ 
          fontSize: '10px', 
          color: '#999', 
          transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', 
          transition: 'transform 0.2s' 
        }}>
          ▼
        </span>
      </button>
      
      {isExpanded && filings.map((f) => (
        <div
          key={f.accessionNumber}
          style={{ 
            ...listStyles.row, 
            background: previewFiling?.accessionNumber === f.accessionNumber ? '#f8f8f8' : 'transparent' 
          }}
          onClick={() => onPreview(f)}
          onMouseEnter={(e) => { 
            if (previewFiling?.accessionNumber !== f.accessionNumber) {
              e.currentTarget.style.background = '#fafafa'; 
            }
          }}
          onMouseLeave={(e) => { 
            if (previewFiling?.accessionNumber !== f.accessionNumber) {
              e.currentTarget.style.background = 'transparent'; 
            }
          }}
        >
          <input 
            type="checkbox" 
            checked={f.selected} 
            onChange={(e) => { e.stopPropagation(); onToggle(f.accessionNumber); }} 
            onClick={(e) => e.stopPropagation()} 
            style={listStyles.checkbox} 
          />
          
          {showPeriod ? (
            <>
              <span style={{ 
                fontSize: '10px', 
                fontWeight: 600, 
                padding: '3px 6px', 
                borderRadius: '3px', 
                background: f.type?.includes('10-K') ? '#e3f2fd' : '#e8f5e9', 
                color: f.type?.includes('10-K') ? '#1976d2' : '#388e3c', 
                whiteSpace: 'nowrap' 
              }}>
                {f.type}
              </span>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#333', minWidth: '65px' }}>
                {getPeriodLabel(f)}
              </span>
              <span style={{ flex: 1, fontSize: '12px', color: '#666' }}>
                Period ended {formatPeriodEnd(f)}
              </span>
            </>
          ) : (
            <>
              <span style={{ fontSize: '12px', color: '#666', width: '55px' }}>{f.type}</span>
              <span style={{ flex: 1, fontSize: '13px', color: '#333' }}>{f.description}</span>
            </>
          )}
          
          <span style={{ fontSize: '11px', color: '#999' }}>{formatDate(f.filingDate)}</span>
        </div>
      ))}
    </div>
  );
};

// =============================================================================
// Transcript Section
// =============================================================================

interface TranscriptSectionProps { 
  title: string; 
  transcripts: Transcript[]; 
  previewTranscript: Transcript | null;
  onToggle: (year: number, quarter: number) => void;
  onPreview: (t: Transcript) => void;
  defaultExpanded?: boolean;
}

export const TranscriptSection: React.FC<TranscriptSectionProps> = ({ 
  title, 
  transcripts, 
  previewTranscript, 
  onToggle, 
  onPreview, 
  defaultExpanded = true 
}) => {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);
  
  return (
    <div style={{ marginBottom: '4px' }}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          ...listStyles.sectionHeader,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          border: 'none',
          cursor: 'pointer',
          background: '#f9f9f9',
        }}
      >
        <span>{title} ({transcripts.length})</span>
        <span style={{ 
          fontSize: '10px', 
          color: '#999', 
          transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', 
          transition: 'transform 0.2s' 
        }}>
          ▼
        </span>
      </button>
      
      {isExpanded && transcripts.map((t) => {
        const isActive = previewTranscript?.year === t.year && previewTranscript?.quarter === t.quarter;
        return (
          <div
            key={`${t.year}-${t.quarter}`}
            style={{ ...listStyles.row, background: isActive ? '#f8f8f8' : 'transparent' }}
            onClick={() => onPreview(t)}
            onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#fafafa'; }}
            onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
          >
            <input 
              type="checkbox" 
              checked={t.selected} 
              onChange={(e) => { e.stopPropagation(); onToggle(t.year, t.quarter); }} 
              onClick={(e) => e.stopPropagation()} 
              style={listStyles.checkbox} 
            />
            <span style={{ 
              fontSize: '10px', 
              fontWeight: 600, 
              padding: '3px 6px', 
              borderRadius: '3px', 
              background: '#fff3e0', 
              color: '#e65100', 
              whiteSpace: 'nowrap' 
            }}>
              Q{t.quarter}
            </span>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#333', minWidth: '50px' }}>
              {t.year}
            </span>
            <span style={{ flex: 1, fontSize: '12px', color: '#666' }}>
              Earnings Call Transcript
            </span>
            <span style={{ fontSize: '11px', color: '#999' }}>{formatDate(t.date)}</span>
          </div>
        );
      })}
    </div>
  );
};
