/**
 * pivotToMatrix - Converts long-form data to a matrix format for heatmaps and 3D surfaces
 * 
 * Input: Array of {xField: value, yField: value, zField: value} rows
 * Output: { x: unique X values, y: unique Y values, z: 2D matrix where z[yIdx][xIdx] = value }
 */

export interface MatrixResult {
  x: (string | number)[];  // Unique X values (columns)
  y: (string | number)[];  // Unique Y values (rows)
  z: (number | null)[][];  // 2D array where z[yIndex][xIndex] = value
  xLabel: string;
  yLabel: string;
  zLabel: string;
}

export interface PivotOptions {
  /** How to handle multiple values for same (x,y) pair */
  aggregation?: 'first' | 'last' | 'sum' | 'mean' | 'min' | 'max';
  /** Sort X values */
  sortX?: boolean;
  /** Sort Y values */
  sortY?: boolean;
  /** Value to use for missing (x,y) combinations */
  fillValue?: number | null;
}

/**
 * Convert long-form data to matrix format
 */
export function pivotToMatrix(
  data: Record<string, any>[],
  xField: string,
  yField: string,
  zField: string,
  options: PivotOptions = {}
): MatrixResult {
  const {
    aggregation = 'first',
    sortX = true,
    sortY = true,
    fillValue = null,
  } = options;

  if (!data || data.length === 0) {
    return { x: [], y: [], z: [], xLabel: xField, yLabel: yField, zLabel: zField };
  }

  // Extract unique X and Y values
  const xSet = new Set<string | number>();
  const ySet = new Set<string | number>();
  
  // Map of "x|y" -> array of z values (for aggregation)
  const valueMap = new Map<string, number[]>();

  for (const row of data) {
    const xVal = row[xField];
    const yVal = row[yField];
    const zVal = row[zField];

    if (xVal === undefined || xVal === null || yVal === undefined || yVal === null) {
      continue;
    }

    xSet.add(xVal);
    ySet.add(yVal);

    if (typeof zVal === 'number' && !isNaN(zVal)) {
      const key = `${xVal}|${yVal}`;
      if (!valueMap.has(key)) {
        valueMap.set(key, []);
      }
      valueMap.get(key)!.push(zVal);
    }
  }

  // Convert to sorted arrays
  let xValues = Array.from(xSet);
  let yValues = Array.from(ySet);

  if (sortX) {
    xValues = smartSort(xValues);
  }
  if (sortY) {
    yValues = smartSort(yValues);
  }

  // Create index maps for fast lookup
  const xIndex = new Map<string | number, number>();
  const yIndex = new Map<string | number, number>();
  xValues.forEach((v, i) => xIndex.set(v, i));
  yValues.forEach((v, i) => yIndex.set(v, i));

  // Build the Z matrix
  const z: (number | null)[][] = [];
  for (let yi = 0; yi < yValues.length; yi++) {
    const row: (number | null)[] = [];
    for (let xi = 0; xi < xValues.length; xi++) {
      const key = `${xValues[xi]}|${yValues[yi]}`;
      const values = valueMap.get(key);
      
      if (!values || values.length === 0) {
        row.push(fillValue);
      } else {
        row.push(aggregate(values, aggregation));
      }
    }
    z.push(row);
  }

  return {
    x: xValues,
    y: yValues,
    z,
    xLabel: xField,
    yLabel: yField,
    zLabel: zField,
  };
}

/**
 * Smart sort that handles mixed types (numbers vs strings, dates)
 */
function smartSort(values: (string | number)[]): (string | number)[] {
  // Check if all values are numbers
  const allNumbers = values.every(v => typeof v === 'number');
  if (allNumbers) {
    return [...values].sort((a, b) => (a as number) - (b as number));
  }

  // Check if all values look like dates
  const allDates = values.every(v => 
    typeof v === 'string' && /^\d{4}-\d{2}(-\d{2})?/.test(v)
  );
  if (allDates) {
    return [...values].sort((a, b) => 
      new Date(a as string).getTime() - new Date(b as string).getTime()
    );
  }

  // Default: string sort
  return [...values].sort((a, b) => String(a).localeCompare(String(b)));
}

/**
 * Aggregate multiple values
 */
function aggregate(values: number[], method: PivotOptions['aggregation']): number {
  if (values.length === 0) return 0;
  
  switch (method) {
    case 'first':
      return values[0];
    case 'last':
      return values[values.length - 1];
    case 'sum':
      return values.reduce((a, b) => a + b, 0);
    case 'mean':
      return values.reduce((a, b) => a + b, 0) / values.length;
    case 'min':
      return Math.min(...values);
    case 'max':
      return Math.max(...values);
    default:
      return values[0];
  }
}

/**
 * Create a symmetric correlation-style matrix from data
 * Useful when X and Y fields are the same (e.g., ticker correlation)
 */
export function createSymmetricMatrix(
  data: Record<string, any>[],
  categoryField: string,
  valueField: string
): MatrixResult {
  // This is a placeholder - actual correlation computation would be done on backend
  // This just formats pre-computed correlation data into a symmetric matrix
  return pivotToMatrix(data, categoryField, categoryField, valueField, {
    aggregation: 'mean',
    sortX: true,
    sortY: true,
    fillValue: null,
  });
}

