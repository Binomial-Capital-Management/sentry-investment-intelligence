/**
 * Unit tests for actionValidator.ts
 * 
 * Tests cover:
 * - validateAction for all action types
 * - Symbol format validation (regex)
 * - Endpoint whitelist behavior
 * - validateWeights function
 */
import { describe, it, expect } from 'vitest';
import { validateAction, validateWeights } from './actionValidator';
import type { AgentAction } from '../types';

// =============================================================================
// validateAction Tests
// =============================================================================

describe('validateAction', () => {
  describe('add_dataset action', () => {
    it('should accept valid uppercase symbol', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'AAPL',
        endpoint: 'historical-price-full',
        dataset_id: 'test-id',
        fields: ['date', 'close'],
        row_count: 100,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should accept lowercase symbol (normalized)', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'aapl', // lowercase - should be normalized
        endpoint: 'historical-price-full',
        dataset_id: 'test-id',
        fields: ['date', 'close'],
        row_count: 100,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should accept symbol with dots (e.g., BRK.B)', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'BRK.B',
        endpoint: 'profile',
        dataset_id: 'test-id',
        fields: [],
        row_count: 1,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should accept symbol with hyphen (e.g., A-USD)', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'BTC-USD',
        endpoint: 'quote',
        dataset_id: 'test-id',
        fields: [],
        row_count: 1,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should reject empty symbol', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: '',
        endpoint: 'historical-price-full',
        dataset_id: 'test-id',
        fields: [],
        row_count: 0,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid symbol');
    });

    it('should reject symbol with invalid characters', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'AAPL$',
        endpoint: 'historical-price-full',
        dataset_id: 'test-id',
        fields: [],
        row_count: 0,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
    });

    it('should reject symbol longer than 15 characters', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'VERYLONGSYMBOLNAME',
        endpoint: 'profile',
        dataset_id: 'test-id',
        fields: [],
        row_count: 0,
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
    });

    it('should accept whitelisted endpoints', () => {
      const whitelistedEndpoints = [
        'historical-price-full',
        'income-statement',
        'balance-sheet-statement',
        'profile',
        'quote',
        'key-metrics',
      ];

      for (const endpoint of whitelistedEndpoints) {
        const action: AgentAction = {
          type: 'add_dataset',
          symbol: 'AAPL',
          endpoint,
          dataset_id: 'test-id',
          fields: [],
          row_count: 0,
        };
        
        const result = validateAction(action);
        expect(result.valid).toBe(true);
      }
    });

    it('should allow non-whitelisted endpoints (with warning logged)', () => {
      const action: AgentAction = {
        type: 'add_dataset',
        symbol: 'AAPL',
        endpoint: 'custom-endpoint-not-in-list',
        dataset_id: 'test-id',
        fields: [],
        row_count: 0,
      };
      
      // Should still be valid - just logs a warning
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });
  });

  describe('remove_dataset action', () => {
    it('should accept valid dataset_id', () => {
      const action: AgentAction = {
        type: 'remove_dataset',
        dataset_id: 'abc123-def456',
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should reject missing dataset_id', () => {
      const action: AgentAction = {
        type: 'remove_dataset',
        dataset_id: '',
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('dataset_id');
    });
  });

  describe('create_chart action', () => {
    it('should accept valid chart config', () => {
      const action: AgentAction = {
        type: 'create_chart',
        config: {
          chartType: 'line',
          xAxis: 'date',
          ySeries: [{ field: 'close', label: 'Price' }],
        },
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should reject missing config', () => {
      const action = {
        type: 'create_chart',
      } as AgentAction;
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('config');
    });

    it('should reject missing xAxis', () => {
      const action: AgentAction = {
        type: 'create_chart',
        config: {
          chartType: 'line',
          xAxis: '',
          ySeries: [{ field: 'close' }],
        },
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('xAxis');
    });

    it('should reject empty ySeries', () => {
      const action: AgentAction = {
        type: 'create_chart',
        config: {
          chartType: 'line',
          xAxis: 'date',
          ySeries: [],
        },
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('ySeries');
    });
  });

  describe('create_pivot action', () => {
    it('should accept valid pivot config', () => {
      const action: AgentAction = {
        type: 'create_pivot',
        config: {
          rows: ['symbol'],
          columns: ['year'],
          values: [{ field: 'revenue', aggregation: 'sum' }],
        },
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should reject missing config', () => {
      const action = {
        type: 'create_pivot',
      } as AgentAction;
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
    });
  });

  describe('start_tool_analysis action', () => {
    it('should accept valid tool analysis request', () => {
      const action: AgentAction = {
        type: 'start_tool_analysis',
        tool_id: 'monte_carlo',
        tickers: ['AAPL', 'MSFT', 'GOOGL'],
        params: { n_simulations: 5000 },
        analysis_id: 'test-analysis-id',
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should reject missing tool_id', () => {
      const action: AgentAction = {
        type: 'start_tool_analysis',
        tool_id: '',
        tickers: ['AAPL'],
        params: {},
        analysis_id: 'test',
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('tool_id');
    });

    it('should reject empty tickers array', () => {
      const action: AgentAction = {
        type: 'start_tool_analysis',
        tool_id: 'monte_carlo',
        tickers: [],
        params: {},
        analysis_id: 'test',
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('tickers');
    });

    it('should reject invalid ticker format', () => {
      const action: AgentAction = {
        type: 'start_tool_analysis',
        tool_id: 'monte_carlo',
        tickers: ['AAPL', 'INVALID$TICKER'],
        params: {},
        analysis_id: 'test',
      };
      
      const result = validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('ticker');
    });
  });

  describe('unknown action types', () => {
    it('should allow unknown action types (with warning)', () => {
      const action = {
        type: 'some_future_action',
        data: 'test',
      } as unknown as AgentAction;
      
      const result = validateAction(action);
      expect(result.valid).toBe(true);
    });
  });
});

// =============================================================================
// validateWeights Tests
// =============================================================================

describe('validateWeights', () => {
  it('should accept weights that sum to 1.0', () => {
    const result = validateWeights([0.5, 0.3, 0.2]);
    expect(result.valid).toBe(true);
  });

  it('should accept empty weights array', () => {
    const result = validateWeights([]);
    expect(result.valid).toBe(true);
  });

  it('should accept single weight of 1.0', () => {
    const result = validateWeights([1.0]);
    expect(result.valid).toBe(true);
  });

  it('should reject weights that sum to less than 1.0', () => {
    const result = validateWeights([0.3, 0.3, 0.3]); // = 0.9
    expect(result.valid).toBe(false);
    expect(result.error).toContain('sum to 1.0');
  });

  it('should reject weights that sum to more than 1.0', () => {
    const result = validateWeights([0.5, 0.5, 0.5]); // = 1.5
    expect(result.valid).toBe(false);
  });

  it('should accept weights within tolerance', () => {
    const result = validateWeights([0.333, 0.333, 0.334]); // = 1.0 exactly
    expect(result.valid).toBe(true);
  });

  it('should handle floating point precision issues', () => {
    // 0.1 + 0.2 + 0.7 might not exactly equal 1.0 due to floating point
    const result = validateWeights([0.1, 0.2, 0.7]);
    expect(result.valid).toBe(true);
  });

  it('should accept custom tolerance', () => {
    // 0.98 with tolerance of 0.05 should pass
    const result = validateWeights([0.48, 0.5], 0.05);
    expect(result.valid).toBe(true);
  });
});

// =============================================================================
// Symbol Regex Edge Cases
// =============================================================================

describe('Symbol Regex Edge Cases', () => {
  const testSymbolValidation = (symbol: string) => {
    const action: AgentAction = {
      type: 'add_dataset',
      symbol,
      endpoint: 'profile',
      dataset_id: 'test',
      fields: [],
      row_count: 0,
    };
    return validateAction(action);
  };

  it('should accept numeric symbols (e.g., Japanese stocks)', () => {
    expect(testSymbolValidation('7203').valid).toBe(true); // Toyota on TSE
  });

  it('should accept mixed alphanumeric', () => {
    expect(testSymbolValidation('META').valid).toBe(true);
    expect(testSymbolValidation('3M').valid).toBe(true);
  });

  it('should reject spaces', () => {
    expect(testSymbolValidation('AA PL').valid).toBe(false);
  });

  it('should reject special characters', () => {
    expect(testSymbolValidation('AAPL@').valid).toBe(false);
    expect(testSymbolValidation('AAPL#').valid).toBe(false);
    expect(testSymbolValidation('AAPL!').valid).toBe(false);
  });

  it('should accept exactly 15 characters', () => {
    expect(testSymbolValidation('ABCDEFGHIJKLMNO').valid).toBe(true); // 15 chars
  });

  it('should reject 16 characters', () => {
    expect(testSymbolValidation('ABCDEFGHIJKLMNOP').valid).toBe(false); // 16 chars
  });
});
