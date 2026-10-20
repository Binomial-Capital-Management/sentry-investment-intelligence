/**
 * Shared normalization utility for BoxPlot and Violin charts
 * Used to compare distributions with different magnitudes
 */

export type NormalizeMode = 'none' | 'zscore' | 'minmax' | 'percent';

/**
 * Normalize an array of values using the specified mode
 * @param values - Array of values (may include non-numeric values)
 * @param mode - Normalization mode
 * @returns Array with normalized numeric values, non-numeric values unchanged
 */
export function normalizeValues(
  values: any[],
  mode: NormalizeMode
): any[] {
  if (mode === 'none') return values;

  // Extract numeric values for stats calculation
  const numericValues = values.filter(
    (v): v is number => typeof v === 'number' && !isNaN(v)
  );

  if (numericValues.length === 0) return values;

  // Calculate statistics
  const mean = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
  const min = Math.min(...numericValues);
  const max = Math.max(...numericValues);
  const std = Math.sqrt(
    numericValues.reduce((sum, v) => sum + (v - mean) ** 2, 0) / numericValues.length
  );

  // Apply normalization
  return values.map(v => {
    if (typeof v !== 'number' || isNaN(v)) return v;

    switch (mode) {
      case 'zscore':
        return std > 0 ? (v - mean) / std : 0;
      case 'minmax':
        return max > min ? ((v - min) / (max - min)) * 100 : 50;
      case 'percent':
        return mean !== 0 ? ((v - mean) / Math.abs(mean)) * 100 : 0;
      default:
        return v;
    }
  });
}
