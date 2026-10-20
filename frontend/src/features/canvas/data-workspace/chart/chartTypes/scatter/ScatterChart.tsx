/**
 * Scatter Chart - correlation and distribution visualization
 * Includes client-side regression fitting
 */

import { ChartTypeDefinition } from '../types';

// Regression types
export type RegressionType = 'linear' | 'polynomial' | 'exponential' | 'logarithmic';

// Regression configuration
export interface RegressionConfig {
  enabled: boolean;
  type: RegressionType;
  degree: number;
  showEquation: boolean;
  showR2: boolean;
  lineColor?: string;
}

// Scatter-specific options
export interface ScatterChartOptions {
  markerSize: number;
  markerOpacity: number;
  markerShape: 'circle' | 'square' | 'diamond' | 'cross' | 'x';
  showTrendline: boolean;
  jitter: boolean;
  regression: RegressionConfig;
}

const COLORS = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6', '#F97316', '#EF4444'];

const SHAPE_MAP: Record<string, string> = {
  circle: 'circle',
  square: 'square',
  diamond: 'diamond',
  cross: 'cross',
  x: 'x',
};

// ─── Regression Math ─────────────────────────────────────────────────────────

interface RegressionResult {
  lineX: number[];
  lineY: number[];
  equation: string;
  rSquared: number;
}

function computeRSquared(yActual: number[], yPredicted: number[]): number {
  const mean = yActual.reduce((a, b) => a + b, 0) / yActual.length;
  const ssTotal = yActual.reduce((sum, y) => sum + (y - mean) ** 2, 0);
  const ssResidual = yActual.reduce((sum, y, i) => sum + (y - yPredicted[i]) ** 2, 0);
  if (ssTotal === 0) return 1;
  return 1 - ssResidual / ssTotal;
}

function linearRegression(x: number[], y: number[], isDateAxis: boolean = false): RegressionResult {
  const n = x.length;
  const xMin = Math.min(...x);
  const xMax = Math.max(...x);
  const xRange = xMax - xMin || 1;
  
  // Normalize x to prevent numerical issues with large timestamps
  const xNorm = x.map((xi) => (xi - xMin) / xRange);
  
  const sumX = xNorm.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumXY = xNorm.reduce((sum, xi, i) => sum + xi * y[i], 0);
  const sumX2 = xNorm.reduce((sum, xi) => sum + xi * xi, 0);
  
  const denom = n * sumX2 - sumX * sumX;
  const mNorm = denom !== 0 ? (n * sumXY - sumX * sumY) / denom : 0;
  const bNorm = (sumY - mNorm * sumX) / n;
  
  // Generate line points in original x space
  const lineX = Array.from({ length: 50 }, (_, i) => xMin + (i / 49) * xRange);
  const lineY = lineX.map((xi) => mNorm * ((xi - xMin) / xRange) + bNorm);
  
  const yPred = xNorm.map((xi) => mNorm * xi + bNorm);
  const rSquared = computeRSquared(y, yPred);
  
  // Calculate slope in meaningful units
  let equation: string;
  if (isDateAxis) {
    // Convert slope to "per day" (milliseconds per day = 86400000)
    const msPerDay = 86400000;
    const slopePerDay = mNorm * (msPerDay / xRange) * (xRange / msPerDay);
    const totalChange = mNorm; // Total change over the range
    const days = xRange / msPerDay;
    const avgDailyChange = totalChange / days;
    
    const sign = avgDailyChange >= 0 ? '+' : '';
    equation = `slope: ${sign}${avgDailyChange.toFixed(2)}/day`;
  } else {
    // Regular numeric x-axis - show actual slope
    const actualSlope = mNorm / xRange * (xMax - xMin);
    const sign = bNorm >= 0 ? '+' : '-';
    equation = `y = ${actualSlope.toFixed(4)}x ${sign} ${Math.abs(bNorm).toFixed(2)}`;
  }
  
  return { lineX, lineY, equation, rSquared };
}

