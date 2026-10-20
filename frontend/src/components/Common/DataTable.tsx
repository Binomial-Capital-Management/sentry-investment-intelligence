import React, { useState, useMemo, ReactNode } from 'react';
import { motion } from 'framer-motion';
import { ChevronUp, ChevronDown, ArrowUpDown } from 'lucide-react';
import { Text } from './Typography';

// Column configuration interface
export interface DataTableColumn<T = any> {
  key: keyof T;
  label: string;
  align?: 'left' | 'center' | 'right';
  format?: 'text' | 'currency' | 'percentage' | 'number' | 'date';
  sortable?: boolean;
  width?: string | number;
  render?: (value: any, row: T) => ReactNode;
}

// Table configuration interface
interface DataTableProps<T = any> {
  columns: DataTableColumn<T>[];
  data: T[];
  sortable?: boolean;
  density?: 'compact' | 'normal' | 'comfortable';
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
  stickyHeader?: boolean;
  zebra?: boolean;
}

// Sort state interface
interface SortState {
  column: string | null;
  direction: 'asc' | 'desc' | null;
}

// Format value utility
const formatValue = (value: any, format?: DataTableColumn['format']): string => {
  if (value === null || value === undefined || value === '') return '—';

  switch (format) {
    case 'currency':
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
      }).format(Number(value));

    case 'percentage':
      return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(Number(value) / 100);

    case 'number':
      return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(Number(value));

    case 'date':
      return new Date(value).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });

    case 'text':
    default:
      return String(value);
  }
};

// Loading skeleton row component
const SkeletonRow: React.FC<{ columns: DataTableColumn[]; density: string }> = ({ columns, density }) => {
  const getRowHeight = () => {
    switch (density) {
      case 'compact': return '28px';
      case 'comfortable': return '44px';
      default: return '36px';
    }
  };

  return (
    <tr style={{ height: getRowHeight() }}>
      {columns.map((_column, index) => (
        <td
          key={index}
          style={{
            padding: density === 'compact' ? '4px 12px' : density === 'comfortable' ? '12px 16px' : '8px 12px',
            borderBottom: '1px solid #E1DFDD',
          }}
        >
          <div
            style={{
              height: '14px',
              background: '#F3F2F1',
              borderRadius: '2px',
              width: `${Math.random() * 60 + 40}%`,
            }}
          />
        </td>
      ))}
    </tr>
  );
};

// Empty state component
const EmptyState: React.FC<{ message: string; colSpan: number }> = ({ message, colSpan }) => (
  <tr>
    <td colSpan={colSpan} style={{ textAlign: 'center', padding: '48px 24px' }}>
      <Text color="muted" variant="body">
        {message}
      </Text>
    </td>
  </tr>
);

