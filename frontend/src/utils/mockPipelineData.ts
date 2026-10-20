// Mock data and schema system for pipeline builder

export interface Schema {
  columns: string[];
  count: number;
  types?: Record<string, string>;
}

export interface MockDataRow {
  [key: string]: any;
}

// Predefined schemas for different data sources
export const mockSchemas = {
  portfolio: {
    columns: ['ticker', 'shares', 'value', 'sector', 'date'],
    count: 5,
    types: {
      ticker: 'string',
      shares: 'number',
      value: 'number',
      sector: 'string',
      date: 'date',
    },
  },
  marketData: {
    columns: ['ticker', 'price', 'volume', 'change', 'marketCap', 'pe_ratio', 'dividend'],
    count: 7,
    types: {
      ticker: 'string',
      price: 'number',
      volume: 'number',
      change: 'number',
      marketCap: 'number',
      pe_ratio: 'number',
      dividend: 'number',
    },
  },
  riskMetrics: {
    columns: ['ticker', 'var_95', 'var_99', 'sharpe', 'beta', 'volatility'],
    count: 6,
    types: {
      ticker: 'string',
      var_95: 'number',
      var_99: 'number',
      sharpe: 'number',
      beta: 'number',
      volatility: 'number',
    },
  },
};

// Generate mock preview data
export const generateMockPreview = (nodeType: string, _config?: any): MockDataRow[] => {

  switch (nodeType) {
    case 'portfolio':
      return [
        { ticker: 'AAPL', shares: 1000, value: 175000, sector: 'Technology', date: '2024-01-15' },
        { ticker: 'MSFT', shares: 800, value: 320000, sector: 'Technology', date: '2024-01-15' },
        { ticker: 'GOOGL', shares: 500, value: 140000, sector: 'Technology', date: '2024-01-15' },
        { ticker: 'JPM', shares: 1200, value: 180000, sector: 'Finance', date: '2024-01-15' },
        { ticker: 'JNJ', shares: 900, value: 144000, sector: 'Healthcare', date: '2024-01-15' },
      ];

    case 'marketData':
      return [
        { ticker: 'AAPL', price: 175.50, volume: 45234000, change: 2.3, marketCap: 2800000000000, pe_ratio: 28.5, dividend: 0.96 },
        { ticker: 'MSFT', price: 400.25, volume: 23456000, change: -0.8, marketCap: 3000000000000, pe_ratio: 32.1, dividend: 3.00 },
        { ticker: 'GOOGL', price: 280.75, volume: 18234000, change: 1.5, marketCap: 1800000000000, pe_ratio: 25.3, dividend: 0 },
      ];

    case 'joined':
      return [
        { ticker: 'AAPL', shares: 1000, value: 175000, sector: 'Technology', price: 175.50, volume: 45234000, change: 2.3, marketCap: 2800000000000 },
        { ticker: 'MSFT', shares: 800, value: 320000, sector: 'Technology', price: 400.25, volume: 23456000, change: -0.8, marketCap: 3000000000000 },
        { ticker: 'GOOGL', shares: 500, value: 140000, sector: 'Technology', price: 280.75, volume: 18234000, change: 1.5, marketCap: 1800000000000 },
      ];

    case 'filtered':
      return [
        { ticker: 'AAPL', shares: 1000, value: 175000, sector: 'Technology', date: '2024-01-15' },
        { ticker: 'MSFT', shares: 800, value: 320000, sector: 'Technology', date: '2024-01-15' },
        { ticker: 'GOOGL', shares: 500, value: 140000, sector: 'Technology', date: '2024-01-15' },
        { ticker: 'JPM', shares: 1200, value: 180000, sector: 'Finance', date: '2024-01-15' },
      ];

    case 'aggregated':
      return [
        { sector: 'Technology', total_value: 635000, avg_shares: 766, count: 3 },
        { sector: 'Finance', total_value: 180000, avg_shares: 1200, count: 1 },
        { sector: 'Healthcare', total_value: 144000, avg_shares: 900, count: 1 },
      ];

    case 'transformed':
      return [
        { ticker: 'AAPL', portfolio_value: 175000, market_value: 175500, gain_loss: 500, gain_pct: 0.29 },
        { ticker: 'MSFT', portfolio_value: 320000, market_value: 320200, gain_loss: 200, gain_pct: 0.06 },
        { ticker: 'GOOGL', portfolio_value: 140000, market_value: 140375, gain_loss: 375, gain_pct: 0.27 },
      ];

    default:
      return [];
  }
};

