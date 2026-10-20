/**
 * Aggregation Utilities Tests
 *
 * Tests for data aggregation functions used by the Smart Join system.
 */

import { describe, it, expect } from 'vitest';
import { applyAggregation, getDefaultAggregation } from './aggregation';

// ============================================================================
// TEST SUITES
// ============================================================================

describe('applyAggregation', () => {
  describe('avg (average)', () => {
    it('should calculate average of positive numbers', () => {
      expect(applyAggregation([10, 20, 30, 40, 50], 'avg')).toBe(30);
    });
    
    it('should calculate average with decimals', () => {
      expect(applyAggregation([1.5, 2.5, 3.5], 'avg')).toBeCloseTo(2.5);
    });
    
    it('should handle single value', () => {
      expect(applyAggregation([42], 'avg')).toBe(42);
    });
    
    it('should handle negative numbers', () => {
      expect(applyAggregation([-10, 10], 'avg')).toBe(0);
    });
    
    it('should ignore null values', () => {
      expect(applyAggregation([10, null, 30], 'avg')).toBe(20);
    });
    
    it('should ignore undefined values', () => {
      expect(applyAggregation([10, undefined, 30], 'avg')).toBe(20);
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'avg')).toBeNull();
    });
    
    it('should return null for all-null array', () => {
      expect(applyAggregation([null, null, null], 'avg')).toBeNull();
    });
  });
  
  describe('sum', () => {
    it('should calculate sum of positive numbers', () => {
      expect(applyAggregation([10, 20, 30, 40, 50], 'sum')).toBe(150);
    });
    
    it('should handle decimals', () => {
      expect(applyAggregation([1.1, 2.2, 3.3], 'sum')).toBeCloseTo(6.6);
    });
    
    it('should handle single value', () => {
      expect(applyAggregation([42], 'sum')).toBe(42);
    });
    
    it('should handle negative numbers', () => {
      expect(applyAggregation([-10, 20, -5], 'sum')).toBe(5);
    });
    
    it('should ignore null values', () => {
      expect(applyAggregation([10, null, 30], 'sum')).toBe(40);
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'sum')).toBeNull();
    });
  });
  
  describe('first', () => {
    it('should return first value', () => {
      expect(applyAggregation([10, 20, 30], 'first')).toBe(10);
    });
    
    it('should skip leading nulls', () => {
      expect(applyAggregation([null, null, 30, 40], 'first')).toBe(30);
    });
    
    it('should handle single value', () => {
      expect(applyAggregation([42], 'first')).toBe(42);
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'first')).toBeNull();
    });
  });
  
  describe('last', () => {
    it('should return last value', () => {
      expect(applyAggregation([10, 20, 30], 'last')).toBe(30);
    });
    
    it('should skip trailing nulls', () => {
      expect(applyAggregation([10, 20, null, null], 'last')).toBe(20);
    });
    
    it('should handle single value', () => {
      expect(applyAggregation([42], 'last')).toBe(42);
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'last')).toBeNull();
    });
  });
  
  describe('min', () => {
    it('should return minimum value', () => {
      expect(applyAggregation([30, 10, 50, 20], 'min')).toBe(10);
    });
    
    it('should handle negative numbers', () => {
      expect(applyAggregation([10, -5, 20], 'min')).toBe(-5);
    });
    
    it('should ignore null values', () => {
      expect(applyAggregation([30, null, 10], 'min')).toBe(10);
    });
    
    it('should handle single value', () => {
      expect(applyAggregation([42], 'min')).toBe(42);
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'min')).toBeNull();
    });
  });
  
  describe('max', () => {
    it('should return maximum value', () => {
      expect(applyAggregation([30, 10, 50, 20], 'max')).toBe(50);
    });
    
    it('should handle negative numbers', () => {
      expect(applyAggregation([-30, -10, -50], 'max')).toBe(-10);
    });
    
    it('should ignore null values', () => {
      expect(applyAggregation([30, null, 50], 'max')).toBe(50);
    });
    
    it('should handle single value', () => {
      expect(applyAggregation([42], 'max')).toBe(42);
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'max')).toBeNull();
    });
  });
  
  describe('count', () => {
    it('should count non-null values', () => {
      expect(applyAggregation([10, 20, 30, 40, 50], 'count')).toBe(5);
    });
    
    it('should exclude null values from count', () => {
      expect(applyAggregation([10, null, 30, null, 50], 'count')).toBe(3);
    });
    
    it('should return 0 for all-null array', () => {
      expect(applyAggregation([null, null], 'count')).toBeNull();
    });
    
    it('should return null for empty array', () => {
      expect(applyAggregation([], 'count')).toBeNull();
    });
  });
});

