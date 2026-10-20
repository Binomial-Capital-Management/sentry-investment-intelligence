/**
 * Custom hooks for SEC filings components
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { debounce } from 'lodash';
import { Filing, TickerResult, MarkdownPage, ViewMode, Transcript, TranscriptContent, InstitutionResult, InstitutionFiling, Holding } from './types';
import { useTickerSearch as useTickerSearchShared } from '@/hooks/useTickerSearch';

/**
 * Hook for ticker search functionality
 */
export function useTickerSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<TickerResult | null>(null);

  const query = selectedTicker ? '' : searchQuery;
  const { results, isLoading } = useTickerSearchShared(query);

  const tickerResults = useMemo(
    () => results as TickerResult[],
    [results],
  );

  // Show dropdown when results arrive
  useEffect(() => {
    if (tickerResults.length > 0 && searchQuery && !selectedTicker) {
      setShowDropdown(true);
    }
  }, [tickerResults, searchQuery, selectedTicker]);

  const selectTicker = (ticker: TickerResult) => {
    setSelectedTicker(ticker);
    setSearchQuery('');
    setShowDropdown(false);
  };

  const clearTicker = () => {
    setSelectedTicker(null);
    setSearchQuery('');
  };

  return {
    searchQuery,
    setSearchQuery,
    tickerResults,
    isSearching: isLoading,
    showDropdown,
    setShowDropdown,
    selectedTicker,
    selectTicker,
    clearTicker,
  };
}

/**
 * Hook for filing list management
 */
export interface FilingFilters {
  formType?: string;
  fromDate?: string;
  toDate?: string;
}

