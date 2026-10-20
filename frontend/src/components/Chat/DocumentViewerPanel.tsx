/**
 * DocumentViewerPanel - SEC filing content viewer
 * 
 * Displays SEC filing HTML in a sandboxed iframe.
 * Fetches on-demand from our proxy endpoint which gets content from SEC EDGAR.
 */

import React, { useState, useEffect, useCallback } from 'react';

interface DocumentViewerPanelProps {
  cik: string;
  accessionNumber: string;
  formType?: string;
  filingDate?: string;
  symbol?: string;
  onClose?: () => void;
  className?: string;
}

const DocumentViewerPanel: React.FC<DocumentViewerPanelProps> = ({
  cik,
  accessionNumber,
  formType,
  filingDate,
  symbol,
  onClose,
  className = '',
}) => {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const fetchContent = useCallback(async () => {
    if (!cik || !accessionNumber) {
      setError('Missing CIK or accession number');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        cik,
        accession: accessionNumber,
      });

      const response = await fetch(`/api/filings/preview?${params.toString()}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to load filing (${response.status})`);
      }

      const html = await response.text();
      setContent(html);
    } catch (err) {
      console.error('Failed to fetch filing:', err);
      setError(err instanceof Error ? err.message : 'Failed to load filing');
    } finally {
      setIsLoading(false);
    }
  }, [cik, accessionNumber]);

  useEffect(() => {
    fetchContent();
  }, [fetchContent]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      });
    } catch {
      return dateStr;
    }
  };

  const handleOpenExternal = () => {
    // Construct SEC EDGAR URL
    const cikClean = cik.replace(/^0+/, '');
    const accessionClean = accessionNumber.replace(/-/g, '');
    const secUrl = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cikClean}&type=&dateb=&owner=include&count=40`;
    window.open(secUrl, '_blank');
  };

  const containerClasses = isFullscreen
    ? 'fixed inset-0 z-50 bg-white'
    : `flex flex-col h-full bg-white ${className}`;

  return (
    <div className={containerClasses}>
      {/* Header */}
      <div 
        className="flex items-center justify-between px-4 py-2 border-b border-gray-200 flex-shrink-0"
        style={{ backgroundColor: '#f8f8f8' }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-gray-500 flex-shrink-0">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
          <div className="min-w-0">
            <div className="text-[13px] font-medium text-gray-800 truncate">
              {symbol && `${symbol} `}{formType || 'SEC Filing'}
            </div>
            {filingDate && (
              <div className="text-[11px] text-gray-500">
                Filed {formatDate(filingDate)}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Refresh Button */}
          <button
            onClick={fetchContent}
            disabled={isLoading}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded"
            title="Refresh"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className={isLoading ? 'animate-spin' : ''}>
              <path d="M23 4v6h-6M1 20v-6h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {/* Open in SEC */}
          <button
            onClick={handleOpenExternal}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded"
            title="Open in SEC EDGAR"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M8 3v3a2 2 0 01-2 2H3M21 8h-3a2 2 0 01-2-2V3M3 16h3a2 2 0 012 2v3M16 21v-3a2 2 0 012-2h3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M8 3H5a2 2 0 00-2 2v3M21 8V5a2 2 0 00-2-2h-3M3 16v3a2 2 0 002 2h3M16 21h3a2 2 0 002-2v-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>

          {/* Close Button */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded"
              title="Close"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden relative">
        {isLoading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-50">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-700 rounded-full animate-spin" />
            <p className="mt-3 text-[12px] text-gray-500">Loading from SEC EDGAR...</p>
            <p className="mt-1 text-[10px] text-gray-400">This may take a few seconds</p>
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-50 px-8 text-center">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="text-red-300 mb-4">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <p className="text-[13px] text-gray-700 font-medium">Failed to Load Filing</p>
            <p className="text-[12px] text-gray-500 mt-1">{error}</p>
            <button
              onClick={fetchContent}
              className="mt-4 px-4 py-2 text-[12px] text-white bg-gray-800 hover:bg-gray-700 rounded"
            >
              Try Again
            </button>
          </div>
        ) : (
          <iframe
            srcDoc={content}
            sandbox="allow-same-origin"
            className="w-full h-full border-0"
            title="SEC Filing Document"
          />
        )}
      </div>

      {/* Footer Info */}
      <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 flex items-center justify-between text-[10px] text-gray-400 flex-shrink-0">
        <span>CIK: {cik} • Accession: {accessionNumber}</span>
        <span>Source: SEC EDGAR</span>
      </div>
    </div>
  );
};

export default DocumentViewerPanel;