describe('getDefaultAggregation', () => {
  describe('Price fields → last', () => {
    it('should default "close" to last', () => {
      expect(getDefaultAggregation('close')).toBe('last');
    });
    
    it('should default "Close" to last (case insensitive)', () => {
      expect(getDefaultAggregation('Close')).toBe('last');
    });
    
    it('should default "adjClose" to last', () => {
      expect(getDefaultAggregation('adjClose')).toBe('last');
    });
    
    it('should default "price" to last', () => {
      expect(getDefaultAggregation('price')).toBe('last');
    });
    
    it('should default "stockPrice" to last', () => {
      expect(getDefaultAggregation('stockPrice')).toBe('last');
    });
  });
  
  describe('Opening values → first', () => {
    it('should default "open" to first', () => {
      expect(getDefaultAggregation('open')).toBe('first');
    });
    
    it('should default "Open" to first', () => {
      expect(getDefaultAggregation('Open')).toBe('first');
    });
    
    it('should default "openPrice" to first', () => {
      expect(getDefaultAggregation('openPrice')).toBe('first');
    });
  });
  
  describe('High values → max', () => {
    it('should default "high" to max', () => {
      expect(getDefaultAggregation('high')).toBe('max');
    });
    
    it('should default "High" to max', () => {
      expect(getDefaultAggregation('High')).toBe('max');
    });
    
    it('should default "dayHigh" to max', () => {
      expect(getDefaultAggregation('dayHigh')).toBe('max');
    });
  });
  
  describe('Low values → min', () => {
    it('should default "low" to min', () => {
      expect(getDefaultAggregation('low')).toBe('min');
    });
    
    it('should default "Low" to min', () => {
      expect(getDefaultAggregation('Low')).toBe('min');
    });
    
    it('should default "dayLow" to min', () => {
      expect(getDefaultAggregation('dayLow')).toBe('min');
    });
  });
  
  describe('Volume/quantity fields → sum', () => {
    it('should default "volume" to sum', () => {
      expect(getDefaultAggregation('volume')).toBe('sum');
    });
    
    it('should default "Volume" to sum', () => {
      expect(getDefaultAggregation('Volume')).toBe('sum');
    });
    
    it('should default "tradingVolume" to sum', () => {
      expect(getDefaultAggregation('tradingVolume')).toBe('sum');
    });
    
    it('should default "amount" to sum', () => {
      expect(getDefaultAggregation('amount')).toBe('sum');
    });
    
    it('should default "quantity" to sum', () => {
      expect(getDefaultAggregation('quantity')).toBe('sum');
    });
    
    it('should default "tradeCount" to sum', () => {
      expect(getDefaultAggregation('tradeCount')).toBe('sum');
    });
  });
  
  describe('Ratio fields → avg', () => {
    it('should default "peRatio" to avg', () => {
      expect(getDefaultAggregation('peRatio')).toBe('avg');
    });
    
    it('should default "pbRatio" to avg', () => {
      expect(getDefaultAggregation('pbRatio')).toBe('avg');
    });
    
    it('should default "dividendYield" to avg', () => {
      expect(getDefaultAggregation('dividendYield')).toBe('avg');
    });
    
    it('should default "priceToBookRatio" to avg', () => {
      expect(getDefaultAggregation('priceToBookRatio')).toBe('avg');
    });
  });
  
  describe('Unknown fields → last', () => {
    it('should default unknown field to last', () => {
      expect(getDefaultAggregation('someRandomField')).toBe('last');
    });
    
    it('should default "revenue" to last', () => {
      // Revenue is already a period total, so we want the value, not sum
      expect(getDefaultAggregation('revenue')).toBe('last');
    });
    
    it('should default "netIncome" to last', () => {
      expect(getDefaultAggregation('netIncome')).toBe('last');
    });
  });
});

describe('Real-world aggregation scenarios', () => {
  describe('Crypto daily to quarterly', () => {
    // Simulated BTC Q1 2024 daily data (90 days)
    const btcQ1Daily = {
      close: Array.from({ length: 90 }, (_, i) => 42000 + i * 300 + Math.random() * 1000),
      high: Array.from({ length: 90 }, (_, i) => 43000 + i * 300 + Math.random() * 2000),
      low: Array.from({ length: 90 }, (_, i) => 41000 + i * 300 + Math.random() * 1000),
      volume: Array.from({ length: 90 }, () => Math.floor(100000 + Math.random() * 50000)),
    };
    
    it('should aggregate close to last (end of quarter price)', () => {
      const result = applyAggregation(btcQ1Daily.close, 'last');
      // Should be around 69000 (42000 + 90*300)
      expect(result).toBeGreaterThan(65000);
      expect(result).toBeLessThan(75000);
    });
    
    it('should aggregate high to max (quarter high)', () => {
      const result = applyAggregation(btcQ1Daily.high, 'max');
      const actualMax = Math.max(...btcQ1Daily.high);
      expect(result).toBe(actualMax);
    });
    
    it('should aggregate low to min (quarter low)', () => {
      const result = applyAggregation(btcQ1Daily.low, 'min');
      const actualMin = Math.min(...btcQ1Daily.low);
      expect(result).toBe(actualMin);
    });
    
    it('should aggregate volume to sum (total quarter volume)', () => {
      const result = applyAggregation(btcQ1Daily.volume, 'sum');
      const actualSum = btcQ1Daily.volume.reduce((a, b) => a + b, 0);
      expect(result).toBe(actualSum);
      // Should be around 90 * 125000 = 11.25M
      expect(result).toBeGreaterThan(10000000);
    });
  });
  
  describe('Stock daily to quarterly with missing data', () => {
    // Stock data has ~63 trading days per quarter (weekends excluded)
    const aaplQ1Daily = {
      close: Array.from({ length: 63 }, (_, i) => 
        i < 5 ? null : 180 + i * 0.5 + Math.random() * 5 // First week missing
      ) as (number | null)[],
      volume: Array.from({ length: 63 }, () => 
        Math.random() > 0.9 ? null : Math.floor(50000000 + Math.random() * 30000000)
      ) as (number | null)[],
    };
    
    it('should handle missing close values', () => {
      const result = applyAggregation(aaplQ1Daily.close, 'last');
      // Should still work, ignoring nulls
      expect(result).not.toBeNull();
      expect(result).toBeGreaterThan(200);
    });
    
    it('should handle sporadic missing volume values', () => {
      const result = applyAggregation(aaplQ1Daily.volume, 'sum');
      // Should sum non-null values
      expect(result).not.toBeNull();
      expect(result).toBeGreaterThan(2000000000);
    });
  });
});
