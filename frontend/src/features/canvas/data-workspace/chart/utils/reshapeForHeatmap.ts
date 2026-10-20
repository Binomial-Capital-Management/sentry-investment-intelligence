/**
 * reshapeForHeatmap - Converts wide OHLC data to long form for heatmap visualization
 * 
 * Transforms:
 *   [{date: "2024-01-01", open: 480, high: 485, low: 478, close: 482}, ...]
 * 
 * To:
 *   [
 *     {date: "2024-01-01", field: "open", value: 480},
 *     {date: "2024-01-01", field: "high", value: 485},
 *     {date: "2024-01-01", field: "low", value: 478},
 *     {date: "2024-01-01", field: "close", value: 482},
 *     {date: "2024-01-02", field: "open", value: 481},
 *     ...
 *   ]
 * 
 * This allows heatmaps with X=date, Y=field_type, Z=value
 */

export function reshapeOHLCForHeatmap(
  data: Record<string, any>[],
  dateField: string,
  valueFields: string[] // e.g., ['open', 'high', 'low', 'close']
): Record<string, any>[] {
  const reshaped: Record<string, any>[] = [];
  
  for (const row of data) {
    const dateValue = row[dateField];
    if (!dateValue) continue;
    
    for (const field of valueFields) {
      const value = row[field];
      if (value !== undefined && value !== null) {
        reshaped.push({
          [dateField]: dateValue,
          field_type: field,
          value: typeof value === 'number' ? value : parseFloat(value),
        });
      }
    }
  }
  
  return reshaped;
}

/**
 * Auto-detect if data needs reshaping for heatmap
 * Returns true if data appears to be wide-format time series
 */
export function shouldReshapeForHeatmap(
  data: Record<string, any>[],
  xField: string,
  yField: string,
  zField: string
): boolean {
  if (data.length === 0) return false;
  
  // Check if Y-field values are all unique (indicates time series, not categories)
  const yValues = data.map(d => d[yField]).filter(v => v !== undefined);
  const uniqueY = new Set(yValues);
  
  // If almost all Y values are unique AND Y is numeric, likely a sparse matrix
  const uniqueRatio = uniqueY.size / yValues.length;
  const yIsNumeric = yValues.every(v => typeof v === 'number');
  
  // Also check if X looks like dates
  const xSample = data[0][xField];
  const xIsDate = typeof xSample === 'string' && /^\d{4}-\d{2}/.test(xSample);
  
  return uniqueRatio > 0.9 && yIsNumeric && xIsDate;
}

