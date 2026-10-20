import { Search, X } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';

interface SearchBarProps {
  placeholder?: string;
  onSearch: (query: string) => void;
  className?: string;
  autoFocus?: boolean;
}

export default function SearchBar({
  placeholder = 'Search...',
  onSearch,
  className = '',
  autoFocus = false,
}: SearchBarProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query) {
        onSearch(query);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, onSearch]);

  const handleClear = () => {
    setQuery('');
    onSearch('');
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleClear();
    }
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-muted)' }} />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className="input w-full pl-10 pr-10"
        />
        {query && (
          <button
            onClick={handleClear}
            className="btn-ghost absolute right-3 top-1/2 -translate-y-1/2 px-2 py-1"
            aria-label="Clear search"
          >
            <X className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
          </button>
        )}
      </div>
    </div>
  );
}

// Global search modal component
interface GlobalSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GlobalSearch({ isOpen, onClose }: GlobalSearchProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);

  if (!isOpen) return null;

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    // Mock search results - replace with actual search logic
    if (query) {
      setSearchResults([
        { type: 'chat', title: 'Portfolio Analysis Discussion', date: '2 hours ago' },
        { type: 'portfolio', title: 'Tech Growth Portfolio', value: '$125,000' },
        { type: 'workflow', title: 'Daily Risk Analysis', status: 'active' },
      ]);
    } else {
      setSearchResults([]);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20" style={{ background: 'var(--overlay-backdrop)' }}>
      <div className="card w-full max-w-2xl" style={{ background: 'var(--bg-base)' }}>
        <div className="p-4" style={{ borderBottom: '1px solid var(--sentry-gray-200)' }}>
          <SearchBar
            placeholder="Search chats, portfolios, workflows..."
            onSearch={handleSearch}
            autoFocus
          />
        </div>

        {searchResults.length > 0 && (
          <div className="max-h-96 overflow-y-auto">
            {searchResults.map((result, index) => (
              <button
                key={index}
                className="w-full px-4 py-3 text-left border-b last:border-0"
                style={{ borderColor: 'var(--sentry-gray-200)' }}
                onClick={() => {
                  // Navigate to result
                  onClose();
                }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{result.title}</p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{result.type}</p>
                  </div>
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{result.date || result.value || result.status}</p>
                </div>
              </button>
            ))}
          </div>
        )}

        {searchQuery && searchResults.length === 0 && (
          <div className="p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
            No results found for "{searchQuery}"
          </div>
        )}

        <div className="p-3 flex items-center justify-between text-xs" style={{ color: 'var(--text-muted)', borderTop: '1px solid var(--sentry-gray-200)' }}>
          <span>Press ESC to close</span>
          <span>↑↓ to navigate • Enter to select</span>
        </div>
      </div>
    </div>
  );
}
