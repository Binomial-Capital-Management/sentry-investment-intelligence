/**
 * Action Validator - Validates agent actions before execution
 * 
 * Provides frontend validation for:
 * - Symbol format (uppercase letters, numbers, dots, hyphens)
 * - Endpoint whitelist (common FMP endpoints)
 * - Weight validation (sum to 1.0)
 */

import type { AgentAction, ValidationResult } from '../types';

// Symbol validation regex: uppercase letters, numbers, dots, hyphens, 1-15 chars
const SYMBOL_REGEX = /^[A-Z0-9\.\-]{1,15}$/;

// Common allowed endpoints (can be expanded or fetched from API)
const ALLOWED_ENDPOINTS = new Set([
  // Price & Volume
  'historical-price-full',
  'historical-price-full/full',
  'quote',
  'quote-short',
  'stock-price-change',
  'historical-chart',
  
  // Fundamentals
  'income-statement',
  'balance-sheet-statement',
  'cash-flow-statement',
  'financial-ratios',
  'key-metrics',
  'financial-growth',
  'enterprise-values',
  
  // Valuation
  'discounted-cash-flow',
  'rating',
  'analyst-estimates',
  'analyst-stock-recommendations',
  
  // Ownership & Institutional
  'institutional-holder',
  'institutional-ownership',
  'insider-trading',
  'insider-roster',
  
  // Analyst & Ratings
  'grade',
  'price-target',
  'upgrades-downgrades',
  
  // Profile & General
  'profile',
  'company-outlook',
  'stock-peers',
  'sector-performance',
  
  // Options
  'options/all',
  
  // ETF
  'etf-holder',
  'etf-sector-weightings',
  
  // Economic
  'economic-calendar',
  'earnings-calendar',
  
  // SEC Filings
  'sec-filings',
]);

/**
 * Validate an agent action before execution
 */
export function validateAction(action: AgentAction): ValidationResult {
  switch (action.type) {
    case 'add_dataset': {
      // Validate symbol format
      if (!action.symbol || !SYMBOL_REGEX.test(action.symbol.toUpperCase())) {
        return { 
          valid: false, 
          error: `Invalid symbol format: "${action.symbol}". Must be 1-15 uppercase alphanumeric characters.` 
        };
      }
      
      // Validate endpoint (allow any if not in strict mode)
      if (action.endpoint && !ALLOWED_ENDPOINTS.has(action.endpoint)) {
        console.warn(`[ActionValidator] Endpoint "${action.endpoint}" not in whitelist, allowing anyway`);
        // Allow anyway - just log warning
      }
      
      return { valid: true };
    }
    
    case 'remove_dataset': {
      if (!action.dataset_id) {
        return { valid: false, error: 'Missing dataset_id for remove_dataset action' };
      }
      return { valid: true };
    }
    
    case 'create_chart': {
      if (!action.config) {
        return { valid: false, error: 'Missing config for create_chart action' };
      }
      if (!action.config.xAxis) {
        return { valid: false, error: 'Chart config missing xAxis field' };
      }
      // Candlestick charts use ohlcFields instead of ySeries
      const isCandlestick = action.config.chartType === 'candlestick';
      if (!isCandlestick && (!action.config.ySeries || action.config.ySeries.length === 0)) {
        return { valid: false, error: 'Chart config missing ySeries' };
      }
      if (isCandlestick && !action.config.ohlcFields) {
        return { valid: false, error: 'Candlestick chart requires ohlcFields configuration' };
      }
      return { valid: true };
    }
    
    case 'create_pivot': {
      if (!action.config) {
        return { valid: false, error: 'Missing config for create_pivot action' };
      }
      return { valid: true };
    }
    
    case 'start_tool_analysis': {
      if (!action.tool_id) {
        return { valid: false, error: 'Missing tool_id for start_tool_analysis action' };
      }
      if (!action.tickers || action.tickers.length === 0) {
        return { valid: false, error: 'Missing tickers for start_tool_analysis action' };
      }
      // Validate all tickers
      for (const ticker of action.tickers) {
        if (!SYMBOL_REGEX.test(ticker.toUpperCase())) {
          return { valid: false, error: `Invalid ticker format: "${ticker}"` };
        }
      }
      return { valid: true };
    }
    
    case 'create_tab': {
      // Tab creation action - used to separate incompatible data types
      if (!action.name) {
        return { valid: false, error: 'Missing name for create_tab action' };
      }
      return { valid: true };
    }
    
    default:
      // Unknown action type - allow but log
      console.warn(`[ActionValidator] Unknown action type: ${(action as any).type}`);
      return { valid: true };
  }
}

/**
 * Validate portfolio weights sum to 1.0 (within tolerance)
 */
export function validateWeights(weights: number[], tolerance = 0.001): ValidationResult {
  if (!weights || weights.length === 0) {
    return { valid: true }; // No weights = equal weight assumed
  }
  
  const sum = weights.reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1.0) > tolerance) {
    return { 
      valid: false, 
      error: `Weights must sum to 1.0, got ${sum.toFixed(4)}` 
    };
  }
  
  return { valid: true };
}
