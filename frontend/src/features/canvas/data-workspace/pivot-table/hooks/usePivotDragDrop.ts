import { useState, useCallback, useMemo } from 'react';
import { PivotConfig, PivotValueConfig } from '../../stores/dataWorkspaceStore';
import { FieldInfo } from '../types';

type DragSource = {
  zone: 'rows' | 'columns' | 'values' | 'filters' | null;
  index: number;
} | null;

export function usePivotDragDrop(
  config: PivotConfig | undefined,
  tabId: string,
  updatePivotConfig: (tabId: string, config: Partial<Omit<PivotConfig, 'id'>>) => void,
  fields: FieldInfo[],
  fieldSearch: string
) {
  // Drag and drop state
  const [draggedField, setDraggedField] = useState<string | null>(null);
  const [dragSource, setDragSource] = useState<DragSource>(null);

  // Handle field drop to zones
  const handleDrop = useCallback((targetZone: 'rows' | 'columns' | 'values' | 'filters', field: string) => {
    if (!config) return;
    
    // First, remove from source zone if dragging from another zone
    if (dragSource && dragSource.zone && dragSource.zone !== targetZone) {
      if (dragSource.zone === 'values') {
        const newValues = config.values.filter((_, i) => i !== dragSource.index);
        updatePivotConfig(tabId, { values: newValues });
      } else if (dragSource.zone === 'filters') {
        const newFilters = (config.filterableFields || []).filter((_, i) => i !== dragSource.index);
        updatePivotConfig(tabId, { filterableFields: newFilters });
      } else {
        const newList = config[dragSource.zone].filter((_, i) => i !== dragSource.index);
        updatePivotConfig(tabId, { [dragSource.zone]: newList });
      }
    }
    
    // Then add to target zone (if not already there)
    if (targetZone === 'values') {
      if (!config.values.some(v => v.field === field)) {
        const newValues = [...config.values, { field, aggregation: 'sum' as const, showTotal: true }];
        updatePivotConfig(tabId, { values: newValues });
      }
    } else if (targetZone === 'filters') {
      const currentFilters = config.filterableFields || [];
      if (!currentFilters.includes(field)) {
        updatePivotConfig(tabId, { filterableFields: [...currentFilters, field] });
      }
    } else {
      if (!config[targetZone].includes(field)) {
        const newList = [...config[targetZone], field];
        updatePivotConfig(tabId, { [targetZone]: newList });
      }
    }
    
    setDraggedField(null);
    setDragSource(null);
  }, [config, tabId, updatePivotConfig, dragSource]);
  
  // Remove field from zone
  const removeFromZone = useCallback((zone: 'rows' | 'columns' | 'values', index: number) => {
    if (!config) return;
    
    if (zone === 'values') {
      const newValues = config.values.filter((_, i) => i !== index);
      updatePivotConfig(tabId, { values: newValues });
    } else {
      const newList = config[zone].filter((_, i) => i !== index);
      updatePivotConfig(tabId, { [zone]: newList });
    }
  }, [config, tabId, updatePivotConfig]);
  
  // Change aggregation for a value field
  const changeAggregation = useCallback((index: number, aggregation: PivotValueConfig['aggregation']) => {
    if (!config) return;
    
    const newValues = config.values.map((v, i) => 
      i === index ? { ...v, aggregation } : v
    );
    updatePivotConfig(tabId, { values: newValues });
  }, [config, tabId, updatePivotConfig]);
  
  // Toggle field via checkbox (Excel-style)
  const toggleField = useCallback((field: FieldInfo, currentZone: 'rows' | 'columns' | 'values' | null) => {
    if (!config) return;
    
    if (currentZone) {
      // Field is active - remove it
      if (currentZone === 'values') {
        const idx = config.values.findIndex(v => v.field === field.name);
        if (idx >= 0) removeFromZone('values', idx);
      } else {
        const idx = config[currentZone].findIndex(f => f === field.name);
        if (idx >= 0) removeFromZone(currentZone, idx);
      }
    } else {
      // Field is not active - add it to appropriate zone
      if (field.can_aggregate) {
        handleDrop('values', field.name);
      } else {
        handleDrop('rows', field.name);
      }
    }
  }, [config, handleDrop, removeFromZone]);
  
  // Available fields (not yet used) with search filtering
  const _availableFields = useMemo(() => {
    if (!config) return fields;
    const used = new Set([...config.rows, ...config.columns, ...config.values.map(v => v.field)]);
    const unused = fields.filter(f => !used.has(f.name));
    if (!fieldSearch.trim()) return unused;
    const search = fieldSearch.toLowerCase();
    return unused.filter(f => f.name.toLowerCase().includes(search));
  }, [fields, config, fieldSearch]);

  // All fields for checkbox display (including used ones)
  const allFieldsWithUsage = useMemo(() => {
    if (!config) return fields.map(f => ({ ...f, zone: null as 'rows' | 'columns' | 'values' | null }));
    const rowSet = new Set(config.rows);
    const colSet = new Set(config.columns);
    const valSet = new Set(config.values.map(v => v.field));
    
    return fields.map(f => ({
      ...f,
      zone: rowSet.has(f.name) ? 'rows' as const : 
            colSet.has(f.name) ? 'columns' as const :
            valSet.has(f.name) ? 'values' as const : null
    })).filter(f => !fieldSearch.trim() || f.name.toLowerCase().includes(fieldSearch.toLowerCase()));
  }, [fields, config, fieldSearch]);

  return {
    draggedField,
    setDraggedField,
    dragSource,
    setDragSource,
    handleDrop,
    removeFromZone,
    changeAggregation,
    toggleField,
    _availableFields,
    allFieldsWithUsage,
  };
}