function polynomialRegression(x: number[], y: number[], degree: number, isDateAxis: boolean = false): RegressionResult {
  const n = x.length;
  const xMin = Math.min(...x);
  const xMax = Math.max(...x);
  const xRange = xMax - xMin || 1;
  
  // Normalize x to [0, 1] to prevent numerical issues
  const xNorm = x.map((xi) => (xi - xMin) / xRange);
  
  // Build Vandermonde matrix
  const X: number[][] = xNorm.map((xi) => 
    Array.from({ length: degree + 1 }, (_, p) => xi ** p)
  );
  
  // Solve normal equations: (X'X)^-1 X'y
  const XtX: number[][] = Array.from({ length: degree + 1 }, (_, i) =>
    Array.from({ length: degree + 1 }, (_, j) =>
      X.reduce((sum, row) => sum + row[i] * row[j], 0)
    )
  );
  const Xty: number[] = Array.from({ length: degree + 1 }, (_, i) =>
    X.reduce((sum, row, k) => sum + row[i] * y[k], 0)
  );
  
  const coeffs = solveLinearSystem(XtX, Xty);
  
  // Generate line points in original x space
  const lineX = Array.from({ length: 100 }, (_, i) => xMin + (i / 99) * xRange);
  const lineY = lineX.map((xi) => {
    const xiNorm = (xi - xMin) / xRange;
    return coeffs.reduce((sum, c, p) => sum + c * (xiNorm ** p), 0);
  });
  
  // R²
  const yPred = xNorm.map((xi) => coeffs.reduce((sum, c, p) => sum + c * (xi ** p), 0));
  const rSquared = computeRSquared(y, yPred);
  
  // Simplified equation display
  const equation = `Poly(${degree})`;
  
  return { lineX, lineY, equation, rSquared };
}

function exponentialRegression(x: number[], y: number[], isDateAxis: boolean = false): RegressionResult {
  // y = a * e^(bx)  =>  ln(y) = ln(a) + bx
  const validIdx = y.map((yi, i) => yi > 0 ? i : -1).filter((i) => i >= 0);
  if (validIdx.length < 2) {
    return { lineX: [], lineY: [], equation: 'Need positive y', rSquared: 0 };
  }
  
  const xMin = Math.min(...x);
  const xMax = Math.max(...x);
  const xRange = xMax - xMin || 1;
  
  // Normalize x
  const xValid = validIdx.map((i) => (x[i] - xMin) / xRange);
  const yValid = validIdx.map((i) => y[i]);
  const lnY = yValid.map((yi) => Math.log(yi));
  
  // Linear regression on normalized x vs ln(y)
  const n = xValid.length;
  const sumX = xValid.reduce((a, b) => a + b, 0);
  const sumY = lnY.reduce((a, b) => a + b, 0);
  const sumXY = xValid.reduce((sum, xi, i) => sum + xi * lnY[i], 0);
  const sumX2 = xValid.reduce((sum, xi) => sum + xi * xi, 0);
  
  const denom = n * sumX2 - sumX * sumX;
  const bNorm = denom !== 0 ? (n * sumXY - sumX * sumY) / denom : 0;
  const lnA = (sumY - bNorm * sumX) / n;
  const a = Math.exp(lnA);
  
  // Generate line points
  const lineX = Array.from({ length: 100 }, (_, i) => xMin + (i / 99) * xRange);
  const lineY = lineX.map((xi) => {
    const xiNorm = (xi - xMin) / xRange;
    return a * Math.exp(bNorm * xiNorm);
  });
  
  // R²
  const yPred = xValid.map((xi) => a * Math.exp(bNorm * xi));
  const rSquared = computeRSquared(yValid, yPred);
  
  const equation = `Exponential`;
  
  return { lineX, lineY, equation, rSquared };
}

function logarithmicRegression(x: number[], y: number[], isDateAxis: boolean = false): RegressionResult {
  // y = a * ln(x_norm) + b, where x_norm is normalized to [1, e] range
  const xMin = Math.min(...x);
  const xMax = Math.max(...x);
  const xRange = xMax - xMin || 1;
  
  // Normalize x to [1, e] range for ln to work nicely
  const xNorm = x.map((xi) => 1 + ((xi - xMin) / xRange) * (Math.E - 1));
  const lnX = xNorm.map((xi) => Math.log(xi));
  
  // Linear regression on ln(x_norm) vs y
  const n = lnX.length;
  const sumX = lnX.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumXY = lnX.reduce((sum, xi, i) => sum + xi * y[i], 0);
  const sumX2 = lnX.reduce((sum, xi) => sum + xi * xi, 0);
  
  const denom = n * sumX2 - sumX * sumX;
  const a = denom !== 0 ? (n * sumXY - sumX * sumY) / denom : 0;
  const b = (sumY - a * sumX) / n;
  
  // Generate line points in original x space
  const lineX = Array.from({ length: 100 }, (_, i) => xMin + (i / 99) * xRange);
  const lineY = lineX.map((xi) => {
    const xiNorm = 1 + ((xi - xMin) / xRange) * (Math.E - 1);
    return a * Math.log(xiNorm) + b;
  });
  
  // R²
  const yPred = lnX.map((xi) => a * xi + b);
  const rSquared = computeRSquared(y, yPred);
  
  const equation = `Logarithmic`;
  
  return { lineX, lineY, equation, rSquared };
}

