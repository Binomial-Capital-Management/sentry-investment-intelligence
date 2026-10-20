/**
 * Expanded preview modals for filings and transcripts
 */

import React from 'react';
import { 
  Filing, 
  Transcript, 
  expandedModalStyles, 
  useDocumentSearch,
  MarkdownViewer,
  formatDate,
} from '../../Filings';
import { CloseIcon } from './icons';
import { DocumentSearchBar } from './PreviewComponents';
import { TranscriptViewer } from './TranscriptViewer';

// =============================================================================
// Expanded Filing Preview Modal
// =============================================================================

interface ExpandedPreviewModalProps {
  filing: Filing;
  ticker: { symbol: string } | null;
  viewMode: 'markdown' | 'html';
  markdownContent: string;
  markdownPages: { page: number; content: string }[];
  previewContent: string;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  docSearch: ReturnType<typeof useDocumentSearch>;
  iframeRef: React.RefObject<HTMLIFrameElement>;
  onClose: () => void;
}

export const ExpandedPreviewModal: React.FC<ExpandedPreviewModalProps> = ({ 
  filing, 
  ticker, 
  viewMode, 
  markdownContent, 
  markdownPages, 
  previewContent, 
  currentPage, 
  totalPages, 
  onPageChange, 
  docSearch, 
  iframeRef, 
  onClose 
}) => (
  <div style={expandedModalStyles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
    <div style={expandedModalStyles.container}>
      <div style={expandedModalStyles.header}>
        <span style={{ fontSize: '14px', fontWeight: 600, color: '#333' }}>
          {ticker?.symbol} {filing.type} - {formatDate(filing.filingDate)}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <DocumentSearchBar docSearch={docSearch} iframeRef={iframeRef} />
          <a 
            href={filing.link} 
            target="_blank" 
            rel="noopener noreferrer" 
            style={{ 
              fontSize: '12px', 
              color: '#1976d2', 
              textDecoration: 'none', 
              padding: '6px 12px', 
              border: '1px solid #1976d2', 
              borderRadius: '6px' 
            }}
          >
            Open in SEC EDGAR →
          </a>
          <button 
            onClick={onClose} 
            style={{ 
              background: '#f5f5f5', 
              border: '1px solid #ddd', 
              borderRadius: '6px', 
              padding: '6px 12px', 
              cursor: 'pointer', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px', 
              fontSize: '12px', 
              color: '#555' 
            }}
          >
            <CloseIcon size={14} /> Close
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {viewMode === 'markdown' && markdownContent ? (
          <MarkdownViewer 
            content={markdownContent} 
            pages={markdownPages} 
            currentPage={currentPage} 
            totalPages={totalPages} 
            onPageChange={onPageChange} 
            expanded 
          />
        ) : (
          <iframe 
            ref={iframeRef} 
            srcDoc={previewContent} 
            sandbox="allow-same-origin allow-scripts" 
            style={{ width: '100%', height: '100%', border: 'none' }} 
            title="Expanded Preview" 
            onLoad={() => docSearch.searchQuery && docSearch.search(docSearch.searchQuery, iframeRef.current)} 
          />
        )}
      </div>
    </div>
  </div>
);

// =============================================================================
// Expanded Transcript Modal
// =============================================================================

interface ExpandedTranscriptModalProps {
  transcript: Transcript;
  content: string;
  ticker: { symbol: string } | null;
  onClose: () => void;
}

export const ExpandedTranscriptModal: React.FC<ExpandedTranscriptModalProps> = ({ 
  transcript, 
  content, 
  ticker, 
  onClose 
}) => (
  <div style={expandedModalStyles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
    <div style={expandedModalStyles.container}>
      <div style={expandedModalStyles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ 
            padding: '3px 8px', 
            background: '#fff3e0', 
            color: '#e65100', 
            fontSize: '11px', 
            fontWeight: 500, 
            borderRadius: '4px' 
          }}>
            Earnings Call
          </span>
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#333' }}>
            {ticker?.symbol} Q{transcript.quarter} {transcript.year}
          </span>
        </div>
        <button 
          onClick={onClose} 
          style={{ 
            background: '#f5f5f5', 
            border: '1px solid #ddd', 
            borderRadius: '6px', 
            padding: '6px 12px', 
            cursor: 'pointer', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '4px', 
            fontSize: '12px', 
            color: '#555' 
          }}
        >
          <CloseIcon size={14} /> Close
        </button>
      </div>
      <TranscriptViewer content={content} expanded />
    </div>
  </div>
);
