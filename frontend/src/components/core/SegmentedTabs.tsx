import React from 'react';
import clsx from 'clsx';

export interface TabItem {
  id: string;
  label: React.ReactNode;
  badge?: React.ReactNode;
}

interface SegmentedTabsProps {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
}

const SegmentedTabs: React.FC<SegmentedTabsProps> = ({ items, activeId, onChange }) => {
  return (
    <div role="tablist" aria-label="Content tabs" className="inline-flex items-center gap-1 p-0.5 rounded-md" style={{ boxShadow: '0 0 0 1px var(--border) inset', background: 'color-mix(in oklab, var(--bg-surface), white 1%)' }}>
      {items.map((it) => {
        const active = it.id === activeId;
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={active}
            className={clsx('px-3 py-1.5 text-sm font-medium rounded flex items-center gap-2 focus-visible:outline-none', active && 'tab-active')}
            onClick={() => onChange(it.id)}
            style={{
              color: active ? 'var(--text-primary)' : 'var(--text-muted)',
              background: active ? 'color-mix(in oklab, var(--bg-subtle), white 6%)' : 'transparent',
            }}
          >
            <span>{it.label}</span>
            {it.badge}
          </button>
        );
      })}
    </div>
  );
};

export default SegmentedTabs;
