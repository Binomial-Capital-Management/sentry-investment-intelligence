import { useEffect, useRef, useState } from 'react';
import CommandInput from '@components/navigation/CommandBar/CommandInput';
import CommandFilters from '@components/navigation/CommandBar/CommandFilters';
import CommandActions from '@components/navigation/CommandBar/CommandActions';
import { useUIStore } from '@stores/uiStore';
import { useChat } from '@/hooks/useChat';

const CommandBar = () => {
  const [query, setQuery] = useState('');
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const filters = ['market', 'portfolio', 'risk', 'optimize', 'macro'];
  const { sendMessage } = useChat();
  const setActiveModal = useUIStore((s) => s.setActiveModal);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const toggleFilter = (f: string) => {
    setActiveFilters((prev) => (prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]));
  };

  const submit = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    // Prepend filters as tags to preserve intent in a simple, audit-friendly way
    const tagPrefix = activeFilters.length ? `[${activeFilters.join(', ')}] ` : '';
    await sendMessage(tagPrefix + trimmed, true);
    setQuery('');
  };

  // Keyboard helpers: '/' to focus, Enter to submit
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isTypingInInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA');
      if (e.key === '/' && !isTypingInInput) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Enter' && (target === inputRef.current)) {
        e.preventDefault();
        submit();
      }
      if (e.key === '#' && target === inputRef.current) {
        // Insert tag marker if desired; keep simple for now
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [submit]);

  return (
    <div className="w-full" style={{ position: 'sticky', top: 0, zIndex: 30, background: 'linear-gradient(180deg, rgba(12,17,23,0.85), rgba(12,17,23,0.65) 70%, rgba(12,17,23,0))' }}>
      <div className="px-6 pb-3 pt-4">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ boxShadow: '0 0 0 1px var(--border) inset', background: 'color-mix(in oklab, var(--bg-surface), white 2%)' }}>
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ color: 'var(--text-muted)' }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <div className="flex-1">
              <CommandInput value={query} onChange={setQuery} placeholder="Ask Sentry (/, #, @ for power commands)" />
            </div>
            <CommandFilters filters={filters} active={activeFilters} onToggle={toggleFilter} />
            <CommandActions onHistory={() => setActiveModal('history')} onBookmarks={() => setActiveModal('bookmarks')} onSettings={() => setActiveModal('settings')} />
            <kbd className="hidden sm:inline-flex items-center px-2 py-0.5 text-[10px] rounded" style={{ boxShadow: '0 0 0 1px var(--border) inset', color: 'var(--text-secondary)' }}>Enter</kbd>
          </div>
          <div className="mt-2 h-0.5 rounded overflow-hidden" aria-hidden="true">
            <div className="scan-bar" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default CommandBar;
