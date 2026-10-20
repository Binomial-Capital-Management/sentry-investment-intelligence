/**
 * MultiTickerSearch Component
 *
 * Multi-select ticker search with autocomplete.
 * Shows selected tickers as removable pills with company logos.
 */

import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useTickerSearch } from '@/hooks/useTickerSearch';

interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

const logoDevToken = (import.meta as any).env?.VITE_LOGODEV_TOKEN;

const getCompanyLogoUrl = (symbol: string) => {
  if (!logoDevToken) {
    return `https://logo.clearbit.com/${symbol.toLowerCase()}.com`;
  }
  return `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${logoDevToken}`;
};

interface MultiTickerSearchProps {
  selectedTickers: string[];
  onChange: (tickers: string[]) => void;
  placeholder?: string;
  minTickers?: number;
  maxTickers?: number;
}

export const MultiSymbolSearch: React.FC<MultiTickerSearchProps> = ({
  selectedTickers,
  onChange,
  placeholder = 'Search tickers...',
  minTickers = 1,
  maxTickers = 20,
}) => {
  const [query, setQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  const { results, isLoading, error } = useTickerSearch(query, {
    excludeSymbols: selectedTickers,
  });

  const handleSelect = (ticker: TickerSearchResult) => {
    if (selectedTickers.length >= maxTickers) return;
    onChange([...selectedTickers, ticker.symbol]);
    setQuery('');
    setShowDropdown(false);
  };

  const handleRemove = (symbol: string) => {
    onChange(selectedTickers.filter((t) => t !== symbol));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && query.length >= 1 && query.length <= 5) {
      const upperQuery = query.toUpperCase();
      if (!selectedTickers.includes(upperQuery) && selectedTickers.length < maxTickers) {
        onChange([...selectedTickers, upperQuery]);
        setQuery('');
        setShowDropdown(false);
      }
      e.preventDefault();
    }
    if (e.key === 'Backspace' && query === '' && selectedTickers.length > 0) {
      onChange(selectedTickers.slice(0, -1));
    }
  };

  return (
    <div className="space-y-3">
      {/* Selected Tickers as Pills with Logos */}
      {selectedTickers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedTickers.map((symbol) => (
            <div
              key={symbol}
              className="inline-flex items-center gap-2 pl-1.5 pr-2 py-1 bg-gray-100 hover:bg-gray-200 rounded-full border border-gray-200 transition-colors group"
            >
              {/* Logo */}
              <div className="w-5 h-5 rounded-full overflow-hidden bg-white border border-gray-200 flex items-center justify-center flex-shrink-0">
                <img
                  src={getCompanyLogoUrl(symbol)}
                  alt=""
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    target.style.display = 'none';
                    if (target.parentElement) {
                      target.parentElement.innerHTML = `<span class="text-[10px] font-semibold text-gray-500">${symbol[0]}</span>`;
                    }
                  }}
                />
              </div>
              {/* Symbol */}
              <span className="text-sm font-semibold text-gray-800">
                {symbol}
              </span>
              {/* Remove Button */}
              <button
                onClick={() => handleRemove(symbol)}
                className="text-gray-400 hover:text-gray-600 transition-colors ml-0.5"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Search Input */}
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
            onChange={(e) => {
              setQuery(e.target.value.toUpperCase());
              setShowDropdown(true);
            }}
            onKeyDown={handleKeyDown}
            placeholder={selectedTickers.length >= maxTickers ? `Max ${maxTickers} tickers` : placeholder}
            disabled={selectedTickers.length >= maxTickers}
            className="w-full pl-8 pr-8 py-1.5 text-xs rounded-lg focus:outline-none focus:ring-0 disabled:bg-gray-100 disabled:cursor-not-allowed"
            style={{ border: '0.5px solid hsl(30 3.3% 11.8% / 20%)' }}
            onFocus={() => results.length > 0 && setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          />
          {isLoading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>

        {/* Dropdown Results */}
        {showDropdown && results.length > 0 && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 shadow-lg max-h-64 overflow-auto rounded-lg">
            {results.map((ticker) => (
              <button
                key={ticker.symbol}
                onClick={() => handleSelect(ticker)}
                className="w-full px-3 py-2.5 text-left hover:bg-gray-50 flex items-center gap-3 border-b border-gray-100 last:border-0 transition-colors"
              >
                {/* Logo */}
                <div className="w-8 h-8 rounded-lg overflow-hidden bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
                  <img
                    src={getCompanyLogoUrl(ticker.symbol)}
                    alt=""
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.style.display = 'none';
                      if (target.parentElement) {
                        target.parentElement.innerHTML = `<span class="text-sm font-semibold text-gray-400">${ticker.symbol[0]}</span>`;
                      }
                    }}
                  />
                </div>
                {/* Ticker Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm text-gray-900">{ticker.symbol}</div>
                  <div className="text-xs text-gray-500 truncate">
                    {ticker.name}
                  </div>
                </div>
                {/* Exchange Badge */}
                <span className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded flex-shrink-0">
                  {ticker.exchange}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* No Results */}
        {showDropdown && !isLoading && query.length > 0 && results.length === 0 && !error && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 shadow-lg px-4 py-3 text-sm text-gray-500 text-center rounded-lg">
            No tickers found for "<span className="font-semibold">{query}</span>" — Press Enter to add
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="absolute z-50 w-full mt-1 bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600 rounded-lg">
            {error}
          </div>
        )}
      </div>

      {/* Helper text */}
      <div className="text-xs text-gray-400">
        {minTickers > 1 && selectedTickers.length < minTickers && (
          <span>Select at least {minTickers} tickers • </span>
        )}
        {selectedTickers.length} / {maxTickers} tickers selected
      </div>
    </div>
  );
};

// Backwards compatibility alias
export const MultiTickerSearch = MultiSymbolSearch;
