/**
 * TickerSearch Component
 *
 * Search-as-you-type ticker autocomplete using pre-fetched ticker universe.
 * Displays dropdown with matching tickers, names, and exchanges.
 */

import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { useTickerSearch } from '@/hooks/useTickerSearch';

interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

interface TickerSearchProps {
  onSelect: (ticker: TickerSearchResult) => void;
  placeholder?: string;
  className?: string;
}

export const TickerSearch: React.FC<TickerSearchProps> = ({
  onSelect,
  placeholder = 'Search tickers (e.g., AAPL, MSFT)...',
  className = '',
}) => {
  const [query, setQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  const { results, isLoading, error } = useTickerSearch(query);

  const handleSelect = (ticker: TickerSearchResult) => {
    onSelect(ticker);
    setQuery('');
    setShowDropdown(false);
  };

  return (
    <div className={`relative ${className}`}>
      {/* Search Input */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value.toUpperCase());
            setShowDropdown(true);
          }}
          placeholder={placeholder}
          style={{
            width: '100%',
            padding: '8px 12px 8px 36px',
            fontSize: '14px',
            border: '1px solid #d1d5db',
            borderRadius: '4px',
            background: '#FFFFFF',
            color: '#323130',
            outline: 'none',
            transition: 'border-color 0.2s',
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = '#0066CC';
            results.length > 0 && setShowDropdown(true);
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = '#d1d5db';
            setTimeout(() => setShowDropdown(false), 200);
          }}
        />
        <Search
          size={16}
          style={{
            position: 'absolute',
            left: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: '#605E5C',
          }}
        />

        {/* Loading Spinner */}
        {isLoading && (
          <div style={{
            position: 'absolute',
            right: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
          }}>
            <div style={{
              width: '16px',
              height: '16px',
              border: '2px solid #0066CC',
              borderTopColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 0.6s linear infinite',
            }}></div>
          </div>
        )}
      </div>

      {/* Dropdown Results */}
      {showDropdown && results.length > 0 && (
        <div style={{
          position: 'absolute',
          zIndex: 9999,
          minWidth: '320px',
          width: 'max-content',
          maxWidth: '450px',
          marginTop: '4px',
          background: '#FFFFFF',
          border: '1px solid #E1DFDD',
          borderRadius: '4px',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          maxHeight: '256px',
          overflowY: 'auto',
        }}>
          {results.map((ticker) => (
            <button
              key={ticker.symbol}
              onClick={() => handleSelect(ticker)}
              style={{
                width: '100%',
                padding: '12px 16px',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                transition: 'background-color 0.15s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#F3F2F1'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ flex: 1 }}>
                <div style={{
                  fontWeight: '600',
                  color: '#323130',
                  fontSize: '14px',
                  marginBottom: '2px',
                }}>
                  {ticker.symbol}
                </div>
                <div style={{
                  fontSize: '12px',
                  color: '#605E5C',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {ticker.name}
                </div>
              </div>
              <div style={{
                marginLeft: '16px',
                padding: '4px 8px',
                background: '#F3F2F1',
                borderRadius: '4px',
                fontSize: '11px',
                color: '#605E5C',
                fontWeight: '500',
              }}>
                {ticker.exchange}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div style={{
          position: 'absolute',
          zIndex: 9999,
          width: '100%',
          marginTop: '4px',
          padding: '12px',
          background: '#FEF2F2',
          border: '1px solid #FCA5A5',
          borderRadius: '4px',
          color: '#DC2626',
          fontSize: '13px',
        }}>
          {error}
        </div>
      )}

      {/* No Results */}
      {showDropdown && !isLoading && query.length > 0 && results.length === 0 && !error && (
        <div style={{
          position: 'absolute',
          zIndex: 9999,
          width: '100%',
          marginTop: '4px',
          padding: '12px',
          background: '#FFFFFF',
          border: '1px solid #E1DFDD',
          borderRadius: '4px',
          color: '#605E5C',
          fontSize: '13px',
          textAlign: 'center',
        }}>
          No tickers found for "{query}"
        </div>
      )}
    </div>
  );
};
