import React, { useMemo } from 'react';
import { useOntologyStore } from '@/stores/ontologyStore';
import type { OntologyObject } from '@/types/ontology';
import './ontology.css';

export default function OntologyTableView() {
  const { objects, viewState } = useOntologyStore();

  // Filter objects logic (reused/similar to graph)
  const filteredObjects = useMemo(() => {
    const objectArray = Array.from(objects.values());

    // Filter by object type filters if active
    const typeFiltered = viewState.object_type_filters.length > 0
      ? objectArray.filter(obj => viewState.object_type_filters.includes(obj.type))
      : objectArray;

    // Filter by search query
    const searchQuery = viewState.search_query.toLowerCase();
    const finalObjects = searchQuery
      ? typeFiltered.filter(obj => {
          const searchableText = JSON.stringify(obj).toLowerCase();
          return searchableText.includes(searchQuery);
        })
      : typeFiltered;

    return finalObjects;
  }, [objects, viewState.object_type_filters, viewState.search_query]);

  // Dynamic column generation based on visible objects
  const columns = useMemo(() => {
    const baseColumns = [
      { key: 'type', label: 'Type', width: '100px' },
      { key: 'id', label: 'ID', width: '150px' },
    ];

    // Determine visible types
    const visibleTypes = new Set(filteredObjects.map(o => o.type));

    if (visibleTypes.has('company')) {
        baseColumns.push({ key: 'ticker', label: 'Ticker', width: '80px' });
        baseColumns.push({ key: 'name', label: 'Name', width: '200px' });
        baseColumns.push({ key: 'price', label: 'Price', width: '100px' });
        baseColumns.push({ key: 'change', label: 'Change %', width: '100px' });
        baseColumns.push({ key: 'sector', label: 'Sector', width: '150px' });
    }

    if (visibleTypes.has('portfolio')) {
        baseColumns.push({ key: 'total_value', label: 'Total Value', width: '120px' });
        baseColumns.push({ key: 'invested', label: 'Invested', width: '120px' });
    }

    if (visibleTypes.has('sec_filing')) {
        baseColumns.push({ key: 'form_type', label: 'Form', width: '80px' });
        baseColumns.push({ key: 'filing_date', label: 'Date', width: '120px' });
    }

    return baseColumns;
  }, [filteredObjects]);

  // Helper to get cell value safely
  const getCellValue = (obj: any, key: string) => {
    if (key === 'price' && typeof obj.price === 'number') return `$${obj.price.toFixed(2)}`;
    if (key === 'change' && typeof obj.change === 'number') return `${obj.change > 0 ? '+' : ''}${obj.change.toFixed(2)}%`;
    if (key === 'total_value' && typeof obj.total_value === 'number') return `$${(obj.total_value / 1e6).toFixed(2)}M`;
    if (key === 'invested' && typeof obj.invested === 'number') return `$${(obj.invested / 1e6).toFixed(2)}M`;
    if (key === 'filing_date') return new Date(obj.filing_date).toLocaleDateString();
    return obj[key] || '-';
  };

  return (
    <div className="ontology-table-container">
      {/* Header managed by parent Workspace now */}
      <div className="ontology-table-wrapper">
        <table className="ontology-data-table">
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key} style={{ width: col.width }}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredObjects.map(obj => (
              <tr key={obj.id} className="ontology-row">
                {columns.map(col => (
                  <td key={`${obj.id}-${col.key}`}>
                    {col.key === 'type' ? (
                        <span className={`ontology-type-badge type-${obj.type}`}>
                            {obj.type.replace('_', ' ').toUpperCase()}
                        </span>
                    ) : (
                        getCellValue(obj, col.key)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
