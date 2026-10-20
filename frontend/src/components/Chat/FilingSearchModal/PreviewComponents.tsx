/**
 * Preview header and navigation components
 */

import React from 'react';
import { Filing, Transcript, previewStyles, buttonStyles, formatDate, useDocumentSearch } from '../../Filings';
import { ExpandIcon, PdfIcon, ChevronLeft, ChevronRight, SearchIcon, CloseIcon } from './icons';

// =============================================================================
// View Mode Toggle
// =============================================================================

interface ViewModeToggleProps {
  mode: 'markdown' | 'html';
  onChange: (mode: 'markdown' | 'html') => void;
}

export const ViewModeToggle: React.FC<ViewModeToggleProps> = ({ mode, onChange }) => (
  <div style={{ display: 'flex', background: '#f0f0f0', borderRadius: '4px', padding: '2px' }}>
    {(['markdown', 'html'] as const).map((m) => (
      <button
        key={m}
        onClick={() => onChange(m)}
        style={{
          padding: '3px 8px', 
          fontSize: '11px', 
          border: 'none', 
          borderRadius: '3px', 
          cursor: 'pointer',
          background: mode === m ? '#fff' : 'transparent',
          color: mode === m ? '#333' : '#888',
          boxShadow: mode === m ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
        }}
      >
        {m === 'markdown' ? 'Clean' : 'Original'}
      </button>
    ))}
  </div>
);

// =============================================================================
// Page Navigation
// =============================================================================

interface PageNavProps {
  currentPage: number;
  totalPages: number;
  onChange: (page: number) => void;
}

export const PageNav: React.FC<PageNavProps> = ({ currentPage, totalPages, onChange }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
    <button 
      onClick={() => onChange(Math.max(1, currentPage - 1))} 
      disabled={currentPage === 1} 
      style={{ 
        background: 'none', 
        border: '1px solid #ddd', 
        borderRadius: '3px', 
        padding: '2px 6px', 
        cursor: currentPage === 1 ? 'not-allowed' : 'pointer', 
        opacity: currentPage === 1 ? 0.5 : 1 
      }}
    >
      <ChevronLeft />
    </button>
    <span style={{ fontSize: '11px', color: '#666', minWidth: '60px', textAlign: 'center' }}>
      Page {currentPage} of {totalPages}
    </span>
    <button 
      onClick={() => onChange(Math.min(totalPages, currentPage + 1))} 
      disabled={currentPage === totalPages} 
      style={{ 
        background: 'none', 
        border: '1px solid #ddd', 
        borderRadius: '3px', 
        padding: '2px 6px', 
        cursor: currentPage === totalPages ? 'not-allowed' : 'pointer', 
        opacity: currentPage === totalPages ? 0.5 : 1 
      }}
    >
      <ChevronRight />
    </button>
  </div>
);

// =============================================================================
// Filing Preview Header
// =============================================================================

interface PreviewHeaderProps {
  filing: Filing;
  viewMode: 'markdown' | 'html';
  onViewModeChange: (mode: 'markdown' | 'html') => void;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onExpand: () => void;
  onExportPdf?: () => void;
  isExportingPdf?: boolean;
}

