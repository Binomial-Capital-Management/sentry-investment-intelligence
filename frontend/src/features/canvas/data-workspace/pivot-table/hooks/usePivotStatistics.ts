import { useState, useEffect, useCallback, useRef } from 'react';
import { PivotConfig } from '../../stores/dataWorkspaceStore';
import { FieldInfo, DescriptiveStats, CorrelationResult, StatisticalTestResult } from '../types';
import { API_BASE } from '@/services/api';

interface RegressionResult {
  x_field: string;
  y_field: string;
  slope: number;
  intercept: number;
  r_squared: number;
  adj_r_squared: number;
  std_error: number;
  p_value: number;
}

interface DistributionData {
  field: string;
  histogram_bins: number[];
  histogram_counts: number[];
  quartiles: Record<string, number>;
  outliers: number[];
}

export function usePivotStatistics(
  sourceData: Record<string, any>[],
  fields: FieldInfo[],
  config: PivotConfig | undefined
) {
  const [activeStatsTab, setActiveStatsTab] = useState<'descriptive' | 'correlation' | 'regression' | 'distribution' | 'tests'>('descriptive');
  const [descriptiveStats, setDescriptiveStats] = useState<DescriptiveStats[]>([]);
  const [correlationResult, setCorrelationResult] = useState<CorrelationResult | null>(null);
  const [distributionData, setDistributionData] = useState<DistributionData[]>([]);
  const [testResult, setTestResult] = useState<StatisticalTestResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  
  // Test configuration
  const [selectedTest, setSelectedTest] = useState<string>('shapiro_wilk');
  const [testFieldA, setTestFieldA] = useState<string>('');
  const [testFieldB, setTestFieldB] = useState<string>('');
  const [testGroupBy, setTestGroupBy] = useState<string>('');
  const [testPopulationMean, setTestPopulationMean] = useState<string>('0');
  
  // Stats panel state
  const [statsPanelCollapsed, setStatsPanelCollapsed] = useState(false);
  const [statsPanelHeight, setStatsPanelHeight] = useState(288); // h-72 = 288px
  const [, setIsResizing] = useState(false);
  
  // Regression state
  const [regressionX, setRegressionX] = useState<string>('');
  const [regressionY, setRegressionY] = useState<string>('');
  const [regressionResult, setRegressionResult] = useState<RegressionResult | null>(null);
  const [regressionLoading, setRegressionLoading] = useState(false);

  // Track if stats have been computed for current data
  const statsComputedRef = useRef<string | null>(null);
  
  // Compute statistics when data changes (debounced by checking ref)
  // Only analyze fields that are in the pivot config (rows, columns, values)
  useEffect(() => {
    if (!sourceData.length || !config) return;
    
    // Get fields used in the pivot table configuration
    const pivotFields = new Set<string>([
      ...config.rows,
      ...config.columns,
      ...config.values.map(v => v.field),
    ]);
    
    // Only include numeric fields that are in the pivot config
    const numericFields = fields
      .filter(f => f.can_aggregate && pivotFields.has(f.name))
      .map(f => f.name);
    
    // If no configured numeric fields, show nothing
    if (numericFields.length === 0) {
      setDescriptiveStats([]);
      setCorrelationResult(null);
      setDistributionData([]);
      return;
    }
    
    // Create a stable key to avoid recomputing for same data
    const dataKey = `${sourceData.length}-${numericFields.join(',')}`;
    if (statsComputedRef.current === dataKey) return;
    statsComputedRef.current = dataKey;
    
    const computeStats = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/canvas/pivot/statistics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data: sourceData,
            fields: numericFields,
            analysis_types: ['descriptive', 'correlation', 'distribution'],
          }),
        });
        
        if (response.ok) {
          const result = await response.json();
          if (result.success) {
            if (result.descriptive) setDescriptiveStats(result.descriptive);
            if (result.correlation) setCorrelationResult(result.correlation);
            if (result.distribution) setDistributionData(result.distribution);
          }
        }
      } catch (error) {
        console.error('Error computing statistics:', error);
      }
    };
    
    computeStats();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceData, fields, config?.rows?.length, config?.columns?.length, config?.values?.length]);
  
  // Run regression analysis
  const runRegression = useCallback(async () => {
    if (!sourceData.length || !regressionX || !regressionY) return;
    
    setRegressionLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/canvas/pivot/statistics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: sourceData,
          fields: [regressionX, regressionY],
          analysis_types: ['regression'],
          regression_x: regressionX,
          regression_y: regressionY,
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.success && result.regression) {
          setRegressionResult(result.regression);
        }
      }
    } catch (error) {
      console.error('Error running regression:', error);
    } finally {
      setRegressionLoading(false);
    }
  }, [sourceData, regressionX, regressionY]);
  
  // Handle stats panel resize
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    
    const startY = e.clientY;
    const startHeight = statsPanelHeight;
    
    const handleMouseMove = (e: MouseEvent) => {
      const delta = startY - e.clientY;
      const newHeight = Math.min(Math.max(startHeight + delta, 100), 500);
      setStatsPanelHeight(newHeight);
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [statsPanelHeight]);

  // Run statistical test
  const runTest = useCallback(async () => {
    if (!sourceData.length || !testFieldA) return;
    
    setTestLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/canvas/pivot/tests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: sourceData,
          test_type: selectedTest,
          field_a: testFieldA,
          field_b: testFieldB || undefined,
          group_by: testGroupBy || undefined,
          population_mean: selectedTest === 'ttest_one' ? parseFloat(testPopulationMean) : undefined,
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.success && result.result) {
          setTestResult(result.result);
        }
      }
    } catch (error) {
      console.error('Error running test:', error);
    } finally {
      setTestLoading(false);
    }
  }, [sourceData, selectedTest, testFieldA, testFieldB, testGroupBy, testPopulationMean]);

  return {
    // Stats tab
    activeStatsTab,
    setActiveStatsTab,
    
    // Descriptive stats
    descriptiveStats,
    
    // Correlation
    correlationResult,
    
    // Distribution
    distributionData,
    
    // Regression
    regressionX,
    setRegressionX,
    regressionY,
    setRegressionY,
    regressionResult,
    regressionLoading,
    runRegression,
    
    // Tests
    selectedTest,
    setSelectedTest,
    testFieldA,
    setTestFieldA,
    testFieldB,
    setTestFieldB,
    testGroupBy,
    setTestGroupBy,
    testPopulationMean,
    setTestPopulationMean,
    testResult,
    testLoading,
    runTest,
    
    // Stats panel
    statsPanelCollapsed,
    setStatsPanelCollapsed,
    statsPanelHeight,
    handleResizeStart,
  };
}
