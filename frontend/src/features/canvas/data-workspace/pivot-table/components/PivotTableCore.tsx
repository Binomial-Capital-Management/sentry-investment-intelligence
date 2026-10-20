import { useState, useEffect, useCallback, useRef } from 'react';
import { PivotConfig } from '../../stores/dataWorkspaceStore';
import { PivotResult, CellMap, getCell } from '../types';

// Convert internal field names to user-friendly display names
const FIELD_DISPLAY_NAMES: Record<string, string> = {
  '_source_symbol': 'Symbol',
  '_row': 'Row',
  'fiscalYear': 'Fiscal Year',
  'calendarYear': 'Calendar Year',
};

function getFieldDisplayName(field: string): string {
  return FIELD_DISPLAY_NAMES[field] || field;
}

interface PivotTableProps {
  config: PivotConfig;
  pivotResult: PivotResult | null;
  cellMap: CellMap;
  sortedRowHeaders: string[];
  sortColumn: string | null;
  sortDirection: 'asc' | 'desc';
  handleSort: (column: string) => void;
  formatValue: (
    value: number | null | undefined,
    showAs: 'value' | 'pct_row' | 'pct_col' | 'pct_grand' | undefined,
    rowTotal: number | null | undefined,
    colTotal: number | null | undefined,
    grandTotal: number | null | undefined
  ) => string;
  columnTotals: Record<string, Record<string, number>>;
  overlayOpen?: boolean;
  overlayHeightPct?: number;
}

