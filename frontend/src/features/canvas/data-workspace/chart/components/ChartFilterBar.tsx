/**
 * ChartFilterBar - Compact filter controls for chart data
 * 
 * Designed for narrow sidebar use. Supports date_range and numeric_range filter types.
 * Displays active filters as removable items in a vertical list.
 */

import { useState, useMemo } from 'react';
import { ChartFilter } from '../../../../stores/dataWorkspaceStore';

interface ChartFilterBarProps {
  filters: ChartFilter[];
  availableFields: { field: string; type: 'date' | 'numeric' | 'string' }[];
  onChange: (filters: ChartFilter[]) => void;
}

// Generate unique ID for filters
const generateFilterId = () => `filter-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export function ChartFilterBar({ filters, availableFields, onChange }: ChartFilterBarProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newFilter, setNewFilter] = useState<{
    field: string;
    filterType: 'date_range' | 'numeric_range';
    minValue: string;
    maxValue: string;
  }>({
    field: '',
    filterType: 'numeric_range',
    minValue: '',
    maxValue: '',
  });

  // Filter out invalid filters (those without a field)
  const validFilters = useMemo(() => {
    return filters.filter(f => f.field && f.field.trim() !== '');
  }, [filters]);

  // Fields not already filtered (only numeric and date fields)
  const unfiltered = useMemo(() => {
    const filteredFields = new Set(validFilters.map(f => f.field));
    return availableFields.filter(f => 
      (f.type === 'numeric' || f.type === 'date') && !filteredFields.has(f.field)
    );
  }, [validFilters, availableFields]);

  const handleAddFilter = () => {
    if (!newFilter.field || newFilter.field.trim() === '') return;
    
    // Only add if at least one value is set
    if (!newFilter.minValue && !newFilter.maxValue) return;
    
    const filter: ChartFilter = {
      id: generateFilterId(),
      field: newFilter.field,
      filterType: newFilter.filterType,
      minValue: newFilter.minValue || undefined,
      maxValue: newFilter.maxValue || undefined,
    };
    
    onChange([...validFilters, filter]);
    setNewFilter({ field: '', filterType: 'numeric_range', minValue: '', maxValue: '' });
    setShowAddForm(false);
  };

  const handleRemoveFilter = (filterId: string) => {
    onChange(validFilters.filter(f => f.id !== filterId));
  };

  const handleUpdateFilter = (filterId: string, updates: Partial<ChartFilter>) => {
    onChange(validFilters.map(f => f.id === filterId ? { ...f, ...updates } : f));
  };

  // Infer filter type from field type
  const handleFieldChange = (field: string) => {
    const fieldMeta = availableFields.find(f => f.field === field);
    const inferredType = fieldMeta?.type === 'date' ? 'date_range' : 'numeric_range';
    setNewFilter({ ...newFilter, field, filterType: inferredType, minValue: '', maxValue: '' });
  };

  // Don't render if no filterable fields
  if (availableFields.filter(f => f.type === 'numeric' || f.type === 'date').length === 0) {
    return <div className="text-[10px] text-slate-400 py-2">No filterable fields</div>;
  }

  return (
    <div className="space-y-2">
      {/* Active filters list */}
      {validFilters.length > 0 && (
        <div className="space-y-1">
          {validFilters.map(filter => (
            <FilterItem
              key={filter.id}
              filter={filter}
              onRemove={() => handleRemoveFilter(filter.id)}
              onUpdate={(updates) => handleUpdateFilter(filter.id, updates)}
            />
          ))}
          <button
            onClick={() => onChange([])}
            className="text-[10px] text-slate-400 hover:text-red-500 transition-colors"
          >
            Clear all filters
          </button>
        </div>
      )}

      {/* Add filter form */}
      {showAddForm ? (
        <div className="p-2 bg-slate-50 rounded border border-slate-200 space-y-2">
          {/* Field selector */}
          <div>
            <label className="text-[10px] text-slate-500">Field</label>
            <select
              value={newFilter.field}
              onChange={(e) => handleFieldChange(e.target.value)}
              className="w-full mt-0.5 text-xs border border-slate-200 rounded bg-white px-2 py-1"
              autoFocus
            >
              <option value="">Select field...</option>
              {unfiltered.map(f => (
                <option key={f.field} value={f.field}>
                  {f.field} ({f.type})
                </option>
              ))}
            </select>
          </div>

          {newFilter.field && (
            <>
              {/* Range inputs */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-500">Min</label>
                  {newFilter.filterType === 'date_range' ? (
                    <input
                      type="date"
                      value={newFilter.minValue}
                      onChange={(e) => setNewFilter({ ...newFilter, minValue: e.target.value })}
                      className="w-full mt-0.5 text-xs border border-slate-200 rounded px-2 py-1"
                    />
                  ) : (
                    <input
                      type="number"
                      placeholder="No min"
                      value={newFilter.minValue}
                      onChange={(e) => setNewFilter({ ...newFilter, minValue: e.target.value })}
                      className="w-full mt-0.5 text-xs border border-slate-200 rounded px-2 py-1"
                    />
                  )}
                </div>
                <div>
                  <label className="text-[10px] text-slate-500">Max</label>
                  {newFilter.filterType === 'date_range' ? (
                    <input
                      type="date"
                      value={newFilter.maxValue}
                      onChange={(e) => setNewFilter({ ...newFilter, maxValue: e.target.value })}
                      className="w-full mt-0.5 text-xs border border-slate-200 rounded px-2 py-1"
                    />
                  ) : (
                    <input
                      type="number"
                      placeholder="No max"
                      value={newFilter.maxValue}
                      onChange={(e) => setNewFilter({ ...newFilter, maxValue: e.target.value })}
                      className="w-full mt-0.5 text-xs border border-slate-200 rounded px-2 py-1"
                    />
                  )}
                </div>
              </div>

              {/* Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleAddFilter}
                  disabled={!newFilter.minValue && !newFilter.maxValue}
                  className="flex-1 text-xs bg-blue-600 text-white hover:bg-blue-700 font-medium px-2 py-1 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Add Filter
                </button>
                <button
                  onClick={() => {
                    setShowAddForm(false);
                    setNewFilter({ field: '', filterType: 'numeric_range', minValue: '', maxValue: '' });
                  }}
                  className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1"
                >
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <button
          onClick={() => setShowAddForm(true)}
          disabled={unfiltered.length === 0}
          className="flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add Filter
        </button>
      )}
    </div>
  );
}

// Individual filter item component (vertical layout)
function FilterItem({
  filter,
  onRemove,
  onUpdate,
}: {
  filter: ChartFilter;
  onRemove: () => void;
  onUpdate: (updates: Partial<ChartFilter>) => void;
}) {
  const [editing, setEditing] = useState(false);

  const formatValue = (val: string | number | undefined): string => {
    if (val === undefined || val === '') return '∞';
    if (typeof val === 'string' && val.match(/^\d{4}-\d{2}-\d{2}/)) {
      return val.slice(0, 10); // Truncate date
    }
    return String(val);
  };

  const rangeText = `${formatValue(filter.minValue)} → ${formatValue(filter.maxValue)}`;

  if (editing) {
    return (
      <div className="p-2 bg-blue-50 border border-blue-200 rounded space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-blue-700">{filter.field}</span>
          <button
            onClick={() => setEditing(false)}
            className="text-[10px] text-blue-600 hover:text-blue-800 font-medium"
          >
            Done
          </button>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {filter.filterType === 'date_range' ? (
            <>
              <input
                type="date"
                value={filter.minValue as string || ''}
                onChange={(e) => onUpdate({ minValue: e.target.value || undefined })}
                className="text-xs border border-blue-200 rounded px-1.5 py-1 w-full"
              />
              <input
                type="date"
                value={filter.maxValue as string || ''}
                onChange={(e) => onUpdate({ maxValue: e.target.value || undefined })}
                className="text-xs border border-blue-200 rounded px-1.5 py-1 w-full"
              />
            </>
          ) : (
            <>
              <input
                type="number"
                value={filter.minValue as number ?? ''}
                onChange={(e) => onUpdate({ minValue: e.target.value ? Number(e.target.value) : undefined })}
                className="text-xs border border-blue-200 rounded px-1.5 py-1 w-full"
                placeholder="Min"
              />
              <input
                type="number"
                value={filter.maxValue as number ?? ''}
                onChange={(e) => onUpdate({ maxValue: e.target.value ? Number(e.target.value) : undefined })}
                className="text-xs border border-blue-200 rounded px-1.5 py-1 w-full"
                placeholder="Max"
              />
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 py-1 px-2 bg-blue-50 border border-blue-200 rounded">
      <span className="text-xs font-medium text-blue-700 truncate flex-1">{filter.field}</span>
      <button
        onClick={() => setEditing(true)}
        className="text-[10px] text-blue-500 hover:text-blue-700 truncate max-w-[80px]"
        title={`${filter.minValue ?? '∞'} to ${filter.maxValue ?? '∞'}`}
      >
        {rangeText}
      </button>
      <button
        onClick={onRemove}
        className="text-blue-400 hover:text-red-500 flex-shrink-0"
        title="Remove filter"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export default ChartFilterBar;

