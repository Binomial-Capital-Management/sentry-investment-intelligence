import React, { useEffect, useRef, useState } from 'react';
import SearchResultCard, { type SearchResult } from './SearchResultCard';

interface Props {
  query: string;
  isStreaming?: boolean;
}

interface SSEHandlers {
  close: () => void;
}

const SearchResultsPanel: React.FC<Props> = ({ query }) => {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [status, setStatus] = useState<string>('');
  const [started, setStarted] = useState<boolean>(false);
  // Track completion via setter only to avoid unused variable warning
  const [, setDone] = useState<boolean>(false);
  const sseRef = useRef<SSEHandlers | null>(null);

  useEffect(() => {
    if (!query) return;
    setResults([]);
    setStatus('Starting search...');
    setStarted(false);
    setDone(false);

    const params = new URLSearchParams({ query, max_results: '10' });
    const searchStreamUrl = (import.meta as any).env?.VITE_SEARCH_STREAM_URL as string | undefined;
    if (!searchStreamUrl) {
      console.warn('Search streaming disabled: set VITE_SEARCH_STREAM_URL to enable');
      setStatus('Search streaming disabled');
      return;
    }
    const es = new EventSource(`${searchStreamUrl}?${params.toString()}`);

    const onMessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.query && !started) setStarted(true);
      } catch (error) {
        console.error('Failed to parse message event:', error);
      }
    };

    const onStatus = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        if (data && data.message) setStatus(data.message);
      } catch (error) {
        console.error('Failed to parse status event:', error);
      }
    };

    const onResult = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as SearchResult;
        setResults((prev) => [...prev, data]);
      } catch (error) {
        console.error('Failed to parse result event:', error);
      }
    };

    const onComplete = () => {
      setDone(true);
      setStatus('Done');
      es.close();
    };

    const onError = () => {
      setStatus('Error during search');
      es.close();
    };

    es.onmessage = onMessage;
    es.onerror = onError;
    es.addEventListener('status', onStatus as any);
    es.addEventListener('result', onResult as any);
    es.addEventListener('complete', onComplete as any);

    sseRef.current = { close: () => es.close() };

    return () => {
      es.close();
    };
  }, [query]);

  return (
    <div className="space-y-3">
      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
        {status || (started ? 'Working...' : 'Idle')}
      </div>
      {results.length === 0 && (
        <div className="skeleton-card p-4" style={{ minHeight: 120 }} />
      )}
      {results.map((r, idx) => (
        <SearchResultCard key={`${r.url}-${idx}`} result={r} index={idx + 1} />
      ))}
    </div>
  );
};

export default SearchResultsPanel;
