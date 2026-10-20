/**
 * FieldSelector - Modern searchable dropdown for field selection
 * 
 * Features:
 * - Search/filter fields
 * - Group by symbol prefix (JPM_, BAC_, etc.)
 * - Modern styling with smooth animations
 * - Keyboard navigation
 */

import { useState, useRef, useEffect, useMemo } from 'react';

interface FieldOption {
  field: string;
  type: 'numeric' | 'date' | 'string';
}

interface Props {
  value: string;
  options: FieldOption[];
  onChange: (field: string) => void;
  placeholder?: string;
}

// Extract symbol prefix from field name (e.g., "JPM_netIncome" -> "JPM")
function getSymbolPrefix(field: string): string | null {
  const match = field.match(/^([A-Z]{1,5})_/);
  return match ? match[1] : null;
}

// Group fields by symbol prefix
function groupFields(fields: FieldOption[]): { prefix: string | null; fields: FieldOption[] }[] {
  const groups: Map<string | null, FieldOption[]> = new Map();
  
  // First pass: group by prefix
  fields.forEach(f => {
    const prefix = getSymbolPrefix(f.field);
    if (!groups.has(prefix)) {
      groups.set(prefix, []);
    }
    groups.get(prefix)!.push(f);
  });
  
  // Convert to array with unprefixed first, then sorted prefixes
  const result: { prefix: string | null; fields: FieldOption[] }[] = [];
  
  // Add unprefixed fields first (common fields like date, calendarYear)
  if (groups.has(null)) {
    result.push({ prefix: null, fields: groups.get(null)! });
    groups.delete(null);
  }
  
  // Add prefixed groups sorted alphabetically
  const sortedPrefixes = Array.from(groups.keys()).sort() as string[];
  sortedPrefixes.forEach(prefix => {
    result.push({ prefix, fields: groups.get(prefix)! });
  });
  
  return result;
}

export function FieldSelector({ value, options, onChange, placeholder = 'Select field...' }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Filter options based on search
  const filteredOptions = useMemo(() => {
    if (!search.trim()) return options;
    const searchLower = search.toLowerCase();
    return options.filter(o => o.field.toLowerCase().includes(searchLower));
  }, [options, search]);

  // Group filtered options
  const groupedOptions = useMemo(() => groupFields(filteredOptions), [filteredOptions]);

  // Flat list for keyboard navigation
  const flatOptions = useMemo(() => {
    return groupedOptions.flatMap(g => g.fields);
  }, [groupedOptions]);

  // Get display value
  const selectedOption = options.find(o => o.field === value);
  const displayValue = selectedOption 
    ? `${selectedOption.field} (${selectedOption.type === 'date' ? 'date' : 'num'})`
    : placeholder;

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus input when opening
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (isOpen && listRef.current) {
      const highlighted = listRef.current.querySelector('[data-highlighted="true"]');
      if (highlighted) {
        highlighted.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex, isOpen]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(i => Math.min(i + 1, flatOptions.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(i => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (flatOptions[highlightedIndex]) {
          onChange(flatOptions[highlightedIndex].field);
          setIsOpen(false);
          setSearch('');
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        setSearch('');
        break;
    }
  };

  const handleSelect = (field: string) => {
    onChange(field);
    setIsOpen(false);
    setSearch('');
  };

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        className={`
          w-full flex items-center justify-between gap-2
          px-3 py-2 text-xs text-left
          bg-white border rounded-lg
          transition-all duration-150
          ${isOpen 
            ? 'border-blue-400 ring-2 ring-blue-100' 
            : 'border-slate-200 hover:border-slate-300'
          }
        `}
      >
        <span className={selectedOption ? 'text-slate-700' : 'text-slate-400'}>
          {displayValue}
        </span>
        <svg 
          className={`w-4 h-4 text-slate-400 transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`}
          fill="none" 
          stroke="currentColor" 
          strokeWidth={2} 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
          {/* Search input */}
          <div className="p-2 border-b border-slate-100">
            <div className="relative">
              <svg 
                className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400"
                fill="none" 
                stroke="currentColor" 
                strokeWidth={2} 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setHighlightedIndex(0);
                }}
                onKeyDown={handleKeyDown}
                placeholder="Search fields..."
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:border-blue-300 focus:bg-white"
              />
            </div>
          </div>

          {/* Options list */}
          <div ref={listRef} className="max-h-64 overflow-y-auto">
            {groupedOptions.length === 0 ? (
              <div className="px-3 py-4 text-xs text-slate-400 text-center">
                No fields found
              </div>
            ) : (
              groupedOptions.map((group) => (
                <div key={group.prefix ?? '_common'}>
                  {/* Group header */}
                  {group.prefix !== null && (
                    <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider bg-slate-50 sticky top-0">
                      {group.prefix}
                    </div>
                  )}
                  {group.prefix === null && groupedOptions.length > 1 && (
                    <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider bg-slate-50 sticky top-0">
                      Common
                    </div>
                  )}
                  
                  {/* Group items */}
                  {group.fields.map((option) => {
                    const globalIndex = flatOptions.findIndex(f => f.field === option.field);
                    const isHighlighted = globalIndex === highlightedIndex;
                    const isSelected = option.field === value;
                    
                    // Display name without prefix for prefixed fields
                    const displayName = group.prefix 
                      ? option.field.replace(`${group.prefix}_`, '')
                      : option.field;
                    
                    return (
                      <button
                        key={option.field}
                        data-highlighted={isHighlighted}
                        onClick={() => handleSelect(option.field)}
                        onMouseEnter={() => setHighlightedIndex(globalIndex)}
                        className={`
                          w-full flex items-center justify-between gap-2
                          px-3 py-2 text-xs text-left
                          transition-colors duration-75
                          ${isHighlighted ? 'bg-blue-50' : ''}
                          ${isSelected ? 'text-blue-600 font-medium' : 'text-slate-700'}
                          hover:bg-blue-50
                        `}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {isSelected && (
                            <svg className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                          <span className={`truncate ${isSelected ? '' : 'ml-5'}`}>
                            {displayName}
                          </span>
                        </div>
                        <span className={`
                          flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded
                          ${option.type === 'date' 
                            ? 'bg-amber-100 text-amber-700' 
                            : 'bg-slate-100 text-slate-500'
                          }
                        `}>
                          {option.type === 'date' ? 'date' : 'num'}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
