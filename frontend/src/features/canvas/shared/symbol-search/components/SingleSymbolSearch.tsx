/**
 * SingleTickerSearch Component
 *
 * Single ticker search with autocomplete dropdown.
 * Used for tools that require a single underlying/ticker input.
 */

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useTickerSearch } from '@/hooks/useTickerSearch';

interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

interface SingleTickerSearchProps {
  value: string;
  onChange: (ticker: string) => void;
  placeholder?: string;
  label?: string;
}

export const SingleSymbolSearch: React.FC<SingleTickerSearchProps> = ({
  value,
  onChange,
  placeholder = 'Search ticker...',
  label = 'Enter Ticker',
}) => {
  const [query, setQuery] = useState(value || '');
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<TickerSearchResult | null>(null);

  const { results, isLoading, error } = useTickerSearch(
    selectedTicker ? '' : query,
    { limit: 8 },
  );

  // Keep query in sync with external value
  useEffect(() => {
    if (value && value !== query) {
      setQuery(value);
    }
  }, [value]);

  const handleSelect = (ticker: TickerSearchResult) => {
    setSelectedTicker(ticker);
    setQuery(ticker.symbol);
    onChange(ticker.symbol);
    setShowDropdown(false);
  };

  const handleClear = () => {
    setSelectedTicker(null);
    setQuery('');
    onChange('');
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value.toUpperCase();
    setQuery(newValue);
    setSelectedTicker(null);
    onChange(newValue);
    setShowDropdown(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && query.length >= 1 && query.length <= 5) {
      onChange(query);
      setShowDropdown(false);
      e.preventDefault();
    }
  };

  return (
    <div className="space-y-2">
      {/* Selected Ticker Display */}
      {selectedTicker && (
        <div className="flex items-center gap-2 p-3 bg-gray-50 border border-gray-200">
          <div className="flex-1">
            <div className="font-semibold text-sm font-mono">{selectedTicker.symbol}</div>
            <div className="text-xs text-gray-500 truncate">{selectedTicker.name}</div>
          </div>
          <button
            onClick={handleClear}
            className="p-1 hover:bg-gray-200 rounded transition-colors"
          >
            <X size={16} className="text-gray-500" />
          </button>
        </div>
      )}

      {/* Search Input */}
      {!selectedTicker && (
        <div className="relative">
          <div className="relative">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
              style={{ color: 'hsl(60 2.5% 23.3% / 35%)' }}
              fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              className="w-full pl-8 pr-8 py-1.5 text-xs rounded-lg focus:outline-none focus:ring-0"
              style={{ border: '0.5px solid hsl(30 3.3% 11.8% / 20%)' }}
              onFocus={() => results.length > 0 && setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              autoFocus
            />
            {isLoading && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <div className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>

          {/* Dropdown Results */}
          {showDropdown && results.length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 shadow-lg max-h-80 overflow-auto">
              {results.map((ticker) => (
                <button
                  key={ticker.symbol}
                  onClick={() => handleSelect(ticker)}
                  className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                >
                  <div>
                    <div className="font-semibold text-sm font-mono">{ticker.symbol}</div>
                    <div className="text-xs text-gray-500 truncate max-w-[280px]">
                      {ticker.name}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1">
                    {ticker.exchange}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* No Results */}
          {showDropdown && !isLoading && query.length > 0 && results.length === 0 && !error && (
            <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 shadow-lg px-4 py-3 text-sm text-gray-500 text-center">
              No tickers found for "{query}" — Press Enter to use anyway
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="absolute z-50 w-full mt-1 bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}
        </div>
      )}

      {/* Helper text */}
      <div className="text-xs text-gray-400">
        Search by company name or ticker symbol
      </div>
    </div>
  );
};

// Backwards compatibility alias
export const SingleTickerSearch = SingleSymbolSearch;