// Calculate output schema based on operation
export const calculateOutputSchema = (
  inputSchema: Schema,
  operation: string,
  config?: any,
): Schema => {
  switch (operation) {
    case 'select':
      const selectedCols = config?.columns || inputSchema.columns.slice(0, 3);
      return {
        columns: selectedCols,
        count: selectedCols.length,
      };

    case 'join':
      const rightSchema = config?.rightSchema || mockSchemas.marketData;
      const combinedCols = [...inputSchema.columns, ...rightSchema.columns.filter((c: string) => c !== 'ticker')];
      return {
        columns: combinedCols,
        count: combinedCols.length,
      };

    case 'filter':
      return {
        columns: inputSchema.columns,
        count: inputSchema.count,
      };

    case 'aggregate':
      const groupBy = config?.groupBy || 'sector';
      const aggregations = config?.aggregations || ['sum_value', 'avg_shares', 'count'];
      return {
        columns: [groupBy, ...aggregations],
        count: aggregations.length + 1,
      };

    case 'transform':
      const newFields = config?.newFields || ['calculated_field'];
      return {
        columns: [...inputSchema.columns, ...newFields],
        count: inputSchema.count + newFields.length,
      };

    default:
      return inputSchema;
  }
};

// Schema propagation through pipeline
export const propagateSchemas = (nodes: any[], edges: any[]): Map<string, Schema> => {
  const schemaMap = new Map<string, Schema>();

  // Start with source nodes
  nodes.forEach(node => {
    if (node.type === 'portfolio') {
      schemaMap.set(node.id, mockSchemas.portfolio);
    } else if (node.data.label === 'Market Data') {
      schemaMap.set(node.id, mockSchemas.marketData);
    }
  });

  // Propagate through edges
  const visited = new Set<string>();
  const queue = nodes.filter(n => n.type === 'portfolio' || n.data.label === 'Market Data');

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (visited.has(current.id)) continue;
    visited.add(current.id);

    // Find connected nodes
    const outgoingEdges = edges.filter(e => e.source === current.id);

    outgoingEdges.forEach(edge => {
      const targetNode = nodes.find(n => n.id === edge.target);
      if (!targetNode) return;

      const inputSchema = schemaMap.get(current.id);
      if (!inputSchema) return;

      // Calculate output schema based on node type
      let outputSchema: Schema;

      switch (targetNode.type) {
        case 'transform':
          outputSchema = calculateOutputSchema(inputSchema, 'transform', targetNode.data);
          break;
        case 'filter':
          outputSchema = inputSchema; // Filter doesn't change columns
          break;
        case 'join':
          const rightInput = edges.find(e => e.target === targetNode.id && e.targetHandle === 'right');
          const rightSchema = rightInput ? schemaMap.get(rightInput.source) : mockSchemas.marketData;
          outputSchema = calculateOutputSchema(inputSchema, 'join', { rightSchema });
          break;
        case 'aggregate':
          outputSchema = calculateOutputSchema(inputSchema, 'aggregate', targetNode.data);
          break;
        default:
          outputSchema = inputSchema;
      }

      schemaMap.set(targetNode.id, outputSchema);
      queue.push(targetNode);
    });
  }

  return schemaMap;
};

// Generate validation status for nodes
export const validatePipeline = (nodes: any[], edges: any[]): Map<string, 'valid' | 'warning' | 'error'> => {
  const statusMap = new Map<string, 'valid' | 'warning' | 'error'>();

  nodes.forEach(node => {
    // Check if node has required inputs
    if (node.type !== 'portfolio' && node.type !== 'output') {
      const hasInput = edges.some(e => e.target === node.id);
      if (!hasInput) {
        statusMap.set(node.id, 'error');
        return;
      }
    }

    // Check specific node validations
    if (node.type === 'filter' && !node.data.condition) {
      statusMap.set(node.id, 'warning');
    } else if (node.type === 'join') {
      const inputs = edges.filter(e => e.target === node.id);
      if (inputs.length !== 2) {
        statusMap.set(node.id, 'error');
      } else {
        statusMap.set(node.id, 'valid');
      }
    } else {
      statusMap.set(node.id, 'valid');
    }
  });

  return statusMap;
};