export const PreviewHeader: React.FC<PreviewHeaderProps> = ({ 
  filing, 
  viewMode, 
  onViewModeChange, 
  currentPage, 
  totalPages, 
  onPageChange, 
  onExpand, 
  onExportPdf, 
  isExportingPdf 
}) => (
  <div style={previewStyles.header}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <span style={{ 
        padding: '3px 8px', 
        background: '#e8f5e9', 
        color: '#2e7d32', 
        fontSize: '11px', 
        fontWeight: 500, 
        borderRadius: '4px' 
      }}>
        Currently viewing
      </span>
      <span style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
        {filing.type} - {formatDate(filing.filingDate)}
      </span>
      <ViewModeToggle mode={viewMode} onChange={onViewModeChange} />
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {viewMode === 'markdown' && totalPages > 1 && (
        <PageNav currentPage={currentPage} totalPages={totalPages} onChange={onPageChange} />
      )}
      {onExportPdf && (
        <button 
          onClick={onExportPdf} 
          disabled={isExportingPdf}
          style={{ ...buttonStyles.secondary, opacity: isExportingPdf ? 0.6 : 1 }} 
          title="Download as PDF"
        >
          <PdfIcon /> {isExportingPdf ? 'Exporting...' : 'PDF'}
        </button>
      )}
      <a 
        href={filing.link} 
        target="_blank" 
        rel="noopener noreferrer" 
        style={{ fontSize: '12px', color: '#1976d2', textDecoration: 'none' }}
      >
        Open in SEC EDGAR →
      </a>
      <button onClick={onExpand} style={buttonStyles.secondary} title="Expand preview">
        <ExpandIcon /> Expand
      </button>
    </div>
  </div>
);

// =============================================================================
// Transcript Preview Header
// =============================================================================

interface TranscriptPreviewHeaderProps {
  transcript: Transcript;
  onExpand: () => void;
}

export const TranscriptPreviewHeader: React.FC<TranscriptPreviewHeaderProps> = ({ transcript, onExpand }) => (
  <div style={previewStyles.header}>
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
      <span style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
        Q{transcript.quarter} {transcript.year}
      </span>
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <button onClick={onExpand} style={buttonStyles.secondary} title="Expand preview">
        <ExpandIcon /> Expand
      </button>
    </div>
  </div>
);

// =============================================================================
// Document Search Bar
// =============================================================================

interface DocumentSearchBarProps {
  docSearch: ReturnType<typeof useDocumentSearch>;
  iframeRef: React.RefObject<HTMLIFrameElement>;
}

export const DocumentSearchBar: React.FC<DocumentSearchBarProps> = ({ docSearch, iframeRef }) => (
  <div style={{ 
    display: 'flex', 
    alignItems: 'center', 
    gap: '4px', 
    padding: '4px 8px', 
    background: '#f5f5f5', 
    borderRadius: '6px', 
    border: '1px solid #e0e0e0' 
  }}>
    <SearchIcon size={14} />
    <input
      type="text"
      value={docSearch.searchQuery}
      onChange={(e) => { 
        docSearch.setSearchQuery(e.target.value); 
        setTimeout(() => docSearch.search(e.target.value, iframeRef.current), 100); 
      }}
      onKeyDown={(e) => { 
        if (e.key === 'Enter') { 
          e.preventDefault(); 
          docSearch.navigate(e.shiftKey ? 'prev' : 'next', iframeRef.current); 
        } 
      }}
      placeholder="Search in document..."
      style={{ 
        border: 'none', 
        outline: 'none', 
        background: 'transparent', 
        fontSize: '13px', 
        width: '160px' 
      }}
    />
    {docSearch.resultCount > 0 && (
      <>
        <span style={{ 
          fontSize: '11px', 
          color: '#666', 
          whiteSpace: 'nowrap', 
          padding: '0 4px' 
        }}>
          {docSearch.currentIndex + 1} of {docSearch.resultCount}
        </span>
        <button 
          onClick={() => docSearch.navigate('prev', iframeRef.current)} 
          style={{ 
            background: 'none', 
            border: 'none', 
            cursor: 'pointer', 
            padding: '4px', 
            color: '#666' 
          }} 
          title="Previous"
        >
          <ChevronLeft />
        </button>
        <button 
          onClick={() => docSearch.navigate('next', iframeRef.current)} 
          style={{ 
            background: 'none', 
            border: 'none', 
            cursor: 'pointer', 
            padding: '4px', 
            color: '#666' 
          }} 
          title="Next"
        >
          <ChevronRight />
        </button>
      </>
    )}
  </div>
);
