import React, { useState, useEffect, useCallback } from 'react';
import { useUIStore, FilingPreview } from '@/stores/uiStore';
import { X, ExternalLink, Loader2, Search, ChevronUp, ChevronDown, Quote } from 'lucide-react';
import toast from 'react-hot-toast';

interface FilingPreviewPanelProps {
  onClose: () => void;
}

const FilingPreviewPanel: React.FC<FilingPreviewPanelProps> = ({ onClose }) => {
  const filingPreviews = useUIStore((s) => s.filingPreviews);
  const activeFilingPreviewId = useUIStore((s) => s.activeFilingPreviewId);
  const closeFilingPreview = useUIStore((s) => s.closeFilingPreview);
  const setActiveFilingPreview = useUIStore((s) => s.setActiveFilingPreview);
  const addFilingCitation = useUIStore((s) => s.addFilingCitation);
  
  // Content cache per filing ID
  const [contentCache, setContentCache] = useState<Record<string, string>>({});
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [errorIds, setErrorIds] = useState<Record<string, string>>({});
  
  // Search state (per active tab)
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<number>(0);
  const [currentMatch, setCurrentMatch] = useState(0);
  const [matchElements, setMatchElements] = useState<Element[]>([]);
  const [selectedText, setSelectedText] = useState('');
  const [selectionPos, setSelectionPos] = useState<{ x: number; y: number } | null>(null);
  const iframeRef = React.useRef<HTMLIFrameElement>(null);
  const searchInputRef = React.useRef<HTMLInputElement>(null);
  const contentContainerRef = React.useRef<HTMLDivElement>(null);

  // Get active filing
  const activeFiling = filingPreviews.find(f => f.id === activeFilingPreviewId);
  const activeContent = activeFiling ? contentCache[activeFiling.id] : '';
  const isActiveLoading = activeFiling ? loadingIds.has(activeFiling.id) : false;
  const activeError = activeFiling ? errorIds[activeFiling.id] : null;

  // Fetch content for a filing
  const fetchContent = useCallback(async (filing: FilingPreview) => {
    // Skip if already cached or loading
    if (contentCache[filing.id] || loadingIds.has(filing.id)) return;
    
    // Use provided content if available
    if (filing.content) {
      setContentCache(prev => ({ ...prev, [filing.id]: filing.content! }));
      return;
    }
    
    // Fetch from API
    setLoadingIds(prev => new Set(prev).add(filing.id));
    try {
      const response = await fetch(`/api/filings/preview?link=${encodeURIComponent(filing.url)}`);
      if (!response.ok) throw new Error('Failed to load filing');
      const html = await response.text();
      setContentCache(prev => ({ ...prev, [filing.id]: html }));
      setErrorIds(prev => {
        const next = { ...prev };
        delete next[filing.id];
        return next;
      });
    } catch (err) {
      setErrorIds(prev => ({ ...prev, [filing.id]: err instanceof Error ? err.message : 'Failed to load' }));
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(filing.id);
        return next;
      });
    }
  }, [contentCache, loadingIds]);

  // Fetch content when active filing changes
  useEffect(() => {
    if (activeFiling) {
      fetchContent(activeFiling);
    }
    // Reset search when switching tabs
    setSearchOpen(false);
    setSearchQuery('');
    setSearchResults(0);
    setCurrentMatch(0);
    setMatchElements([]);
  }, [activeFiling?.id]);

  // Inject search highlight styles into iframe
  useEffect(() => {
    if (!activeContent || !iframeRef.current) return;
    
    const iframe = iframeRef.current;
    const onLoad = () => {
      try {
        const iframeDoc = iframe.contentDocument;
        if (iframeDoc) {
          const style = iframeDoc.createElement('style');
          style.textContent = `
            .search-highlight {
              background-color: #fef08a !important;
              color: inherit !important;
            }
            .search-highlight.current {
              background-color: #fb923c !important;
            }
          `;
          iframeDoc.head.appendChild(style);
        }
      } catch (e) {
        console.error('Failed to inject styles:', e);
      }
    };
    
    iframe.addEventListener('load', onLoad);
    return () => iframe.removeEventListener('load', onLoad);
  }, [activeContent]);

  // Track text selection in iframe
  useEffect(() => {
    if (!iframeRef.current) return;
    
    const iframe = iframeRef.current;
    const checkSelection = () => {
      try {
        const iframeDoc = iframe.contentDocument;
        if (iframeDoc) {
          const selection = iframeDoc.getSelection();
          const text = selection?.toString().trim() || '';
          setSelectedText(text);
          
          // Get position for floating button
          if (text && selection && selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            const iframeRect = iframe.getBoundingClientRect();
            const containerRect = contentContainerRef.current?.getBoundingClientRect();
            
            if (containerRect) {
              // Position button above the selection, centered
              setSelectionPos({
                x: Math.min(Math.max(rect.left + rect.width / 2, 40), containerRect.width - 40),
                y: rect.top - 8
              });
            }
          } else {
            setSelectionPos(null);
          }
        }
      } catch (e) {
        // Cross-origin or sandbox issue
      }
    };

    const onLoad = () => {
      const iframeDoc = iframe.contentDocument;
      if (iframeDoc) {
        iframeDoc.addEventListener('mouseup', checkSelection);
        iframeDoc.addEventListener('keyup', checkSelection);
      }
    };

    iframe.addEventListener('load', onLoad);
    // If already loaded
    if (iframe.contentDocument) {
      iframe.contentDocument.addEventListener('mouseup', checkSelection);
      iframe.contentDocument.addEventListener('keyup', checkSelection);
    }

    return () => {
      iframe.removeEventListener('load', onLoad);
      try {
        iframe.contentDocument?.removeEventListener('mouseup', checkSelection);
        iframe.contentDocument?.removeEventListener('keyup', checkSelection);
      } catch (e) {}
    };
  }, [activeContent]);

  // Handle citing selected text
  const handleCite = useCallback(() => {
    if (!selectedText || !activeFiling) return;
    
    const citation = {
      id: `cite-${Date.now()}`,
      text: selectedText.slice(0, 500), // Limit citation length
      filingId: activeFiling.id,
      filingTitle: activeFiling.title,
      formType: activeFiling.formType,
      ticker: activeFiling.ticker,
    };
    
    addFilingCitation(citation);
    toast.success('Added to chat context', { duration: 1500, icon: '📎' });
    setSelectedText('');
    setSelectionPos(null);
    
    // Clear selection in iframe
    try {
      iframeRef.current?.contentDocument?.getSelection()?.removeAllRanges();
    } catch (e) {}
  }, [selectedText, activeFiling, addFilingCitation]);

  // Search within iframe
  const handleSearch = useCallback(() => {
    if (!iframeRef.current || !searchQuery.trim()) {
      setSearchResults(0);
      setCurrentMatch(0);
      setMatchElements([]);
      return;
    }
    
    try {
      const iframeDoc = iframeRef.current.contentDocument;
      if (!iframeDoc || !iframeDoc.body) return;
      
      // Clear previous highlights
      const oldHighlights = iframeDoc.querySelectorAll('.search-highlight');
      oldHighlights.forEach(el => {
        const parent = el.parentNode;
        if (parent) {
          parent.replaceChild(document.createTextNode(el.textContent || ''), el);
          parent.normalize();
        }
      });
      
      if (!searchQuery.trim()) {
        setSearchResults(0);
        setCurrentMatch(0);
        setMatchElements([]);
        return;
      }
      
      const searchRegex = new RegExp(searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      const newMatches: Element[] = [];
      
      const walkAndHighlight = (node: Node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          const text = node.textContent || '';
          if (searchRegex.test(text)) {
            searchRegex.lastIndex = 0;
            const fragment = document.createDocumentFragment();
            let lastIndex = 0;
            let match;
            
            while ((match = searchRegex.exec(text)) !== null) {
              if (match.index > lastIndex) {
                fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
              }
              const span = iframeDoc.createElement('span');
              span.className = 'search-highlight';
              span.textContent = match[0];
              fragment.appendChild(span);
              newMatches.push(span);
              lastIndex = searchRegex.lastIndex;
            }
            if (lastIndex < text.length) {
              fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
            }
            node.parentNode?.replaceChild(fragment, node);
          }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          const tagName = (node as Element).tagName.toLowerCase();
          if (tagName !== 'script' && tagName !== 'style') {
            Array.from(node.childNodes).forEach(walkAndHighlight);
          }
        }
      };
      
      walkAndHighlight(iframeDoc.body);
      setMatchElements(newMatches);
      setSearchResults(newMatches.length);
      
      if (newMatches.length > 0) {
        setCurrentMatch(1);
        newMatches[0].classList.add('current');
        newMatches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        setCurrentMatch(0);
      }
    } catch (e) {
      console.error('Search error:', e);
    }
  }, [searchQuery]);

  // Navigate between matches
  const navigateMatch = useCallback((direction: 'next' | 'prev') => {
    if (searchResults === 0 || matchElements.length === 0) return;
    
    matchElements[currentMatch - 1]?.classList.remove('current');
    
    let newMatch: number;
    if (direction === 'next') {
      newMatch = currentMatch >= searchResults ? 1 : currentMatch + 1;
    } else {
      newMatch = currentMatch <= 1 ? searchResults : currentMatch - 1;
    }
    
    setCurrentMatch(newMatch);
    const element = matchElements[newMatch - 1];
    if (element) {
      element.classList.add('current');
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [currentMatch, searchResults, matchElements]);

  // Toggle search
  const toggleSearch = () => {
    const newState = !searchOpen;
    setSearchOpen(newState);
    if (newState) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery('');
      setSearchResults(0);
      setCurrentMatch(0);
      setMatchElements([]);
    }
  };

  // Format date
  const formatDate = (date: string | undefined) => {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // Get tab label
  const getTabLabel = (filing: FilingPreview) => {
    if (filing.ticker && filing.formType) {
      return `${filing.ticker} ${filing.formType}`;
    }
    return filing.formType || filing.title?.slice(0, 15) || 'Filing';
  };

  if (filingPreviews.length === 0) return null;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Tab bar - Chrome-style */}
      <div className="flex-shrink-0 flex items-end bg-gray-100 pt-1.5 px-1 overflow-x-auto">
        {filingPreviews.map((filing) => (
          <div
            key={filing.id}
            className={`group relative flex items-center gap-1.5 px-3 py-1.5 text-xs cursor-pointer whitespace-nowrap transition-all ${
              filing.id === activeFilingPreviewId
                ? 'bg-white text-gray-900 rounded-t-lg shadow-sm z-10'
                : 'text-gray-500 hover:bg-gray-200/70 rounded-t-lg mr-0.5'
            }`}
            style={{
              minWidth: '80px',
              maxWidth: '160px',
            }}
            onClick={() => setActiveFilingPreview(filing.id)}
          >
            <span className="flex-1 truncate" title={filing.title}>
              {getTabLabel(filing)}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeFilingPreview(filing.id);
              }}
              className={`p-0.5 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-all ${
                filing.id === activeFilingPreviewId ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
              }`}
            >
              <X size={11} />
            </button>
          </div>
        ))}
        {/* Close all button */}
        <button
          onClick={onClose}
          className="ml-auto mb-1 p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded"
          title="Close all"
        >
          <X size={14} />
        </button>
      </div>

      {activeFiling && (
        <>
          {/* Active tab header */}
          <div className="flex-shrink-0 border-b border-gray-200 px-3 py-1.5">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-500 truncate flex-1">
                {activeFiling.filingDate && formatDate(activeFiling.filingDate)}
              </span>
              <button
                onClick={toggleSearch}
                className={`p-1 rounded ${searchOpen ? 'bg-gray-100 text-gray-600' : 'hover:bg-gray-100 text-gray-400 hover:text-gray-600'}`}
                title="Find"
              >
                <Search size={13} />
              </button>
              <a
                href={activeFiling.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600"
                title="Open in SEC EDGAR"
              >
                <ExternalLink size={13} />
              </a>
            </div>
            
            {/* Search bar */}
            {searchOpen && (
              <div className="flex items-center gap-1.5 mt-1.5">
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      if (searchResults > 0 && searchQuery) {
                        navigateMatch('next');
                      } else {
                        handleSearch();
                      }
                    } else if (e.key === 'Escape') {
                      toggleSearch();
                    }
                  }}
                  placeholder="Find..."
                  className="flex-1 px-2 py-1 text-xs bg-gray-50 border border-gray-200 rounded focus:outline-none focus:border-gray-300 focus:bg-white"
                />
                {searchResults > 0 ? (
                  <div className="flex items-center gap-0.5 text-xs text-gray-500">
                    <span className="text-[11px]">{currentMatch}/{searchResults}</span>
                    <button onClick={() => navigateMatch('prev')} className="p-0.5 hover:bg-gray-100 rounded">
                      <ChevronUp size={13} />
                    </button>
                    <button onClick={() => navigateMatch('next')} className="p-0.5 hover:bg-gray-100 rounded">
                      <ChevronDown size={13} />
                    </button>
                  </div>
                ) : searchQuery ? (
                  <span className="text-[11px] text-gray-400">0</span>
                ) : null}
              </div>
            )}
          </div>

          {/* Content */}
          <div ref={contentContainerRef} className="flex-1 overflow-hidden bg-gray-50 relative">
            {isActiveLoading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="animate-spin text-gray-400" size={24} />
              </div>
            ) : activeError ? (
              <div className="flex flex-col items-center justify-center h-full p-6 text-center">
                <p className="text-sm text-gray-500 mb-3">{activeError}</p>
                <a
                  href={activeFiling.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-600 hover:text-gray-800"
                >
                  Open in SEC EDGAR →
                </a>
              </div>
            ) : (
              <>
                <iframe
                  ref={iframeRef}
                  srcDoc={activeContent}
                  sandbox="allow-same-origin"
                  className="w-full h-full border-none bg-white"
                  title="Filing Preview"
                />
                {/* Floating Cite button on text selection */}
                {selectedText && selectionPos && (
                  <button
                    onClick={handleCite}
                    className="absolute z-20 flex items-center gap-1 px-2 py-1 text-xs font-medium text-white bg-gray-800 rounded shadow-lg hover:bg-gray-700 transition-colors"
                    style={{
                      left: `${selectionPos.x}px`,
                      top: `${selectionPos.y}px`,
                      transform: 'translate(-50%, -100%)',
                    }}
                  >
                    <Quote size={11} />
                    Cite
                  </button>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default FilingPreviewPanel;
