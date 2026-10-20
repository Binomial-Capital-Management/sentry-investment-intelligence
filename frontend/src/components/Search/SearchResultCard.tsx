import React from 'react';
import type { Source } from '@/types';

export interface SearchResult extends Omit<Source, 'id'> {
  id?: number;
  source?: string;
  score?: number | null;
  published_date?: string | null;
  metadata?: Record<string, unknown>;
}

interface SearchResultCardProps {
  result: SearchResult;
  index: number;
}

const getDomain = (url: string) => {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return '';
  }
};

const SearchResultCard: React.FC<SearchResultCardProps> = ({ result, index }) => {
  const domain = getDomain(result.url);
  const favicon = domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=64` : '';
  const provider = result.source || 'web';
  const scorePct = typeof result.score === 'number' ? Math.round(result.score * 100) : null;

  return (
    <div className="p-3 rounded-lg transition-colors" style={{ boxShadow: '0 0 0 1px var(--border) inset', background: 'var(--bg-surface)' }}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-10 h-10 rounded-md overflow-hidden" style={{ boxShadow: '0 0 0 1px var(--border) inset' }}>
          {favicon ? <img src={favicon} alt={domain} className="w-full h-full object-cover" /> : <div className="w-full h-full bg-gray-100" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="inline-flex items-center gap-1">
              <span className="px-1.5 py-0.5 rounded-sm" style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}>{index}</span>
              <span>{domain}</span>
            </span>
            <span>• {provider}</span>
            {scorePct !== null && <span>• relevance {scorePct}%</span>}
          </div>
          <a href={result.url} target="_blank" rel="noreferrer" className="block mt-1 truncate" style={{ color: 'var(--accent)', fontWeight: 'var(--fw-medium)' }}>
            {result.title || domain || result.url}
          </a>
          {result.snippet && (
            <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              {result.snippet}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchResultCard;
