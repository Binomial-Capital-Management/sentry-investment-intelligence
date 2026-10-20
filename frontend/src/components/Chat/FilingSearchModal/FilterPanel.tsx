/**
 * Filing filters panel component
 */

import React from 'react';
import { FilingFilters } from '../../Filings';
import { FilterIcon } from './icons';

// Filing type options for filter dropdown
export const FORM_TYPE_OPTIONS = [
  { value: '', label: 'All Types' },
  { value: '10-K', label: '10-K (Annual)' },
  { value: '10-Q', label: '10-Q (Quarterly)' },
  { value: '8-K', label: '8-K (Current)' },
  { value: 'S-1', label: 'S-1 (Registration)' },
  { value: '20-F', label: '20-F (Foreign Annual)' },
  { value: '6-K', label: '6-K (Foreign Current)' },
  { value: 'DEF 14A', label: 'DEF 14A (Proxy)' },
  { value: '13F', label: '13F (Institutional)' },
  { value: 'SC 13', label: 'SC 13D/G (Ownership)' },
];

interface FilingFiltersPanelProps {
  filters: FilingFilters;
  onChange: (filters: FilingFilters) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export const FilingFiltersPanel: React.FC<FilingFiltersPanelProps> = ({ 
  filters, 
  onChange, 
  isOpen, 
  onToggle 
}) => (
  <div style={{ borderBottom: '1px solid #eee', marginBottom: '8px' }}>
    <button
      onClick={onToggle}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        width: '100%',
        padding: '10px 16px',
        border: 'none',
        background: 'transparent',
        cursor: 'pointer',
        fontSize: '12px',
        fontWeight: 500,
        color: '#666',
      }}
    >
      <FilterIcon />
      Filters
      {(filters.formType || filters.fromDate || filters.toDate) && (
        <span style={{ 
          background: '#1976d2', 
          color: '#fff', 
          padding: '2px 6px', 
          borderRadius: '10px', 
          fontSize: '10px' 
        }}>
          Active
        </span>
      )}
      <span style={{ 
        marginLeft: 'auto', 
        transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', 
        transition: 'transform 0.2s' 
      }}>
        ▼
      </span>
    </button>
    
    {isOpen && (
      <div style={{ 
        padding: '12px 16px', 
        background: '#fafafa', 
        display: 'flex', 
        flexDirection: 'column', 
        gap: '10px' 
      }}>
        <div>
          <label style={{ fontSize: '11px', color: '#666', marginBottom: '4px', display: 'block' }}>
            Form Type
          </label>
          <select
            value={filters.formType || ''}
            onChange={(e) => onChange({ ...filters, formType: e.target.value || undefined })}
            style={{ 
              width: '100%', 
              padding: '6px 8px', 
              fontSize: '12px', 
              border: '1px solid #ddd', 
              borderRadius: '4px', 
              background: '#fff' 
            }}
          >
            {FORM_TYPE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        
        <div style={{ display: 'flex', gap: '8px' }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: '11px', color: '#666', marginBottom: '4px', display: 'block' }}>
              From
            </label>
            <input
              type="date"
              value={filters.fromDate || ''}
              onChange={(e) => onChange({ ...filters, fromDate: e.target.value || undefined })}
              style={{ 
                width: '100%', 
                padding: '6px 8px', 
                fontSize: '12px', 
                border: '1px solid #ddd', 
                borderRadius: '4px' 
              }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: '11px', color: '#666', marginBottom: '4px', display: 'block' }}>
              To
            </label>
            <input
              type="date"
              value={filters.toDate || ''}
              onChange={(e) => onChange({ ...filters, toDate: e.target.value || undefined })}
              style={{ 
                width: '100%', 
                padding: '6px 8px', 
                fontSize: '12px', 
                border: '1px solid #ddd', 
                borderRadius: '4px' 
              }}
            />
          </div>
        </div>
        
        {(filters.formType || filters.fromDate || filters.toDate) && (
          <button
            onClick={() => onChange({})}
            style={{ 
              fontSize: '11px', 
              color: '#e53935', 
              background: 'none', 
              border: 'none', 
              cursor: 'pointer', 
              textAlign: 'left', 
              padding: 0 
            }}
          >
            Clear filters
          </button>
        )}
      </div>
    )}
  </div>
);
