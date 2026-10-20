/**
 * Aggregation Utilities
 *
 * Functions for aggregating numerical data, used by the Smart Join system
 * to collapse fine-grained data (daily) into coarser periods (quarterly).
 */

// ============================================================================
// TYPES
// ============================================================================

export type AggMethod = 'avg' | 'sum' | 'first' | 'last' | 'min' | 'max' | 'count';

// ============================================================================
// AGGREGATION FUNCTIONS
// ============================================================================

/**
 * Get the default aggregation method for a field based on its name.
 *
 * Uses common conventions:
 * - open, openPrice → first (start of period)
 * - close, price → last (end of period)
 * - high → max
 * - low → min
 * - volume, amount, quantity, count → sum
 * - ratio, pe, pb, yield → avg
 * - unknown → last (safe default)
 *
 * @param fieldName - The name of the field
 * @returns The recommended aggregation method
 *
 * @example
 * getDefaultAggregation('close')    // => 'last'
 * getDefaultAggregation('volume')   // => 'sum'
 * getDefaultAggregation('peRatio')  // => 'avg'
 */
export function getDefaultAggregation(fieldName: string): AggMethod {
  const lower = fieldName.toLowerCase();

  // Opening values - check FIRST to handle "openPrice" correctly
  if (lower.startsWith('open') || lower.includes('_open') || lower === 'open') {
    return 'first';
  }

  // Price/close fields - use last (end of period)
  if (
    lower.includes('close') ||
    lower === 'price' ||
    (lower.includes('price') && !lower.includes('ratio'))
  ) {
    return 'last';
  }

  // High values - use max
  if (lower.includes('high')) {
    return 'max';
  }

  // Low values - use min
  if (lower.includes('low')) {
    return 'min';
  }

  // Volume/quantity fields - use sum
  if (
    lower.includes('volume') ||
    lower.includes('amount') ||
    lower.includes('quantity') ||
    lower.includes('count')
  ) {
    return 'sum';
  }

  // Ratio fields - use average (check after price to handle "priceToBookRatio")
  if (
    lower.includes('ratio') ||
    lower.includes('pe') ||
    lower.includes('pb') ||
    lower.includes('yield')
  ) {
    return 'avg';
  }

  // Default to last for unknown fields
  return 'last';
}

/**
 * Apply an aggregation method to a list of values.
 *
 * Handles null/undefined values gracefully by filtering them out.
 * Returns null if no valid values remain after filtering.
 *
 * @param values - Array of numbers (may contain nulls)
 * @param method - Aggregation method to apply
 * @returns Aggregated result, or null if no valid values
 *
 * @example
 * applyAggregation([10, 20, 30], 'avg')  // => 20
 * applyAggregation([10, null, 30], 'sum') // => 40
 * applyAggregation([], 'avg')            // => null
 */
export function applyAggregation(
  values: (number | null | undefined)[],
  method: AggMethod
): number | null {
  // Filter out null, undefined, and NaN values
  const cleanValues = values.filter(
    (v): v is number => v !== null && v !== undefined && !isNaN(v)
  );

  if (cleanValues.length === 0) return null;

  switch (method) {
    case 'avg':
      return cleanValues.reduce((a, b) => a + b, 0) / cleanValues.length;
    case 'sum':
      return cleanValues.reduce((a, b) => a + b, 0);
    case 'first':
      return cleanValues[0];
    case 'last':
      return cleanValues[cleanValues.length - 1];
    case 'min':
      return Math.min(...cleanValues);
    case 'max':
      return Math.max(...cleanValues);
    case 'count':
      return cleanValues.length;
    default:
      return null;
  }
}