export function useFilingsList() {
  const [filings, setFilings] = useState<Filing[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [filters, setFilters] = useState<FilingFilters>({});

  const fetchFilings = useCallback(async (symbol: string, filterOverrides?: FilingFilters) => {
    setIsLoading(true);
    const activeFilters = filterOverrides || filters;
    try {
      const params = new URLSearchParams({ symbol, limit: '100' });
      if (activeFilters.formType) params.append('form_type', activeFilters.formType);
      if (activeFilters.fromDate) params.append('from_date', activeFilters.fromDate);
      if (activeFilters.toDate) params.append('to_date', activeFilters.toDate);
      
      const response = await fetch(`/api/filings/list?${params}`);
      if (!response.ok) throw new Error('Failed to fetch filings');
      const data = await response.json();
      setFilings((data.filings || []).map((f: Filing) => ({ ...f, selected: false })));
    } catch (error) {
      console.error('Filing fetch failed:', error);
      setFilings([]);
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  const toggleFiling = (accessionNumber: string) => {
    setFilings(prev => prev.map(f => 
      f.accessionNumber === accessionNumber ? { ...f, selected: !f.selected } : f
    ));
  };

  const clearSelection = () => {
    setFilings(prev => prev.map(f => ({ ...f, selected: false })));
  };

  const selectedCount = filings.filter(f => f.selected).length;

  return {
    filings,
    setFilings,
    isLoading,
    fetchFilings,
    toggleFiling,
    clearSelection,
    selectedCount,
    filters,
    setFilters,
  };
}

/**
 * Hook for earnings transcripts list management
 */
export function useTranscriptsList() {
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchTranscripts = useCallback(async (symbol: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/filings/transcripts?symbol=${symbol}&limit=20`);
      if (!response.ok) throw new Error('Failed to fetch transcripts');
      const data = await response.json();
      setTranscripts((data.transcripts || []).map((t: Transcript) => ({ ...t, selected: false })));
    } catch (error) {
      console.error('Transcript fetch failed:', error);
      setTranscripts([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const toggleTranscript = (year: number, quarter: number) => {
    setTranscripts(prev => prev.map(t => 
      t.year === year && t.quarter === quarter ? { ...t, selected: !t.selected } : t
    ));
  };

  const clearSelection = () => {
    setTranscripts(prev => prev.map(t => ({ ...t, selected: false })));
  };

  const selectedCount = transcripts.filter(t => t.selected).length;

  return {
    transcripts,
    setTranscripts,
    isLoading,
    fetchTranscripts,
    toggleTranscript,
    clearSelection,
    selectedCount,
  };
}

/**
 * Hook for transcript preview
 */
export function useTranscriptPreview() {
  const [previewTranscript, setPreviewTranscript] = useState<Transcript | null>(null);
  const [transcriptContent, setTranscriptContent] = useState<TranscriptContent | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadTranscript = async (transcript: Transcript) => {
    if (previewTranscript?.year === transcript.year && previewTranscript?.quarter === transcript.quarter) return;
    
    setPreviewTranscript(transcript);
    setTranscriptContent(null);
    setIsLoading(true);
    
    try {
      const response = await fetch(
        `/api/filings/transcript?symbol=${transcript.symbol}&year=${transcript.year}&quarter=${transcript.quarter}`
      );
      if (!response.ok) throw new Error('Failed to fetch transcript');
      const data = await response.json();
      setTranscriptContent(data);
    } catch (error) {
      console.error('Transcript load error:', error);
      setTranscriptContent(null);
    } finally {
      setIsLoading(false);
    }
  };

  const clearPreview = () => {
    setPreviewTranscript(null);
    setTranscriptContent(null);
  };

  return {
    previewTranscript,
    transcriptContent,
    isLoading,
    loadTranscript,
    clearPreview,
  };
}

/**
 * Hook for filing preview
 */
export function useFilingPreview() {
  const [previewFiling, setPreviewFiling] = useState<Filing | null>(null);
  const [previewContent, setPreviewContent] = useState('');
  const [markdownContent, setMarkdownContent] = useState('');
  const [markdownPages, setMarkdownPages] = useState<MarkdownPage[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>('html');
  const [isLoading, setIsLoading] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  const loadPreview = async (filing: Filing, symbol?: string) => {
    if (previewFiling?.accessionNumber === filing.accessionNumber) return;
    
    setPreviewFiling(filing);
    setPreviewContent('');
    setMarkdownContent('');
    setMarkdownPages([]);
    setCurrentPage(1);
    setTotalPages(1);
    setIsLoading(true);
    
    const params = new URLSearchParams();
    if (filing.link) params.append('link', filing.link);
    else {
      params.append('cik', filing.cik);
      params.append('accession', filing.accessionNumber);
    }
    
    // Always fetch HTML first (Original view) - this is the reliable fallback
    try {
      const response = await fetch(`/api/filings/preview?${params}`);
      if (response.ok) {
        const html = await response.text();
        setPreviewContent(html);
      }
    } catch (error) {
      console.error('HTML preview error:', error);
      setPreviewContent(`
        <div style="padding: 60px; text-align: center; font-family: -apple-system, sans-serif;">
          <p style="color: #666; margin-bottom: 16px;">Unable to load preview</p>
          <a href="${filing.link}" target="_blank" rel="noopener" style="color: #2563eb; text-decoration: none;">Open in SEC EDGAR →</a>
        </div>
      `);
    }
    
    // Also try Markdown (Clean view) - optional enhancement
    try {
      const mdResponse = await fetch(`/api/filings/preview-markdown?${params}`);
      if (mdResponse.ok) {
        const data = await mdResponse.json();
        setMarkdownContent(data.markdown || '');
        setMarkdownPages(data.pages || []);
        setTotalPages(data.total_pages || 1);
      }
    } catch (e) {
      console.log('Markdown preview not available');
    }
    
    // Default to HTML (Original) view
    setViewMode('html');
    setIsLoading(false);
  };

  const exportPdf = async (symbol: string, formType: string, year?: number) => {
    setIsExportingPdf(true);
    try {
      const params = new URLSearchParams({
        symbol,
        form_type: formType,
      });
      if (year) params.append('year', year.toString());
      
      const response = await fetch(`/api/filings/export-pdf?${params}`);
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'PDF export failed');
      }
      
      // Download the PDF
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${symbol}_${formType}_${year || 'latest'}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      return true;
    } catch (error) {
      console.error('PDF export error:', error);
      throw error;
    } finally {
      setIsExportingPdf(false);
    }
  };

  const clearPreview = () => {
    setPreviewFiling(null);
    setPreviewContent('');
    setMarkdownContent('');
    setMarkdownPages([]);
  };

  return {
    previewFiling,
    previewContent,
    markdownContent,
    markdownPages,
    currentPage,
    setCurrentPage,
    totalPages,
    viewMode,
    setViewMode,
    isLoading,
    loadPreview,
    clearPreview,
    exportPdf,
    isExportingPdf,
  };
}

/**
 * Hook for document search within iframe
 */
export function useDocumentSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [resultCount, setResultCount] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const search = useCallback((query: string, iframe: HTMLIFrameElement | null, jumpToIndex?: number) => {
    if (!iframe || !query) {
      setResultCount(0);
      setCurrentIndex(0);
      return;
    }

    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (!doc) return;

      // Remove previous highlights
      doc.querySelectorAll('mark.search-highlight').forEach(mark => {
        const parent = mark.parentNode;
        if (parent) {
          parent.replaceChild(doc.createTextNode(mark.textContent || ''), mark);
          parent.normalize();
        }
      });

      if (!query.trim()) {
        setResultCount(0);
        setCurrentIndex(0);
        return;
      }

      // Find and highlight matches
      const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, null);
      const textNodes: Text[] = [];
      let node;
      while ((node = walker.nextNode())) {
        if (node.textContent?.toLowerCase().includes(query.toLowerCase())) {
          textNodes.push(node as Text);
        }
      }

      let count = 0;
      textNodes.forEach(textNode => {
        const text = textNode.textContent || '';
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        const parts = text.split(regex);
        if (parts.length > 1) {
          const fragment = doc.createDocumentFragment();
          parts.forEach(part => {
            if (part.toLowerCase() === query.toLowerCase()) {
              const mark = doc.createElement('mark');
              mark.className = 'search-highlight';
              mark.dataset.index = String(count);
              mark.style.cssText = 'background: #ffeb3b; padding: 1px 2px; border-radius: 2px;';
              mark.textContent = part;
              fragment.appendChild(mark);
              count++;
            } else {
              fragment.appendChild(doc.createTextNode(part));
            }
          });
          textNode.parentNode?.replaceChild(fragment, textNode);
        }
      });

      setResultCount(count);

      const targetIndex = jumpToIndex ?? 0;
      setCurrentIndex(count > 0 ? targetIndex : 0);

      // Highlight current and scroll
      doc.querySelectorAll('mark.search-highlight').forEach((mark, idx) => {
        (mark as HTMLElement).style.background = idx === targetIndex ? '#ff9800' : '#ffeb3b';
      });

      const currentMatch = doc.querySelector(`mark.search-highlight[data-index="${targetIndex}"]`);
      currentMatch?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (e) {
      console.error('Search failed:', e);
    }
  }, []);

  const navigate = useCallback((direction: 'next' | 'prev', iframe: HTMLIFrameElement | null) => {
    if (!iframe || resultCount === 0) return;

    const newIndex = direction === 'next'
      ? (currentIndex + 1) % resultCount
      : (currentIndex - 1 + resultCount) % resultCount;

    setCurrentIndex(newIndex);

    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (!doc) return;

      doc.querySelectorAll('mark.search-highlight').forEach((mark, idx) => {
        (mark as HTMLElement).style.background = idx === newIndex ? '#ff9800' : '#ffeb3b';
      });

      const currentMatch = doc.querySelector(`mark.search-highlight[data-index="${newIndex}"]`);
      currentMatch?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (e) {
      console.error('Navigate search failed:', e);
    }
  }, [currentIndex, resultCount]);

  const reset = () => {
    setSearchQuery('');
    setResultCount(0);
    setCurrentIndex(0);
  };

  return {
    searchQuery,
    setSearchQuery,
    resultCount,
    currentIndex,
    iframeRef,
    search,
    navigate,
    reset,
  };
}

/**
 * Hook for institution search functionality - mirrors useTickerSearch
 */
export function useInstitutionSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<InstitutionResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedInstitution, setSelectedInstitution] = useState<InstitutionResult | null>(null);

  const searchInstitutions = useCallback(
    debounce(async (query: string) => {
      if (!query || query.length < 1) {
        setSearchResults([]);
        setShowDropdown(false);
        return;
      }
      setIsSearching(true);
      try {
        const response = await fetch(`/api/institution-search?q=${encodeURIComponent(query)}`);
        if (response.ok) {
          const data = await response.json();
          setSearchResults(data || []);
          setShowDropdown(true);
        }
      } catch (err) {
        console.error('Institution search error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 200),
    []
  );

  useEffect(() => {
    if (!selectedInstitution) searchInstitutions(searchQuery);
  }, [searchQuery, searchInstitutions, selectedInstitution]);

  const selectInstitution = (inst: InstitutionResult) => {
    setSelectedInstitution(inst);
    setSearchQuery('');
    setShowDropdown(false);
  };

  const clearInstitution = () => {
    setSelectedInstitution(null);
    setSearchQuery('');
  };

  return {
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearching,
    showDropdown,
    setShowDropdown,
    selectedInstitution,
    selectInstitution,
    clearInstitution,
  };
}

/**
 * Hook for fetching 13F filings for a specific institution
 */
export function useInstitutionFilings() {
  const [filings, setFilings] = useState<InstitutionFiling[]>([]);
  const [selectedFiling, setSelectedFiling] = useState<InstitutionFiling | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchFilings = useCallback(async (cik: string) => {
    setIsLoading(true);
    setSelectedFiling(null);
    try {
      const response = await fetch(`/api/filings/institutions/filings?cik=${cik}&limit=50`);
      if (!response.ok) throw new Error('Failed to fetch institution filings');
      const data = await response.json();
      setFilings(data.filings || []);
    } catch (error) {
      console.error('Institution filings fetch failed:', error);
      setFilings([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const selectFiling = (filing: InstitutionFiling) => {
    setSelectedFiling(filing);
  };

  const clearFilings = () => {
    setFilings([]);
    setSelectedFiling(null);
  };

  return {
    filings,
    selectedFiling,
    isLoading,
    fetchFilings,
    selectFiling,
    clearFilings,
  };
}

/**
 * Hook for fetching 13F holdings for a specific filing
 */
export function useHoldings() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [secLink, setSecLink] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const fetchHoldings = useCallback(async (cik: string, year: number, quarter: number) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/filings/institutions/holdings?cik=${cik}&year=${year}&quarter=${quarter}&limit=100`);
      if (!response.ok) throw new Error('Failed to fetch holdings');
      const data = await response.json();
      setHoldings(data.holdings || []);
      setTotalValue(data.totalValue || 0);
      setSecLink(data.secLink || '');
    } catch (error) {
      console.error('Holdings fetch failed:', error);
      setHoldings([]);
      setTotalValue(0);
      setSecLink('');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearHoldings = () => {
    setHoldings([]);
    setTotalValue(0);
    setSecLink('');
  };

  return {
    holdings,
    totalValue,
    secLink,
    isLoading,
    fetchHoldings,
    clearHoldings,
  };
}