// Main DataTable component
export const DataTable = <T extends Record<string, any>>({
  columns,
  data,
  sortable = true,
  density = 'normal',
  loading = false,
  emptyMessage = 'No data available',
  className = '',
  stickyHeader = false,
  zebra = true,
}: DataTableProps<T>) => {
  const [sortState, setSortState] = useState<SortState>({ column: null, direction: null });

  // Handle sorting
  const handleSort = (columnKey: string) => {
    if (!sortable) return;

    const column = columns.find(col => col.key === columnKey);
    if (!column?.sortable && column?.sortable !== undefined) return;

    setSortState(prevState => {
      if (prevState.column === columnKey) {
        if (prevState.direction === 'asc') {
          return { column: columnKey, direction: 'desc' };
        } else if (prevState.direction === 'desc') {
          return { column: null, direction: null };
        }
      }
      return { column: columnKey, direction: 'asc' };
    });
  };

  // Sort data
  const sortedData = useMemo(() => {
    if (!sortState.column || !sortState.direction) return data;

    return [...data].sort((a, b) => {
      const aVal = a[sortState.column!];
      const bVal = b[sortState.column!];

      if (aVal === bVal) return 0;

      let comparison = 0;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sortState.direction === 'asc' ? comparison : -comparison;
    });
  }, [data, sortState]);

  // Get dynamic styles based on density
  const getRowHeight = () => {
    switch (density) {
      case 'compact': return '28px';
      case 'comfortable': return '44px';
      default: return '36px';
    }
  };

  const getCellPadding = () => {
    switch (density) {
      case 'compact': return '4px 12px';
      case 'comfortable': return '12px 16px';
      default: return '8px 12px';
    }
  };

  // Render sort icon
  const renderSortIcon = (columnKey: string) => {
    if (!sortable) return null;

    const column = columns.find(col => col.key === columnKey);
    if (column?.sortable === false) return null;

    if (sortState.column === columnKey) {
      return sortState.direction === 'asc' ? (
        <ChevronUp size={14} style={{ marginLeft: '4px' }} />
      ) : (
        <ChevronDown size={14} style={{ marginLeft: '4px' }} />
      );
    }

    return <ArrowUpDown size={12} style={{ marginLeft: '4px', opacity: 0.4 }} />;
  };

  return (
    <div className={`data-table-container ${className}`}>
      <div
        style={{
          border: '1px solid #E1DFDD',
          borderRadius: '6px',
          overflow: 'hidden',
          background: '#FFFFFF',
          boxShadow: '0 1.6px 3.6px rgba(0,0,0,0.132)',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontFamily: 'var(--font-institutional)',
          }}
        >
          <thead
            style={{
              background: '#F3F2F1',
              position: stickyHeader ? 'sticky' : 'static',
              top: 0,
              zIndex: 10,
            }}
          >
            <tr>
              {columns.map((column) => (
                <th
                  key={String(column.key)}
                  onClick={() => handleSort(String(column.key))}
                  style={{
                    padding: getCellPadding(),
                    textAlign: column.align || 'left',
                    borderBottom: '1px solid #E1DFDD',
                    fontSize: '12px',
                    fontWeight: '600',
                    color: '#605E5C',
                    cursor: sortable && column.sortable !== false ? 'pointer' : 'default',
                    userSelect: 'none',
                    width: column.width,
                    transition: 'background-color 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (sortable && column.sortable !== false) {
                      e.currentTarget.style.backgroundColor = 'var(--hover-bg)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-subtle)';
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: column.align === 'center' ? 'center' : column.align === 'right' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    {column.label}
                    {renderSortIcon(String(column.key))}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              // Loading skeleton
              Array.from({ length: 5 }).map((_, index) => (
                <SkeletonRow key={index} columns={columns} density={density} />
              ))
            ) : sortedData.length === 0 ? (
              // Empty state
              <EmptyState message={emptyMessage} colSpan={columns.length} />
            ) : (
              // Data rows
              sortedData.map((row, rowIndex) => (
                <motion.tr
                  key={rowIndex}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2, delay: rowIndex * 0.02 }}
                  style={{
                    height: getRowHeight(),
                    backgroundColor: zebra && rowIndex % 2 === 1 ? 'var(--bg-surface)' : 'transparent',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--hover-bg)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = zebra && rowIndex % 2 === 1 ? 'var(--bg-surface)' : 'transparent';
                  }}
                >
                  {columns.map((column) => {
                    const value = row[column.key];
                    const isNumeric = column.format && ['currency', 'percentage', 'number'].includes(column.format);

                    return (
                      <td
                        key={String(column.key)}
                        style={{
                          padding: getCellPadding(),
                          textAlign: column.align || 'left',
                          borderBottom: '1px solid #E1DFDD',
                          fontSize: '13px',
                          fontFamily: isNumeric ? 'var(--font-mono-institutional)' : 'var(--font-institutional)',
                          color: 'var(--text-primary)',
                          verticalAlign: 'middle',
                        }}
                      >
                        {column.render ? column.render(value, row) : formatValue(value, column.format)}
                      </td>
                    );
                  })}
                </motion.tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DataTable;