function solveLinearSystem(A: number[][], b: number[]): number[] {
  const n = A.length;
  const augmented = A.map((row, i) => [...row, b[i]]);
  
  // Forward elimination
  for (let i = 0; i < n; i++) {
    let maxRow = i;
    for (let k = i + 1; k < n; k++) {
      if (Math.abs(augmented[k][i]) > Math.abs(augmented[maxRow][i])) {
        maxRow = k;
      }
    }
    [augmented[i], augmented[maxRow]] = [augmented[maxRow], augmented[i]];
    
    if (Math.abs(augmented[i][i]) < 1e-10) continue;
    
    for (let k = i + 1; k < n; k++) {
      const factor = augmented[k][i] / augmented[i][i];
      for (let j = i; j <= n; j++) {
        augmented[k][j] -= factor * augmented[i][j];
      }
    }
  }
  
  // Back substitution
  const x = new Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) {
    if (Math.abs(augmented[i][i]) < 1e-10) continue;
    x[i] = augmented[i][n];
    for (let j = i + 1; j < n; j++) {
      x[i] -= augmented[i][j] * x[j];
    }
    x[i] /= augmented[i][i];
  }
  
  return x;
}

function computeRegression(
  x: number[], 
  y: number[], 
  type: RegressionType, 
  degree: number,
  isDateAxis: boolean = false
): RegressionResult {
  switch (type) {
    case 'linear':
      return linearRegression(x, y, isDateAxis);
    case 'polynomial':
      return polynomialRegression(x, y, degree, isDateAxis);
    case 'exponential':
      return exponentialRegression(x, y, isDateAxis);
    case 'logarithmic':
      return logarithmicRegression(x, y, isDateAxis);
    default:
      return linearRegression(x, y, isDateAxis);
  }
}

// ─── Chart Definition ────────────────────────────────────────────────────────

