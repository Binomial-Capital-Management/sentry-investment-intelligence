/**
 * useRegression - Fetches regression analysis from backend
 * 
 * Returns regression line data, equation, and R² for overlay on scatter charts
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { API_BASE } from '@/services/api';
import type { RegressionConfig, RegressionType } from '../chartTypes/ScatterChart';

interface RegressionResult {
  lineX: number[];
  lineY: number[];
  equation: string;
  rSquared: number;
  type: RegressionType;
}

interface RegressionState {
  results: RegressionResult[];
  loading: boolean;
  error: string | null;
}

interface UseRegressionParams {
  enabled: boolean;
  config: RegressionConfig | undefined;
  data: any[];
  xAxis: string;
  ySeries: { field: string; label?: string; color?: string }[];
}

export function useRegression({
  enabled,
  config,
  data,
  xAxis,
  ySeries,
}: UseRegressionParams): RegressionState {
  const [results, setResults] = useState<RegressionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Convert x value to number (handles dates by converting to timestamps)
  const parseXValue = useCallback((val: any): number | null => {
    if (val === null || val === undefined) return null;
    
    // Already a number
    if (typeof val === 'number') {
      return isFinite(val) ? val : null;
    }
    
    // String - could be date or numeric string
    if (typeof val === 'string') {
      // Check if it looks like a date (YYYY-MM-DD or similar)
      if (val.match(/^\d{4}-\d{2}-\d{2}/)) {
        const ts = new Date(val).getTime();
        return isFinite(ts) ? ts : null;
      }
      // Try parsing as number
      const num = Number(val);
      return isFinite(num) ? num : null;
    }
    
    // Date object
    if (val instanceof Date) {
      const ts = val.getTime();
      return isFinite(ts) ? ts : null;
    }
    
    return null;
  }, []);

  // Extract numeric x/y pairs for each series
  const seriesData = useMemo(() => {
    if (!enabled || !config?.enabled || data.length === 0) return [];

    return ySeries.map((series) => {
      const pairs: { x: number; y: number }[] = [];
      data.forEach((row) => {
        const x = parseXValue(row[xAxis]);
        const y = Number(row[series.field]);
        if (x !== null && !isNaN(y) && isFinite(y)) {
          pairs.push({ x, y });
        }
      });
      return {
        field: series.field,
        label: series.label || series.field,
        color: series.color,
        x: pairs.map((p) => p.x),
        y: pairs.map((p) => p.y),
      };
    });
  }, [enabled, config?.enabled, data, xAxis, ySeries, parseXValue]);

  // Fetch regression for each series
  useEffect(() => {
    if (!enabled || !config?.enabled || seriesData.length === 0) {
      setResults([]);
      return;
    }

    let cancelled = false;

    const fetchRegressions = async () => {
      setLoading(true);
      setError(null);

      const newResults: RegressionResult[] = [];

      for (const series of seriesData) {
        if (series.x.length < 2) continue;

        try {
          const response = await fetch(`${API_BASE}/api/canvas/chart/regression`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              x: series.x,
              y: series.y,
              regression_type: config.type,
              degree: config.degree,
            }),
          });

          if (!response.ok) {
            console.warn(`Regression failed for ${series.field}:`, response.status);
            continue;
          }

          const result = await response.json();
          
          if (!cancelled) {
            newResults.push({
              lineX: result.line_x,
              lineY: result.line_y,
              equation: result.equation,
              rSquared: result.r_squared,
              type: result.regression_type,
            });
          }
        } catch (err) {
          console.error(`Failed to compute regression for ${series.field}:`, err);
        }
      }

      if (!cancelled) {
        setResults(newResults);
        setLoading(false);
      }
    };

    fetchRegressions();
    return () => { cancelled = true; };
  }, [enabled, config?.enabled, config?.type, config?.degree, seriesData]);

  return { results, loading, error };
}

// Check if values look like timestamps (large numbers typical of JS timestamps)
function looksLikeTimestamp(val: number): boolean {
  // JS timestamps are typically 13 digits (milliseconds since 1970)
  // Valid range: 1970-01-01 to ~2100
  return val > 946684800000 && val < 4102444800000;
}

// Convert timestamp to ISO date string for Plotly
function timestampToDateString(ts: number): string {
  return new Date(ts).toISOString().split('T')[0];
}

// Build Plotly traces for regression lines
export function buildRegressionTraces(
  results: RegressionResult[],
  config: RegressionConfig | undefined,
  seriesColors: string[]
): any[] {
  if (!config?.enabled || results.length === 0) return [];

  const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899'];

  return results.map((result, idx) => {
    const color = seriesColors[idx] || COLORS[idx % COLORS.length];
    
    // Check if x values are timestamps and convert back to dates
    let xValues: (number | string)[] = result.lineX;
    if (result.lineX.length > 0 && looksLikeTimestamp(result.lineX[0])) {
      xValues = result.lineX.map(timestampToDateString);
    }
    
    // Build name with equation and R²
    let name = `Regression`;
    if (config.showEquation && config.showR2) {
      name = `${result.equation} (R²=${result.rSquared.toFixed(4)})`;
    } else if (config.showEquation) {
      name = result.equation;
    } else if (config.showR2) {
      name = `R²=${result.rSquared.toFixed(4)}`;
    }

    return {
      x: xValues,
      y: result.lineY,
      type: 'scatter' as const,
      mode: 'lines',
      name,
      line: {
        color: config.lineColor || color,
        width: 2.5,
        dash: 'solid',
      },
      hoverinfo: 'name+y',
    };
  });
}

