/**
 * TickerMention Component
 *
 * Compact @ticker mention autocomplete in chat input.
 * Triggers when user types @ followed by letters.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useTickerSearch } from '@/hooks/useTickerSearch';

interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

export interface MentionedTicker {
  symbol: string;
  name: string;
  exchange: string;
}

interface TickerMentionProps {
  inputText: string;
  cursorPosition: number;
  onSelect: (ticker: MentionedTicker, startIndex: number, endIndex: number) => void;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLElement>;
}

const logoDevToken = (import.meta as any).env?.VITE_LOGODEV_TOKEN;

const getCompanyLogoUrl = (symbol: string) => {
  if (!logoDevToken) {
    return `https://logo.clearbit.com/${symbol.toLowerCase()}.com`;
  }
  return `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${logoDevToken}`;
};

export const TickerMention: React.FC<TickerMentionProps> = ({
  inputText,
  cursorPosition,
  onSelect,
  onClose,
  anchorRef,
}) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const [mentionQuery, setMentionQuery] = useState<{ query: string; startIndex: number } | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Detect @mention pattern at cursor position
  useEffect(() => {
    const textBeforeCursor = inputText.slice(0, cursorPosition);
    const atMatch = textBeforeCursor.match(/@([A-Za-z0-9.]*)$/);

    if (atMatch) {
      const query = atMatch[1];
      const startIndex = textBeforeCursor.lastIndexOf('@');
      setMentionQuery({ query, startIndex });
    } else {
      setMentionQuery(null);
    }
  }, [inputText, cursorPosition]);

  const { results, isLoading } = useTickerSearch(mentionQuery?.query || '', { limit: 10 });

  // Reset active index when results change
  useEffect(() => {
    setActiveIndex(0);
  }, [results]);

  // Handle keyboard navigation with scroll into view
  useEffect(() => {
    if (!mentionQuery) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (results.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        e.stopPropagation();
        setActiveIndex((prev) => {
          const newIndex = (prev + 1) % results.length;
          setTimeout(() => {
            if (dropdownRef.current) {
              const buttons = dropdownRef.current.querySelectorAll('button');
              const activeButton = buttons[newIndex] as HTMLElement;
              activeButton?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
          }, 0);
          return newIndex;
        });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        e.stopPropagation();
        setActiveIndex((prev) => {
          const newIndex = (prev - 1 + results.length) % results.length;
          setTimeout(() => {
            if (dropdownRef.current) {
              const buttons = dropdownRef.current.querySelectorAll('button');
              const activeButton = buttons[newIndex] as HTMLElement;
              activeButton?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
          }, 0);
          return newIndex;
        });
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        if (results.length > 0) {
          e.preventDefault();
          e.stopPropagation();
          handleSelect(results[activeIndex]);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [mentionQuery, results, activeIndex, onClose]);

  const handleSelect = (ticker: TickerSearchResult) => {
    if (!mentionQuery) return;

    const textAfterAt = inputText.slice(mentionQuery.startIndex);
    const wordEndMatch = textAfterAt.match(/^@[A-Za-z0-9.]*/);
    const wordLength = wordEndMatch ? wordEndMatch[0].length : 1;
    const endIndex = mentionQuery.startIndex + wordLength;

    onSelect(
      { symbol: ticker.symbol, name: ticker.name, exchange: ticker.exchange },
      mentionQuery.startIndex,
      endIndex,
    );
    setMentionQuery(null);
  };

  // Show dropdown when there's an @ pattern (even without results yet)
  if (!mentionQuery) {
    return null;
  }

  return (
    <div
      ref={dropdownRef}
      onMouseDown={(e) => e.preventDefault()} // Prevent blur on input
      style={{
        position: 'absolute',
        bottom: '100%',
        left: 0,
        marginBottom: '4px',
        background: '#FFFFFF',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        boxShadow: '0 2px 12px rgba(0, 0, 0, 0.12)',
        maxHeight: '280px',
        overflowY: 'auto',
        overflowX: 'hidden',
        zIndex: 9999,
        minWidth: '260px',
        maxWidth: '340px',
        WebkitOverflowScrolling: 'touch',
      }}
    >
      {/* Loading state */}
      {isLoading && results.length === 0 && (
        <div style={{
          padding: '10px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: '#9ca3af',
          fontSize: '12px',
          flexShrink: 0,
        }}>
          <div style={{
            width: '14px',
            height: '14px',
            border: '2px solid #e5e7eb',
            borderTopColor: '#3b82f6',
            borderRadius: '50%',
            animation: 'spin 0.6s linear infinite',
          }} />
          Searching...
        </div>
      )}

      {/* Results */}
      {results.map((ticker, index) => (
        <button
          key={ticker.symbol}
          onClick={() => handleSelect(ticker)}
          onMouseEnter={() => setActiveIndex(index)}
          style={{
            width: '100%',
            padding: '6px 10px',
            textAlign: 'left',
            background: index === activeIndex ? '#f3f4f6' : 'transparent',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'background-color 0.1s',
            flexShrink: 0,
          }}
        >
          {/* Logo */}
          <div style={{
            width: '22px',
            height: '22px',
            borderRadius: '4px',
            overflow: 'hidden',
            background: '#f9fafb',
            border: '1px solid #e5e7eb',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <img
              src={getCompanyLogoUrl(ticker.symbol)}
              alt=""
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
              }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                target.parentElement!.innerHTML = `<span style="font-size: 11px; font-weight: 600; color: #6b7280;">${ticker.symbol[0]}</span>`;
              }}
            />
          </div>

          {/* Symbol */}
          <span style={{
            fontWeight: 600,
            fontSize: '13px',
            color: '#111827',
            minWidth: '50px',
          }}>
            {ticker.symbol}
          </span>

          {/* Name - truncated */}
          <span style={{
            flex: 1,
            fontSize: '12px',
            color: '#6b7280',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {ticker.name}
          </span>

          {/* Exchange */}
          <span style={{
            fontSize: '10px',
            color: '#9ca3af',
            flexShrink: 0,
          }}>
            {ticker.exchange}
          </span>
        </button>
      ))}

      {/* No results */}
      {!isLoading && results.length === 0 && mentionQuery.query.length > 0 && (
        <div style={{
          padding: '10px 12px',
          color: '#9ca3af',
          fontSize: '12px',
          flexShrink: 0,
        }}>
          No tickers found
        </div>
      )}

      {/* Empty query hint */}
      {!isLoading && results.length === 0 && mentionQuery.query.length === 0 && (
        <div style={{
          padding: '10px 12px',
          color: '#9ca3af',
          fontSize: '12px',
          flexShrink: 0,
        }}>
          Type to search tickers...
        </div>
      )}

      <style>
        {`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  );
};

export default TickerMention;
