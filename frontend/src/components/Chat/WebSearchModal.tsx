/**
 * WebSearchModal - Professional web research interface
 */

import React, { useState } from 'react';
import toast from 'react-hot-toast';

interface WebSearchResult {
  id: number;
  title: string;
  url: string;
  snippet: string;
  domain: string;
  selected?: boolean;
}

interface WebSearchModalProps {
  sessionId: string;
  onClose: () => void;
  onAddSources: (sources: WebSearchResult[]) => Promise<void>;
}

const WebSearchModal: React.FC<WebSearchModalProps> = ({ sessionId, onClose, onAddSources }) => {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'web' | 'fast'>('web');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<WebSearchResult[]>([]);
  const [content, setContent] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const [isAdding, setIsAdding] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    setHasSearched(true);
    try {
      const response = await fetch('/api/v6/studio/web-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sessionId, mode }),
      });
      
      if (!response.ok) throw new Error('Search failed');
      
      const data = await response.json();
      
      if (data.error) {
        toast.error(data.content || 'Search failed');
        return;
      }
      
      const resultsWithSelection = (data.sources || []).map((src: WebSearchResult) => ({
        ...src,
        selected: false,
      }));
      
      setResults(resultsWithSelection);
      setContent(data.content || '');
    } catch (error) {
      console.error('Web search failed:', error);
      toast.error('Web search failed');
    } finally {
      setIsSearching(false);
    }
  };

  const toggleResult = (id: number) => {
    setResults(prev => prev.map(r => r.id === id ? { ...r, selected: !r.selected } : r));
  };

  const toggleAll = () => {
    const allSelected = results.every(r => r.selected);
    setResults(prev => prev.map(r => ({ ...r, selected: !allSelected })));
  };

  const selectedCount = results.filter(r => r.selected).length;

  const handleAddSelected = async () => {
    const selected = results.filter(r => r.selected);
    if (selected.length === 0) return;
    
    setIsAdding(true);
    try {
      await onAddSources(selected);
      onClose();
    } catch (error) {
      toast.error('Failed to add sources');
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
      <div 
        className="bg-white w-full max-w-[900px] h-[85vh] flex flex-col"
        style={{ boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}
      >
        {/* Header */}
        <div 
          className="h-10 flex items-center justify-between px-4 border-b border-gray-200"
          style={{ backgroundColor: '#f8f8f8' }}
        >
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-gray-800">Web Research</span>
            <span className="text-[11px] text-gray-400">|</span>
            <span className="text-[11px] text-gray-400">External Sources</span>
          </div>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-gray-600"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Search Section */}
        <div className="px-4 py-3 border-b border-gray-200" style={{ backgroundColor: '#fafafa' }}>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search query..."
              className="flex-1 h-9 px-3 text-[13px] text-gray-900 bg-white border border-gray-300 focus:outline-none focus:border-gray-400"
              style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}
              autoFocus
            />
            <button
              onClick={handleSearch}
              disabled={isSearching || !query.trim()}
              className="h-9 px-4 text-[12px] font-medium text-white disabled:opacity-40"
              style={{ backgroundColor: '#1a1a1a' }}
            >
              {isSearching ? 'SEARCHING...' : 'SEARCH'}
            </button>
          </div>
          
          {/* Mode */}
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[10px] text-gray-500 uppercase tracking-wide">Mode</span>
            <div className="flex">
              <button
                onClick={() => setMode('web')}
                className="h-6 px-3 text-[11px] border border-r-0 border-gray-300"
                style={{ 
                  backgroundColor: mode === 'web' ? '#1a1a1a' : '#fff',
                  color: mode === 'web' ? '#fff' : '#666'
                }}
              >
                Full
              </button>
              <button
                onClick={() => setMode('fast')}
                className="h-6 px-3 text-[11px] border border-gray-300"
                style={{ 
                  backgroundColor: mode === 'fast' ? '#1a1a1a' : '#fff',
                  color: mode === 'fast' ? '#fff' : '#666'
                }}
              >
                Quick
              </button>
            </div>
          </div>
        </div>

        {/* Results Area */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {isSearching ? (
            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="w-5 h-5 border border-gray-300 border-t-gray-700 rounded-full animate-spin" />
              <p className="mt-3 text-[12px] text-gray-500">Searching...</p>
            </div>
          ) : results.length > 0 ? (
            <>
              {/* Results Header */}
              <div 
                className="h-8 flex items-center justify-between px-4 border-b border-gray-200"
                style={{ backgroundColor: '#f5f5f5' }}
              >
                <button
                  onClick={toggleAll}
                  className="flex items-center gap-2 text-[11px] text-gray-600 hover:text-gray-900"
                >
                  <div 
                    className="w-3 h-3 border flex items-center justify-center"
                    style={{ 
                      backgroundColor: results.every(r => r.selected) ? '#1a1a1a' : '#fff',
                      borderColor: results.every(r => r.selected) ? '#1a1a1a' : '#999'
                    }}
                  >
                    {results.every(r => r.selected) && (
                      <svg width="8" height="8" viewBox="0 0 12 12" fill="none">
                        <path d="M2 6l3 3 5-6" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                  </div>
                  SELECT ALL
                </button>
                <span className="text-[11px] text-gray-500">
                  {selectedCount} of {results.length} selected
                </span>
              </div>

              {/* Results Table */}
              <div className="flex-1 overflow-y-auto">
                <table className="w-full">
                  <tbody>
                    {results.map((result, idx) => (
                      <tr
                        key={result.id}
                        onClick={() => toggleResult(result.id)}
                        className="border-b border-gray-100 cursor-pointer hover:bg-gray-50"
                        style={{ backgroundColor: result.selected ? '#f9f9f9' : 'transparent' }}
                      >
                        <td className="w-10 px-4 py-3 align-top">
                          <div 
                            className="w-3 h-3 border flex items-center justify-center mt-0.5"
                            style={{ 
                              backgroundColor: result.selected ? '#1a1a1a' : '#fff',
                              borderColor: result.selected ? '#1a1a1a' : '#999'
                            }}
                          >
                            {result.selected && (
                              <svg width="8" height="8" viewBox="0 0 12 12" fill="none">
                                <path d="M2 6l3 3 5-6" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                          </div>
                        </td>
                        <td className="w-8 py-3 align-top">
                          <span className="text-[11px] text-gray-400 tabular-nums">{String(idx + 1).padStart(2, '0')}</span>
                        </td>
                        <td className="py-3 pr-4">
                          <div>
                            <a
                              href={result.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-[13px] text-gray-900 hover:underline font-medium leading-tight"
                            >
                              {result.title}
                            </a>
                            <div className="text-[11px] text-gray-400 mt-0.5">{result.domain}</div>
                            {result.snippet && (
                              <p className="text-[12px] text-gray-500 mt-1.5 line-clamp-2 leading-relaxed">{result.snippet}</p>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : hasSearched ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
              <p className="text-[13px] text-gray-600">No results found</p>
              <p className="text-[11px] text-gray-400 mt-1">Try: "AAPL earnings" or "Fed interest rate"</p>
              {content && (
                <div className="mt-4 p-3 bg-gray-50 border border-gray-200 text-left max-w-md w-full">
                  <p className="text-[10px] text-gray-500 uppercase mb-1">Summary</p>
                  <p className="text-[12px] text-gray-600 line-clamp-3">{content}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <p className="text-[13px] text-gray-600">Enter a search query</p>
              <p className="text-[11px] text-gray-400 mt-1">Find articles, news, and research</p>
            </div>
          )}
        </div>

        {/* Footer */}
        {results.length > 0 && (
          <div 
            className="h-12 flex items-center justify-end gap-2 px-4 border-t border-gray-200"
            style={{ backgroundColor: '#fafafa' }}
          >
            <button
              onClick={onClose}
              className="h-8 px-4 text-[12px] text-gray-600 border border-gray-300 hover:border-gray-400"
            >
              Cancel
            </button>
            <button
              onClick={handleAddSelected}
              disabled={selectedCount === 0 || isAdding}
              className="h-8 px-4 text-[12px] font-medium text-white disabled:opacity-40"
              style={{ backgroundColor: '#1a1a1a' }}
            >
              {isAdding ? 'Adding...' : `Add${selectedCount > 0 ? ` (${selectedCount})` : ''}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default WebSearchModal;