export function PivotTable({
  config,
  pivotResult,
  cellMap,
  sortedRowHeaders,
  sortColumn,
  sortDirection,
  handleSort,
  formatValue,
  columnTotals,
  overlayOpen,
  overlayHeightPct,
}: PivotTableProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const theadRef = useRef<HTMLTableSectionElement>(null);
  const [fades, setFades] = useState({ top: false, right: false, bottom: false, left: false });
  const [scrollbarSize, setScrollbarSize] = useState({ x: 0, y: 0 });
  const [headerHeight, setHeaderHeight] = useState(0);

  const [containerHeight, setContainerHeight] = useState(0);

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setScrollbarSize({ y: el.offsetWidth - el.clientWidth, x: el.offsetHeight - el.clientHeight });
    setHeaderHeight(theadRef.current?.offsetHeight || 0);
    setContainerHeight(wrapperRef.current?.clientHeight || 0);
    setFades({
      top: el.scrollTop > 2,
      right: el.scrollLeft + el.clientWidth < el.scrollWidth - 2,
      bottom: el.scrollTop + el.clientHeight < el.scrollHeight - 2,
      left: el.scrollLeft > 2,
    });
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateFades();
    el.addEventListener('scroll', updateFades, { passive: true });
    const ro = new ResizeObserver(updateFades);
    ro.observe(el);

    let timer: ReturnType<typeof setTimeout>;
    const onScroll = () => {
      el.classList.add('is-scrolling');
      clearTimeout(timer);
      timer = setTimeout(() => el.classList.remove('is-scrolling'), 800);
    };
    el.addEventListener('scroll', onScroll, { passive: true });

    return () => { el.removeEventListener('scroll', updateFades); el.removeEventListener('scroll', onScroll); ro.disconnect(); clearTimeout(timer); };
  }, [updateFades]);

  const sbY = scrollbarSize.y;
  const sbX = scrollbarSize.x;

  return (
    <div ref={wrapperRef} className="relative flex-1 min-h-0">
      {!pivotResult || pivotResult.cells.length === 0 ? (
        <div className="flex items-center justify-center h-full text-slate-400">
          <div className="text-center">
            <svg className="w-16 h-16 mx-auto mb-4 text-slate-200" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25" />
            </svg>
            <div className="text-sm font-medium">Configure Your Pivot Table</div>
            <div className="text-xs text-slate-400 mt-1">Drag fields to Rows, Columns, and Values zones</div>
          </div>
        </div>
      ) : (
        <div ref={scrollRef} className="h-full overflow-auto pivot-scroll"
          style={{
            ...(overlayOpen && overlayHeightPct ? { paddingBottom: containerHeight * overlayHeightPct / 100 } : {}),
            '--pivot-header-h': `${headerHeight}px`,
          } as React.CSSProperties}>
          <div>
            <table className="w-full text-xs">
              <thead ref={theadRef} className="bg-slate-50 sticky top-0 z-20">
                <tr>
                  {/* Row dimension header OR Value field header when no rows but multiple values */}
                  {(config.rows.length > 0 || (config.rows.length === 0 && config.values.length > 1)) && (
                    <th 
                      className="px-3 py-2 text-left font-medium text-slate-600 border-r border-b border-slate-200 cursor-pointer hover:bg-slate-100 select-none"
                      onClick={() => handleSort('_row')}
                    >
                      <div className="flex items-center gap-1">
                        {config.rows.length > 0 ? config.rows.map(getFieldDisplayName).join(' / ') : 'Metric'}
                        {sortColumn === '_row' && (
                          <span className="text-[10px]">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                  )}
                  {/* Column headers */}
                  {config.columns.length === 0 && config.values.length > 1 ? (
                    // No column dimension, single row - value names as columns
                    config.values.map(v => (
                      <th 
                        key={v.field} 
                        className="px-3 py-2 text-center font-medium text-slate-600 border-b border-slate-200 capitalize cursor-pointer hover:bg-slate-100 select-none"
                        onClick={() => handleSort('_total')}
                      >
                        <div className="flex items-center justify-center gap-1">
                          {v.field} ({v.aggregation})
                          {sortColumn === '_total' && (
                            <span className="text-[10px]">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                    ))
                  ) : (
                    // Show column dimension values as headers
                    pivotResult.col_headers.map(col => (
                      <th 
                        key={col} 
                        className="px-3 py-2 text-center font-medium text-slate-600 border-b border-slate-200 cursor-pointer hover:bg-slate-100 select-none"
                        onClick={() => handleSort(col)}
                      >
                        <div className="flex items-center justify-center gap-1">
                          {col === '_total' ? (config.values.length === 1 ? `${config.values[0].field} (${config.values[0].aggregation})` : 'Total') : col}
                          {sortColumn === col && (
                            <span className="text-[10px]">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                          )}
                        </div>
                      </th>
                    ))
                  )}
                  {/* Grand Total Column Header */}
                  {config?.showGrandTotalColumn && config.columns.length > 0 && (
                    <th 
                      className="px-3 py-2 text-center font-medium text-slate-700 border-b border-slate-200 bg-slate-100 cursor-pointer hover:bg-slate-200 select-none"
                      onClick={() => handleSort('_grand_total')}
                    >
                      <div className="flex items-center justify-center gap-1">
                        Grand Total
                        {sortColumn === '_grand_total' && (
                          <span className="text-[10px]">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {/* Case 1: No rows, has columns, multiple values → each value is a row */}
                {config.rows.length === 0 && config.columns.length > 0 && config.values.length > 1 ? (
                  config.values.map((v, vIdx) => (
                    <tr key={v.field} className={vIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                      <td className="px-3 py-2 font-medium text-slate-700 border-r border-slate-100">
                        {v.field} <span className="text-slate-400 text-[10px]">({v.aggregation})</span>
                      </td>
                      {pivotResult.col_headers.map(col => {
                        const cell = getCell(cellMap, '_total', col);
                        const value = cell?.values[v.field];
                        return (
                          <td key={col} className="px-3 py-2 text-center text-slate-600">
                            {value != null ? (typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value)) : '-'}
                          </td>
                        );
                      })}
                    </tr>
                  ))
                ) : (
                  /* Case 2: Normal row-based rendering with subtotals support */
                  (() => {
                    const rows = sortedRowHeaders;
                    const showSubtotals = config?.showSubtotals && config.rows.length > 1 && pivotResult.subtotals;
                    let lastGroup: string | null = null;
                    const output: JSX.Element[] = [];
                    
                    rows.forEach((row, rowIndex) => {
                      // Extract first-level group from composite key
                      const currentGroup = row.includes(' | ') ? row.split(' | ')[0] : row;
                      
                      // Insert subtotal row when group changes (except first row)
                      if (showSubtotals && lastGroup !== null && currentGroup !== lastGroup && pivotResult.subtotals?.[lastGroup]) {
                        const groupKey = lastGroup; // Capture for TypeScript
                        output.push(
                          <tr key={`subtotal-${groupKey}`} className="bg-indigo-50 font-medium border-t border-indigo-200">
                            <td className="px-3 py-2 text-indigo-700 border-r border-indigo-200">
                              <span className="text-[10px] uppercase">Subtotal: {groupKey}</span>
                            </td>
                            {config.columns.length === 0 && config.values.length > 1 ? (
                              config.values.map(v => (
                                <td key={v.field} className="px-3 py-2 text-center text-indigo-700">
                                  {pivotResult.subtotals?.[groupKey]?.[v.field] != null 
                                    ? (pivotResult.subtotals[groupKey][v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                    : '-'}
                                </td>
                              ))
                            ) : (
                              pivotResult.col_headers.map(col => (
                                <td key={col} className="px-3 py-2 text-center text-indigo-700">
                                  {config.values.map(v => (
                                    <div key={v.field} className="text-[10px]">
                                      {pivotResult.subtotals?.[groupKey]?.[v.field] != null 
                                        ? (pivotResult.subtotals[groupKey][v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                        : '-'}
                                    </div>
                                  ))}
                                </td>
                              ))
                            )}
                            {config?.showGrandTotalColumn && config.columns.length > 0 && (
                              <td className="px-3 py-2 text-center text-indigo-700 bg-indigo-100 border-l border-indigo-200">
                                {config.values.map(v => (
                                  <div key={v.field} className="text-[10px]">
                                    {pivotResult.subtotals?.[groupKey]?.[v.field] != null 
                                      ? (pivotResult.subtotals[groupKey][v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                      : '-'}
                                  </div>
                                ))}
                              </td>
                            )}
                          </tr>
                        );
                      }
                      lastGroup = currentGroup;
                      
                      // Normal data row
                      output.push(
                    <tr key={row} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                      {config.rows.length > 0 && (
                        <td className="px-3 py-2 font-medium text-slate-700 border-r border-slate-100">
                          {row === '_total' ? 'Total' : row}
                        </td>
                      )}
                      {config.columns.length === 0 && config.values.length > 1 ? (
                        // No columns - each value as a separate column with % support
                        config.values.map(v => {
                          const cell = getCell(cellMap, row, '_total');
                          const value = cell?.values[v.field];
                          const rowTotal = pivotResult.row_totals?.[row]?.[v.field];
                          const colTotal = columnTotals['_total']?.[v.field];
                          const grandTotal = pivotResult.totals[v.field];
                          return (
                            <td key={v.field} className="px-3 py-2 text-center text-slate-600">
                              {formatValue(value as number | null, v.showAs, rowTotal, colTotal, grandTotal)}
                            </td>
                          );
                        })
                      ) : config.values.length > 1 ? (
                        // Has columns AND multiple values - show each column, values stacked with labels
                        pivotResult.col_headers.map(col => {
                          const cell = getCell(cellMap, row, col);
                          return (
                            <td key={col} className="px-3 py-2 text-center text-slate-600">
                              {cell ? (
                                <div className="space-y-0.5">
                                  {config.values.map(v => {
                                    const value = cell.values[v.field];
                                    const rowTotal = pivotResult.row_totals?.[row]?.[v.field];
                                    const colTotal = columnTotals[col]?.[v.field];
                                    const grandTotal = pivotResult.totals[v.field];
                                    return (
                                      <div key={v.field} className="whitespace-nowrap text-[10px]">
                                        <span className="text-slate-400">{v.field}: </span>
                                        {formatValue(value as number | null, v.showAs, rowTotal, colTotal, grandTotal)}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : '-'}
                            </td>
                          );
                        })
                      ) : (
                        // Single value - simple render with % support
                        pivotResult.col_headers.map(col => {
                          const cell = getCell(cellMap, row, col);
                          const valueConfig = config.values[0];
                          const value = cell?.values[valueConfig?.field];
                          const rowTotal = pivotResult.row_totals?.[row]?.[valueConfig?.field];
                          const colTotal = columnTotals[col]?.[valueConfig?.field];
                          const grandTotal = pivotResult.totals[valueConfig?.field];
                          return (
                            <td key={col} className="px-3 py-2 text-center text-slate-600">
                              {formatValue(value as number | null, valueConfig?.showAs, rowTotal, colTotal, grandTotal)}
                            </td>
                          );
                        })
                      )}
                      {/* Grand Total Cell for this row */}
                      {config?.showGrandTotalColumn && config.columns.length > 0 && pivotResult.row_totals && (
                        <td className="px-3 py-2 text-center font-medium text-slate-700 bg-slate-50 border-l border-slate-200">
                          {config.values.length === 1 ? (
                            // Single value
                            pivotResult.row_totals[row]?.[config.values[0].field] != null 
                              ? (pivotResult.row_totals[row][config.values[0].field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                              : '-'
                          ) : (
                            // Multiple values - show each
                            <div className="space-y-0.5">
                              {config.values.map(v => (
                                <div key={v.field} className="whitespace-nowrap text-[10px]">
                                  <span className="text-slate-400">{v.field}: </span>
                                  {pivotResult.row_totals?.[row]?.[v.field] != null 
                                    ? (pivotResult.row_totals[row]![v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                    : '-'}
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                      );
                    });
                    
                    // Add final subtotal for last group
                    if (showSubtotals && lastGroup !== null && pivotResult.subtotals?.[lastGroup]) {
                      const finalGroupKey = lastGroup; // Capture for TypeScript
                      output.push(
                        <tr key={`subtotal-${finalGroupKey}-final`} className="bg-indigo-50 font-medium border-t border-indigo-200">
                          <td className="px-3 py-2 text-indigo-700 border-r border-indigo-200">
                            <span className="text-[10px] uppercase">Subtotal: {finalGroupKey}</span>
                          </td>
                          {config.columns.length === 0 && config.values.length > 1 ? (
                            config.values.map(v => (
                              <td key={v.field} className="px-3 py-2 text-center text-indigo-700">
                                {pivotResult.subtotals?.[finalGroupKey]?.[v.field] != null 
                                  ? (pivotResult.subtotals[finalGroupKey][v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                  : '-'}
                              </td>
                            ))
                          ) : (
                            pivotResult.col_headers.map(col => (
                              <td key={col} className="px-3 py-2 text-center text-indigo-700">
                                {config.values.map(v => (
                                  <div key={v.field} className="text-[10px]">
                                    {pivotResult.subtotals?.[finalGroupKey]?.[v.field] != null 
                                      ? (pivotResult.subtotals[finalGroupKey][v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                      : '-'}
                                  </div>
                                ))}
                              </td>
                            ))
                          )}
                          {config?.showGrandTotalColumn && config.columns.length > 0 && (
                            <td className="px-3 py-2 text-center text-indigo-700 bg-indigo-100 border-l border-indigo-200">
                              {config.values.map(v => (
                                <div key={v.field} className="text-[10px]">
                                  {pivotResult.subtotals?.[finalGroupKey]?.[v.field] != null 
                                    ? (pivotResult.subtotals[finalGroupKey][v.field] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                    : '-'}
                                </div>
                              ))}
                            </td>
                          )}
                        </tr>
                      );
                    }
                    
                    return output;
                  })()
                )}
                {/* Totals row - only show if at least one value has showTotal enabled */}
                {pivotResult.totals && Object.keys(pivotResult.totals).length > 0 && config.values.some(v => v.showTotal !== false) && (
                  <tr className="bg-slate-100 font-medium border-t-2 border-slate-300">
                    {(config.rows.length > 0 || (config.rows.length === 0 && config.values.length > 1)) && (
                      <td className="px-3 py-2 text-slate-700 border-r border-slate-200">
                        {config.values.length === 1 ? (
                          // Single value: show "Sum of Revenue" / "Avg of EPS" etc.
                          <span className="font-medium">
                            {(config.values[0].totalAggregation || config.values[0].aggregation) === 'none' 
                              ? `${config.values[0].field}` 
                              : `${(config.values[0].totalAggregation || config.values[0].aggregation).charAt(0).toUpperCase() + (config.values[0].totalAggregation || config.values[0].aggregation).slice(1)} of ${config.values[0].field}`}
                          </span>
                        ) : (
                          // Multiple values: show "Totals" with breakdown
                          <div>
                            <span className="font-medium">Totals</span>
                            <div className="text-[9px] text-slate-400 font-normal mt-0.5">
                              {config.values.filter(v => v.showTotal !== false).map(v => (
                                <span key={v.field} className="block">
                                  {(v.totalAggregation || v.aggregation) === 'none' ? v.field : `${v.totalAggregation || v.aggregation}(${v.field})`}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </td>
                    )}
                    {config.columns.length === 0 && config.values.length > 1 ? (
                      // No columns - each value as separate column
                      config.values.map(v => (
                        <td key={v.field} className="px-3 py-2 text-center text-slate-700">
                          {v.showTotal === false ? (
                            <span className="text-slate-300">-</span>
                          ) : pivotResult.totals[v.field] != null ? (
                            pivotResult.totals[v.field].toLocaleString(undefined, { maximumFractionDigits: 2 })
                          ) : '-'}
                        </td>
                      ))
                    ) : config.rows.length === 0 && config.columns.length > 0 && config.values.length > 1 ? (
                      // No rows, has columns, multiple values (values as rows)
                      pivotResult.col_headers.map(col => {
                        // Use column-specific totals, not global totals
                        return (
                          <td key={col} className="px-3 py-2 text-center text-slate-700">
                            {config.values.filter(v => v.showTotal !== false).map(v => (
                              <div key={v.field} className="text-[10px]">
                                {columnTotals[col]?.[v.field] != null 
                                  ? columnTotals[col][v.field].toLocaleString(undefined, { maximumFractionDigits: 0 })
                                  : '-'}
                              </div>
                            ))}
                          </td>
                        );
                      })
                    ) : (
                      // Has rows and possibly columns - use column-specific totals
                      pivotResult.col_headers.map(col => (
                        <td key={col} className="px-3 py-2 text-center text-slate-700">
                          {config.values.filter(v => v.showTotal !== false).map(v => (
                            <div key={v.field} className="whitespace-nowrap text-[10px]">
                              <span className="text-slate-500">{v.field}: </span>
                              {columnTotals[col]?.[v.field] != null 
                                ? columnTotals[col][v.field].toLocaleString(undefined, { maximumFractionDigits: 2 }) 
                                : '-'}
                            </div>
                          ))}
                        </td>
                      ))
                    )}
                    {/* Grand Total for totals row - overall grand total */}
                    {config?.showGrandTotalColumn && config.columns.length > 0 && (
                      <td className="px-3 py-2 text-center font-bold text-slate-800 bg-slate-200 border-l border-slate-300">
                        {config.values.filter(v => v.showTotal !== false).map(v => (
                          <div key={v.field} className="whitespace-nowrap text-[10px]">
                            {config.values.length > 1 && <span className="text-slate-500">{v.field}: </span>}
                            {pivotResult.totals[v.field] != null 
                              ? pivotResult.totals[v.field].toLocaleString(undefined, { maximumFractionDigits: 2 }) 
                              : '-'}
                          </div>
                        ))}
                      </td>
                    )}
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {fades.top    && <div className="pointer-events-none absolute left-0 h-10 z-10" style={{ top: headerHeight, right: sbY, background: 'linear-gradient(to bottom, white, transparent)' }} />}
      {fades.right  && <div className="pointer-events-none absolute z-10" style={{ top: headerHeight, right: sbY, bottom: sbX, width: 48, background: 'linear-gradient(to left, white, transparent)' }} />}
      {fades.bottom && <div className="pointer-events-none absolute left-0 h-10 z-10" style={{ bottom: sbX, right: sbY, background: 'linear-gradient(to top, white, transparent)' }} />}
      {fades.left   && <div className="pointer-events-none absolute left-0 z-10" style={{ top: headerHeight, bottom: sbX, width: 48, background: 'linear-gradient(to right, white, transparent)' }} />}
    </div>
  );
}
