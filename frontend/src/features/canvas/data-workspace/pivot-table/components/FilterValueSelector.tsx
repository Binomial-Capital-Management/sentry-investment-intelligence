import { useState, useCallback } from 'react';

const C = {
  text:       'hsl(60 2.5% 23.3%)',
  textMuted:  'hsl(60 2.5% 23.3% / 60%)',
  textFaint:  'hsl(60 2.5% 23.3% / 35%)',
  textGhost:  'hsl(60 2.5% 23.3% / 25%)',
  border:     '0.5px solid hsl(30 3.3% 11.8% / 10%)',
  borderSel:  '0.5px solid hsl(30 3.3% 11.8% / 15%)',
  bgActive:   'hsl(30 3.3% 11.8% / 8%)',
  bgSubtle:   'hsl(30 3.3% 11.8% / 3%)',
  bgHover:    'hsl(30 3.3% 11.8% / 5%)',
} as const;

const FONT_MONO = "'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace";

interface FilterValueSelectorProps {
  filterableFields: string[];
  filterOptions: Record<string, string[]>;
  activeFilters: Record<string, { operator: string; value: any }>;
  loading: boolean;
  onFiltersChange: (filters: Record<string, { operator: string; value: any }>) => void;
}

export function FilterValueSelector({
  filterableFields,
  filterOptions,
  activeFilters,
  loading,
  onFiltersChange,
}: FilterValueSelectorProps) {
  const [expandedField, setExpandedField] = useState<string | null>(null);

  const getSelectedValues = useCallback((field: string): Set<string> => {
    const filter = activeFilters[field];
    if (!filter || filter.operator !== 'in' || !Array.isArray(filter.value)) {
      return new Set(filterOptions[field] || []);
    }
    return new Set(filter.value);
  }, [activeFilters, filterOptions]);

  const toggleValue = useCallback((field: string, val: string, checked: boolean) => {
    const options = filterOptions[field] || [];
    const current = getSelectedValues(field);
    const next = new Set(current);
    if (checked) next.add(val);
    else next.delete(val);

    const allSelected = next.size === options.length;
    const updated = { ...activeFilters };
    if (allSelected) {
      delete updated[field];
    } else {
      updated[field] = { operator: 'in', value: Array.from(next) };
    }
    onFiltersChange(updated);
  }, [filterOptions, activeFilters, getSelectedValues, onFiltersChange]);

  if (filterableFields.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
      {filterableFields.map(field => {
        const options = filterOptions[field];
        const isExpanded = expandedField === field;
        const selected = getSelectedValues(field);
        const isFiltered = activeFilters[field] && activeFilters[field].operator === 'in';
        const count = isFiltered ? selected.size : options?.length;
        const total = options?.length;

        return (
          <div key={field} style={{ border: C.border, borderRadius: '0.5rem', overflow: 'hidden', flexShrink: 0 }}>
            <div
              onClick={() => setExpandedField(isExpanded ? null : field)}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.375rem',
                padding: '0.375rem 0.5rem', backgroundColor: C.bgSubtle,
                cursor: 'pointer', fontSize: '0.625rem', fontWeight: 600, color: C.text,
              }}
            >
              <svg
                style={{ width: 8, height: 8, flexShrink: 0, transition: 'transform 0.15s ease', transform: isExpanded ? 'rotate(90deg)' : 'none' }}
                fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: FONT_MONO }}>
                {field}
              </span>
              {total != null && (
                <span style={{ fontSize: '0.5rem', fontWeight: 400, color: C.textFaint }}>
                  {isFiltered ? `${count}/${total}` : total}
                </span>
              )}
            </div>

            {isExpanded && (
              <div style={{ maxHeight: '10rem', overflowY: 'auto' }}>
                {loading || !options ? (
                  <div style={{ padding: '0.75rem', textAlign: 'center' }}>
                    <svg className="w-3.5 h-3.5 animate-spin mx-auto" style={{ color: C.textMuted }} fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  </div>
                ) : (
                  options.map(val => {
                    const isChecked = selected.has(val);
                    return (
                      <div
                        key={val}
                        onClick={() => toggleValue(field, val, !isChecked)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.375rem',
                          padding: '0.375rem 0.5rem',
                          cursor: 'pointer',
                          fontSize: '0.688rem',
                          fontFamily: FONT_MONO,
                          borderRadius: '0.5rem',
                          color: isChecked ? C.text : C.textMuted,
                          backgroundColor: 'transparent',
                          border: '0.5px solid transparent',
                          transition: 'all 0.1s ease',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.backgroundColor = C.bgHover; }}
                        onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                      >
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{val}</span>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
