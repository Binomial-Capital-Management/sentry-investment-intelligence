import { useCallback } from 'react';
import { PivotConfig } from '../../stores/dataWorkspaceStore';
import { PivotResult, CellMap, getCell } from '../types';
import * as XLSX from 'xlsx';

export function usePivotExport(
  pivotResult: PivotResult | null,
  cellMap: CellMap,
  config: PivotConfig | undefined,
) {
  // Export to CSV
  const exportToCSV = useCallback(() => {
    if (!pivotResult || !config) return;
    
    const rows: string[][] = [];
    
    // Header row
    const headerRow: string[] = [];
    if (config.rows.length > 0) headerRow.push(config.rows.join(' / '));
    config.columns.length > 0 
      ? pivotResult.col_headers.forEach(h => headerRow.push(h))
      : config.values.forEach(v => headerRow.push(`${v.aggregation} of ${v.field}`));
    if (config.showGrandTotalColumn) headerRow.push('Grand Total');
    rows.push(headerRow);
    
    // Data rows
    pivotResult.row_headers.forEach(rowKey => {
      const dataRow: string[] = [];
      if (config.rows.length > 0) dataRow.push(rowKey);
      
      if (config.columns.length === 0) {
        config.values.forEach(v => {
          const cell = getCell(cellMap, rowKey, '_total');
          const value = cell?.values[v.field];
          dataRow.push(value != null ? String(value) : '');
        });
      } else {
        pivotResult.col_headers.forEach(colKey => {
          const cell = getCell(cellMap, rowKey, colKey);
          const values = config.values.map(v => cell?.values[v.field]).filter(v => v != null);
          dataRow.push(values.length === 1 ? String(values[0]) : values.join(' | '));
        });
      }
      
      if (config.showGrandTotalColumn && pivotResult.row_totals) {
        const rowTotal = config.values.map(v => pivotResult.row_totals?.[rowKey]?.[v.field]).filter(v => v != null);
        dataRow.push(rowTotal.length === 1 ? String(rowTotal[0]) : rowTotal.join(' | '));
      }
      
      rows.push(dataRow);
    });
    
    // Totals row
    if (config.values.some(v => v.showTotal !== false)) {
      const totalRow: string[] = ['Totals'];
      if (config.columns.length === 0) {
        config.values.forEach(v => {
          const value = pivotResult.totals[v.field];
          totalRow.push(value != null ? String(value) : '');
        });
      } else {
        pivotResult.col_headers.forEach(() => {
          const values = config.values.map(v => pivotResult.totals[v.field]).filter(v => v != null);
          totalRow.push(values.length === 1 ? String(values[0]) : values.join(' | '));
        });
      }
      if (config.showGrandTotalColumn) {
        const grandTotal = config.values.map(v => pivotResult.totals[v.field]).filter(v => v != null);
        totalRow.push(grandTotal.length === 1 ? String(grandTotal[0]) : grandTotal.join(' | '));
      }
      rows.push(totalRow);
    }
    
    // Build CSV string
    const csvContent = rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    
    // Download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `pivot_table_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [pivotResult, cellMap, config]);

  // Export to Excel
  const exportToExcel = useCallback(() => {
    if (!pivotResult || !config) return;
    
    const rows: (string | number | null)[][] = [];
    
    // Header row
    const headerRow: (string | number | null)[] = [];
    if (config.rows.length > 0) headerRow.push(config.rows.join(' / '));
    config.columns.length > 0 
      ? pivotResult.col_headers.forEach(h => headerRow.push(h))
      : config.values.forEach(v => headerRow.push(`${v.aggregation} of ${v.field}`));
    if (config.showGrandTotalColumn) headerRow.push('Grand Total');
    rows.push(headerRow);
    
    // Data rows
    pivotResult.row_headers.forEach(rowKey => {
      const dataRow: (string | number | null)[] = [];
      if (config.rows.length > 0) dataRow.push(rowKey);
      
      if (config.columns.length === 0) {
        config.values.forEach(v => {
          const cell = getCell(cellMap, rowKey, '_total');
          const value = cell?.values[v.field];
          dataRow.push(value ?? null);
        });
      } else {
        pivotResult.col_headers.forEach(colKey => {
          const cell = getCell(cellMap, rowKey, colKey);
          // For Excel, use first value if single, otherwise concatenate
          const values = config.values.map(v => cell?.values[v.field]).filter(v => v != null);
          dataRow.push(values.length === 1 ? (values[0] as number) : values.join(' | '));
        });
      }
      
      if (config.showGrandTotalColumn && pivotResult.row_totals) {
        const rowTotal = config.values.map(v => pivotResult.row_totals?.[rowKey]?.[v.field]).filter(v => v != null);
        dataRow.push(rowTotal.length === 1 ? (rowTotal[0] as number) : (rowTotal.join(' | ')));
      }
      
      rows.push(dataRow);
    });
    
    // Totals row
    if (config.values.some(v => v.showTotal !== false)) {
      const totalRow: (string | number | null)[] = ['Totals'];
      if (config.columns.length === 0) {
        config.values.forEach(v => {
          totalRow.push(pivotResult.totals[v.field] ?? null);
        });
      } else {
        pivotResult.col_headers.forEach(() => {
          const values = config.values.map(v => pivotResult.totals[v.field]).filter(v => v != null);
          totalRow.push(values.length === 1 ? (values[0] as number) : values.join(' | '));
        });
      }
      if (config.showGrandTotalColumn) {
        const grandTotal = config.values.map(v => pivotResult.totals[v.field]).filter(v => v != null);
        totalRow.push(grandTotal.length === 1 ? (grandTotal[0] as number) : grandTotal.join(' | '));
      }
      rows.push(totalRow);
    }
    
    // Create workbook and worksheet
    const ws = XLSX.utils.aoa_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Pivot Table');
    
    // Download
    XLSX.writeFile(wb, `pivot_table_${new Date().toISOString().split('T')[0]}.xlsx`);
  }, [pivotResult, cellMap, config]);

  return {
    exportToCSV,
    exportToExcel,
  };
}
