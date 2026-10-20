/**
 * SeriesEditor - Inline editor for chart Y-series
 * 
 * Features:
 * - List of Y-series with color dots and labels
 * - Color picker (preset palette + custom hex)
 * - Editable custom labels
 * - Add/remove series
 */

import { useState, useRef, useEffect } from 'react';
import { ChartSeriesConfig } from '../../stores/dataWorkspaceStore';

// Preset color palette
const PRESET_COLORS = [
  '#3B82F6', // blue
  '#EF4444', // red
  '#10B981', // green
  '#F59E0B', // amber
  '#8B5CF6', // violet
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#F97316', // orange
  '#6366F1', // indigo
  '#84CC16', // lime
];

interface FieldOption {
  field: string;
  type: 'numeric' | 'date' | 'string';
}

interface Props {
  series: ChartSeriesConfig[];
  availableFields: FieldOption[];
  onChange: (series: ChartSeriesConfig[]) => void;
}

function ColorPicker({ 
  color, 
  onChange, 
  onClose 
}: { 
  color: string; 
  onChange: (color: string) => void; 
  onClose: () => void;
}) {
  const [customHex, setCustomHex] = useState(color);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <div 
      ref={ref}
      className="absolute top-full left-0 mt-1 p-2 bg-white border border-slate-200 rounded-lg shadow-lg z-50"
    >
      <div className="grid grid-cols-5 gap-1 mb-2">
        {PRESET_COLORS.map((c) => (
          <button
            key={c}
            onClick={() => { onChange(c); onClose(); }}
            className={`w-6 h-6 rounded border-2 transition-all ${
              color === c ? 'border-slate-900 scale-110' : 'border-transparent hover:border-slate-300'
            }`}
            style={{ backgroundColor: c }}
            title={c}
          />
        ))}
      </div>
      <div className="flex items-center gap-1 pt-2 border-t border-slate-100">
        <span className="text-[10px] text-slate-400">#</span>
        <input
          type="text"
          value={customHex.replace('#', '')}
          onChange={(e) => {
            const hex = e.target.value.replace(/[^0-9a-fA-F]/g, '').slice(0, 6);
            setCustomHex('#' + hex);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && customHex.length === 7) {
              onChange(customHex);
              onClose();
            }
          }}
          className="w-16 text-xs px-1 py-0.5 border border-slate-200 rounded font-mono"
          placeholder="3B82F6"
        />
        <button
          onClick={() => { if (customHex.length === 7) { onChange(customHex); onClose(); } }}
          disabled={customHex.length !== 7}
          className="text-[10px] px-1.5 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-50"
        >
          OK
        </button>
      </div>
    </div>
  );
}

