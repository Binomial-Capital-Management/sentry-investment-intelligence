import React from 'react';

interface CommandFiltersProps {
  filters: string[];
  active?: string[];
  onToggle?: (filter: string) => void;
}

const CommandFilters: React.FC<CommandFiltersProps> = ({ filters, active = [], onToggle }) => {
  return (
    <div className="hidden md:flex items-center gap-2">
      {filters.map((f) => {
        const isActive = active.includes(f);
        return (
          <button
            key={f}
            className="px-2 py-1 text-xs rounded-full"
            style={{ boxShadow: '0 0 0 1px var(--border) inset', color: isActive ? 'var(--accent)' : 'var(--text-secondary)' }}
            aria-pressed={isActive}
            onClick={() => onToggle?.(f)}
          >
            {f}
          </button>
        );
      })}
    </div>
  );
};

export default CommandFilters;
