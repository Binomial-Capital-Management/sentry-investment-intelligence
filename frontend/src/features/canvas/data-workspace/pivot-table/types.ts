import { PivotValueConfig } from '../stores/dataWorkspaceStore';

export interface FieldInfo {
  name: string;
  type: 'numeric' | 'categorical' | 'datetime' | 'text' | 'boolean' | 'unknown';
  can_aggregate: boolean;
  can_group: boolean;
  unique_count: number;
  null_count: number;
  sample_values: any[];
}

export interface PivotCell {
  row_key: string;
  col_key: string;
  values: Record<string, number | null>;
}

export interface PivotResult {
  row_headers: string[];
  col_headers: string[];
  cells: PivotCell[];
  totals: Record<string, number>;
  row_totals?: Record<string, Record<string, number>>;
  subtotals?: Record<string, Record<string, number>>;
}

export type CellMap = Map<string, PivotCell>;

export function buildCellMap(cells: PivotCell[]): CellMap {
  const map = new Map<string, PivotCell>();
  for (const cell of cells) map.set(`${cell.row_key}::${cell.col_key}`, cell);
  return map;
}

export function getCell(map: CellMap, row: string, col: string): PivotCell | undefined {
  return map.get(`${row}::${col}`);
}

export interface DatasetRef {
  symbol: string;
  endpoint: string;
  params: Record<string, any>;
}

export interface DescriptiveStats {
  field: string;
  count: number;
  mean: number | null;
  median: number | null;
  mode: number | null;
  std: number | null;
  variance: number | null;
  min: number | null;
  max: number | null;
  range: number | null;
  q1: number | null;
  q2: number | null;
  q3: number | null;
  iqr: number | null;
  skewness: number | null;
  kurtosis: number | null;
}

export interface CorrelationResult {
  fields: string[];
  matrix: number[][];
  p_values: number[][];
}

export interface StatisticalTestResult {
  test_type: string;
  test_name: string;
  statistic: number;
  p_value: number;
  degrees_of_freedom?: number;
  interpretation: string;
  significant_at_05: boolean;
  significant_at_01: boolean;
  additional_info?: Record<string, any>;
}

export const AGGREGATION_OPTIONS: { value: PivotValueConfig['aggregation']; label: string; description?: string }[] = [
  { value: 'none', label: 'Value', description: 'Raw value (no aggregation)' },
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'count', label: 'Count' },
  { value: 'min', label: 'Min' },
  { value: 'max', label: 'Max' },
  { value: 'first', label: 'First', description: 'First value in group' },
  { value: 'last', label: 'Last', description: 'Last value in group' },
  { value: 'median', label: 'Median' },
  { value: 'stddev', label: 'Std Dev' },
];

export const TEST_OPTIONS = [
  { value: 'ttest_one', label: 'One-Sample T-Test', description: 'Compare sample mean to known value' },
  { value: 'ttest_two', label: 'Two-Sample T-Test', description: 'Compare means of two groups' },
  { value: 'ttest_paired', label: 'Paired T-Test', description: 'Compare paired observations' },
  { value: 'anova_one', label: 'One-Way ANOVA', description: 'Compare means across 3+ groups' },
  { value: 'chi_square_independence', label: 'Chi-Square Independence', description: 'Test association between categoricals' },
  { value: 'chi_square_goodness', label: 'Chi-Square Goodness of Fit', description: 'Test observed vs expected frequency' },
  { value: 'shapiro_wilk', label: 'Shapiro-Wilk', description: 'Test for normality' },
  { value: 'kolmogorov_smirnov', label: 'Kolmogorov-Smirnov', description: 'Test normality / distribution fit' },
];