function SeriesItem({
  series,
  index,
  onUpdate,
  onRemove,
  onReplace,
  availableFields,
}: {
  series: ChartSeriesConfig;
  index: number;
  onUpdate: (updates: Partial<ChartSeriesConfig>) => void;
  onRemove: () => void;
  onReplace: (newField: string) => void;
  availableFields: FieldOption[];
}) {
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [showFieldPicker, setShowFieldPicker] = useState(false);
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelValue, setLabelValue] = useState(series.label || '');
  const color = series.color || PRESET_COLORS[index % PRESET_COLORS.length];
  const fieldPickerRef = useRef<HTMLDivElement>(null);

  // Fields available for replacement (numeric fields not already used, plus current field)
  const replaceableFields = availableFields.filter(
    (f) => f.type === 'numeric' && f.field !== series.field
  );

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (fieldPickerRef.current && !fieldPickerRef.current.contains(e.target as Node)) {
        setShowFieldPicker(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="flex items-center gap-2 py-1.5 px-2 bg-slate-50 rounded group">
      {/* Color dot - clickable */}
      <div className="relative">
        <button
          onClick={() => setShowColorPicker(!showColorPicker)}
          className="w-4 h-4 rounded-full border border-slate-300 hover:scale-110 transition-transform"
          style={{ backgroundColor: color }}
          title="Change color"
        />
        {showColorPicker && (
          <ColorPicker
            color={color}
            onChange={(c) => onUpdate({ color: c })}
            onClose={() => setShowColorPicker(false)}
          />
        )}
      </div>

      {/* Field name - clickable to replace */}
      <div className="relative flex-1 min-w-0" ref={fieldPickerRef}>
        <button
          onClick={() => setShowFieldPicker(!showFieldPicker)}
          className="text-xs text-slate-600 font-medium truncate w-full text-left hover:text-blue-600"
          title="Click to change field"
        >
          {series.field}
        </button>
        {showFieldPicker && replaceableFields.length > 0 && (
          <div className="absolute top-full left-0 mt-1 py-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 min-w-[120px] max-h-48 overflow-y-auto">
            {replaceableFields.map((f) => (
              <button
                key={f.field}
                onClick={() => { onReplace(f.field); setShowFieldPicker(false); }}
                className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
              >
                {f.field}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Label editor */}
      {editingLabel ? (
        <input
          type="text"
          value={labelValue}
          onChange={(e) => setLabelValue(e.target.value)}
          onBlur={() => {
            onUpdate({ label: labelValue || undefined });
            setEditingLabel(false);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onUpdate({ label: labelValue || undefined });
              setEditingLabel(false);
            }
            if (e.key === 'Escape') {
              setLabelValue(series.label || '');
              setEditingLabel(false);
            }
          }}
          className="w-20 text-[10px] px-1 py-0.5 border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
          placeholder="Label..."
          autoFocus
        />
      ) : (
        <button
          onClick={() => { setLabelValue(series.label || ''); setEditingLabel(true); }}
          className="text-[10px] text-slate-400 hover:text-slate-600 truncate max-w-[60px]"
          title={series.label ? `Label: ${series.label}` : 'Add label'}
        >
          {series.label || 'label'}
        </button>
      )}

      {/* Remove button - always visible */}
      <button
        onClick={onRemove}
        className="p-0.5 text-slate-400 hover:text-red-500"
        title="Remove series"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export function SeriesEditor({ series, availableFields, onChange }: Props) {
  const [showAddMenu, setShowAddMenu] = useState(false);
  const addMenuRef = useRef<HTMLDivElement>(null);

  // Fields that can be added (numeric fields not already in series)
  const addableFields = availableFields.filter(
    (f) => f.type === 'numeric' && !series.some((s) => s.field === f.field)
  );

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleUpdate = (index: number, updates: Partial<ChartSeriesConfig>) => {
    const newSeries = [...series];
    newSeries[index] = { ...newSeries[index], ...updates };
    onChange(newSeries);
  };

  const handleRemove = (index: number) => {
    const newSeries = series.filter((_, i) => i !== index);
    onChange(newSeries);
  };

  const handleReplace = (index: number, newField: string) => {
    const newSeries = [...series];
    newSeries[index] = { ...newSeries[index], field: newField, label: undefined };
    onChange(newSeries);
  };

  const handleAdd = (field: string) => {
    const newIndex = series.length;
    onChange([...series, { field, color: PRESET_COLORS[newIndex % PRESET_COLORS.length] }]);
    setShowAddMenu(false);
  };

  return (
    <div className="space-y-2">
      {/* Series list */}
      <div className="space-y-1">
        {series.map((s, i) => (
          <SeriesItem
            key={`${s.field}-${i}`}
            series={s}
            index={i}
            onUpdate={(updates) => handleUpdate(i, updates)}
            onRemove={() => handleRemove(i)}
            onReplace={(newField) => handleReplace(i, newField)}
            availableFields={availableFields}
          />
        ))}
      </div>

      {/* Add series button */}
      {addableFields.length > 0 && (
        <div className="relative" ref={addMenuRef}>
          <button
            onClick={() => setShowAddMenu(!showAddMenu)}
            className="flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-700 font-medium"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Add Series
          </button>

          {showAddMenu && (
            <div className="absolute top-full left-0 mt-1 py-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 min-w-[120px] max-h-48 overflow-y-auto">
              {addableFields.map((f) => (
                <button
                  key={f.field}
                  onClick={() => handleAdd(f.field)}
                  className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <span className="w-2 h-2 rounded-full bg-slate-300" />
                  {f.field}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {series.length === 0 && (
        <div className="text-[10px] text-slate-400 text-center py-2">
          No series selected
        </div>
      )}
    </div>
  );
}