export const ScatterChart: ChartTypeDefinition<ScatterChartOptions> = {
  id: 'scatter',
  name: 'Scatter',
  description: 'Best for correlations and distributions',
  icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
      <circle cx="6" cy="18" r="2" fill="currentColor" />
      <circle cx="10" cy="10" r="2" fill="currentColor" />
      <circle cx="14" cy="14" r="2" fill="currentColor" />
      <circle cx="18" cy="6" r="2" fill="currentColor" />
    </svg>
  ),
  
  defaultOptions: {
    markerSize: 8,
    markerOpacity: 0.7,
    markerShape: 'circle',
    showTrendline: false,
    jitter: false,
    regression: {
      enabled: false,
      type: 'linear',
      degree: 2,
      showEquation: true,
      showR2: true,
    },
  },
  
  buildTraces: (data, xAxis, ySeries, options) => {
    const traces: any[] = [];
    
    // Parse x values (handle dates)
    const parseX = (val: any): number | null => {
      if (typeof val === 'number') return isFinite(val) ? val : null;
      if (typeof val === 'string') {
        if (val.match(/^\d{4}-\d{2}-\d{2}/)) {
          return new Date(val).getTime();
        }
        const num = Number(val);
        return isFinite(num) ? num : null;
      }
      return null;
    };
    
    // Check if x-axis is dates for display
    const isDateAxis = data.length > 0 && typeof data[0][xAxis] === 'string' && 
                       !!data[0][xAxis]?.match(/^\d{4}-\d{2}-\d{2}/);
    
    // ─── Long-format mode: data has 'symbol' column, group by symbol ───────────
    // This happens when multiple symbols with same X/Y fields (e.g., scatter of totalAssets vs netIncome)
    const hasSymbolColumn = data.length > 0 && 'symbol' in data[0];
    const has_source_symbol = data.length > 0 && '_source_symbol' in data[0];
    const uniqueSymbols = hasSymbolColumn 
      ? [...new Set(data.map(d => d.symbol).filter(Boolean))] as string[]
      : [];

    // Helper to strip symbol prefix from field name (e.g., "JPM_netIncome" -> "netIncome")
    const stripSymbolPrefix = (field: string): string => {
      for (const sym of uniqueSymbols) {
        if (field.startsWith(`${sym}_`)) {
          return field.slice(sym.length + 1);
        }
      }
      return field;
    };
    
    // Get first Y field and strip any symbol prefix
    const firstYFieldRaw = ySeries[0]?.field;
    const firstYFieldBase = firstYFieldRaw ? stripSymbolPrefix(firstYFieldRaw) : '';
    
    // Use long-format if: data has symbol column AND we can find the base Y field (unprefixed)
    const isLongFormat = hasSymbolColumn && uniqueSymbols.length > 1 && 
                         firstYFieldBase && data.some(d => d[firstYFieldBase] != null);
    
    if (isLongFormat && uniqueSymbols.length > 1) {
      // Long-format: create one trace per symbol, all using same X and Y fields (unprefixed)
      const yFieldToUse = firstYFieldBase;
      
      uniqueSymbols.forEach((symbol, idx) => {
        const symbolData = data.filter(d => d.symbol === symbol);
        const color = COLORS[idx % COLORS.length];
        
        const xValues = symbolData.map(d => d[xAxis]);
        let yValues = symbolData.map(d => d[yFieldToUse]);
        
        // Apply jitter
        if (options.jitter) {
          const validY = yValues.filter(v => v != null) as number[];
          if (validY.length > 0) {
            const range = Math.max(...validY) - Math.min(...validY);
            const jitterAmount = range * 0.02;
            yValues = yValues.map(v => v != null ? (v as number) + (Math.random() - 0.5) * jitterAmount : v);
          }
        }
        
        traces.push({
          x: xValues,
          y: yValues,
          type: 'scatter' as const,
          mode: 'markers',
          name: `${symbol}`,
          marker: {
            color,
            size: options.markerSize,
            opacity: options.markerOpacity,
            symbol: SHAPE_MAP[options.markerShape] || 'circle',
          },
        });
        
        // Add regression per symbol if enabled
        if (options.regression?.enabled) {
          const xNumeric = symbolData.map(d => parseX(d[xAxis]));
          const pairs: { x: number; y: number }[] = [];
          for (let i = 0; i < symbolData.length; i++) {
            const x = xNumeric[i];
            const y = Number(yValues[i]);
            if (x !== null && !isNaN(y) && isFinite(y)) {
              pairs.push({ x, y });
            }
          }
          
          if (pairs.length >= 2) {
            const result = computeRegression(
              pairs.map(p => p.x),
              pairs.map(p => p.y),
              options.regression.type,
              options.regression.degree,
              isDateAxis
            );
            
            if (result.lineX.length > 0) {
              const lineXDisplay = isDateAxis 
                ? result.lineX.map(ts => new Date(ts).toISOString().split('T')[0])
                : result.lineX;
              
              traces.push({
                x: lineXDisplay,
                y: result.lineY,
                type: 'scatter' as const,
                mode: 'lines',
                name: `${symbol} fit (R²=${result.rSquared.toFixed(3)})`,
                line: { color, width: 2, dash: 'dash' },
                hoverinfo: 'name+y',
                showlegend: false,
              });
            }
          }
        }
      });
      
      return traces;
    }
    
    // ─── Standard mode: one trace per Y-series ─────────────────────────────────
    const xValues = data.map((d) => d[xAxis]);
    const xNumeric = data.map((d) => parseX(d[xAxis]));
    
    ySeries.forEach((series, idx) => {
      const color = series.color || COLORS[idx % COLORS.length];
      let yValues = data.map((d) => d[series.field]);
      
      // Apply jitter
      if (options.jitter) {
        const validY = yValues.filter((v) => v != null);
        const range = Math.max(...validY) - Math.min(...validY);
        const jitterAmount = range * 0.02;
        yValues = yValues.map((v) => v != null ? v + (Math.random() - 0.5) * jitterAmount : v);
      }
      
      // Main scatter trace
      traces.push({
        x: xValues,
        y: yValues,
        type: 'scatter' as const,
        mode: 'markers',
        name: series.label || series.field,
        marker: {
          color,
          size: options.markerSize,
          opacity: options.markerOpacity,
          symbol: SHAPE_MAP[options.markerShape] || 'circle',
        },
      });
      
      // Add regression if enabled
      if (options.regression?.enabled) {
        // Get valid numeric pairs
        const pairs: { x: number; y: number; origX: any }[] = [];
        for (let i = 0; i < data.length; i++) {
          const x = xNumeric[i];
          const y = Number(yValues[i]);
          if (x !== null && !isNaN(y) && isFinite(y)) {
            pairs.push({ x, y, origX: xValues[i] });
          }
        }
        
        if (pairs.length >= 2) {
          const result = computeRegression(
            pairs.map((p) => p.x),
            pairs.map((p) => p.y),
            options.regression.type,
            options.regression.degree,
            isDateAxis
          );
          
          if (result.lineX.length > 0) {
            // Convert x back to dates if needed
            const lineXDisplay = isDateAxis 
              ? result.lineX.map((ts) => new Date(ts).toISOString().split('T')[0])
              : result.lineX;
            
            // Build legend name
            let name = 'Fit';
            if (options.regression.showEquation && options.regression.showR2) {
              name = `${result.equation} | R²=${result.rSquared.toFixed(4)}`;
            } else if (options.regression.showEquation) {
              name = result.equation;
            } else if (options.regression.showR2) {
              name = `R²=${result.rSquared.toFixed(4)}`;
            }
            
            traces.push({
              x: lineXDisplay,
              y: result.lineY,
              type: 'scatter' as const,
              mode: 'lines',
              name,
              line: {
                color: options.regression.lineColor || color,
                width: 2.5,
              },
              hoverinfo: 'name+y',
            });
          }
        }
      }
    });
    
    return traces;
  },
};
