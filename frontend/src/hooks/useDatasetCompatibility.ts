/**
 * Hook for checking dataset compatibility in the Data Workspace.
 * 
 * Provides utilities to:
 * - Check if a new endpoint is compatible with existing datasets
 * - Get compatibility metadata for endpoints
 * - Show warnings when adding incompatible datasets
 */

import { useState, useCallback } from 'react';
import { 
  useDataWorkspaceStore, 
  fetchEndpointMetadata, 
  checkEndpointCompatibility,
  CompatibilityResult 
} from '@/features/canvas/data-workspace/stores/dataWorkspaceStore';
import { selectDatasets } from '@/features/canvas/data-workspace/stores/selectors';

export interface EndpointMetadata {
  endpoint: string;
  structureType: string;
  compatibilityGroup: string;
  timeKey: string | null;
  cardinality: 'single' | 'multi' | 'none';
}

export interface CompatibilityCheckState {
  isChecking: boolean;
  result: CompatibilityResult | null;
  metadata: EndpointMetadata | null;
}

/**
 * Hook to check compatibility before adding a dataset.
 * 
 * Usage:
 * ```tsx
 * const { checkCompatibility, result, isChecking } = useDatasetCompatibility();
 * 
 * const handleAddDataset = async (endpoint: string) => {
 *   const compat = await checkCompatibility(endpoint);
 *   if (!compat.compatible) {
 *     showWarning(compat.reason);
 *   }
 *   // proceed with adding...
 * };
 * ```
 */
export function useDatasetCompatibility() {
  const [state, setState] = useState<CompatibilityCheckState>({
    isChecking: false,
    result: null,
    metadata: null,
  });
  
  const datasets = useDataWorkspaceStore(selectDatasets);
  const getActiveSheetCompatibilityGroup = useDataWorkspaceStore(state => state.getActiveSheetCompatibilityGroup);
  
  /**
   * Check if an endpoint is compatible with the current sheet's datasets.
   */
  const checkCompatibility = useCallback(async (endpoint: string): Promise<CompatibilityResult> => {
    setState(prev => ({ ...prev, isChecking: true }));
    
    try {
      // Fetch metadata for the new endpoint
      const metadata = await fetchEndpointMetadata(endpoint);
      
      // Get the current sheet's compatibility group
      const sheetGroup = getActiveSheetCompatibilityGroup();
      
      // No datasets yet - everything is compatible
      if (datasets.length === 0 || !sheetGroup || sheetGroup === 'unknown') {
        const result: CompatibilityResult = { 
          compatible: true, 
          group: metadata.compatibilityGroup 
        };
        setState({ isChecking: false, result, metadata });
        return result;
      }
      
      // Check if the new endpoint's group matches the sheet's group
      if (metadata.compatibilityGroup === sheetGroup) {
        const result: CompatibilityResult = { 
          compatible: true, 
          group: sheetGroup 
        };
        setState({ isChecking: false, result, metadata });
        return result;
      }
      
      // Groups don't match - not compatible
      const result: CompatibilityResult = {
        compatible: false,
        group: metadata.compatibilityGroup,
        groups: [sheetGroup, metadata.compatibilityGroup],
        reason: `This endpoint belongs to the "${metadata.compatibilityGroup}" group, but the current sheet contains "${sheetGroup}" data. These datasets have different time structures and cannot be merged.`,
      };
      setState({ isChecking: false, result, metadata });
      return result;
      
    } catch (error) {
      console.error('Compatibility check failed:', error);
      // Fail open - allow the dataset
      const result: CompatibilityResult = { compatible: true };
      setState({ isChecking: false, result, metadata: null });
      return result;
    }
  }, [datasets, getActiveSheetCompatibilityGroup]);
  
  /**
   * Check compatibility for multiple endpoints at once.
   */
  const checkMultipleCompatibility = useCallback(async (endpoints: string[]): Promise<CompatibilityResult> => {
    setState(prev => ({ ...prev, isChecking: true }));
    
    try {
      const result = await checkEndpointCompatibility(endpoints);
      setState({ isChecking: false, result, metadata: null });
      return result;
    } catch (error) {
      console.error('Compatibility check failed:', error);
      const result: CompatibilityResult = { compatible: true };
      setState({ isChecking: false, result, metadata: null });
      return result;
    }
  }, []);
  
  /**
   * Get descriptive text for a compatibility group.
   */
  const getGroupDescription = useCallback((group: string): string => {
    const descriptions: Record<string, string> = {
      'fiscal_period': 'Fiscal period data (quarterly/annual reports)',
      'daily_series': 'Daily trading data (prices, volumes)',
      'point_in_time': 'Snapshot data (current state)',
      'event_list': 'Event-based records (earnings, news)',
      'market_wide': 'Market-wide data (no specific ticker)',
      'options': 'Options chain data',
      'crypto': 'Cryptocurrency data',
      'commodity': 'Commodity market data',
      'forex': 'Foreign exchange data',
      'filing': 'SEC filing documents',
      'intraday': 'Intraday price data',
      'technical': 'Technical indicator series',
      'unknown': 'Unknown data structure',
    };
    return descriptions[group] || group;
  }, []);
  
  return {
    ...state,
    checkCompatibility,
    checkMultipleCompatibility,
    getGroupDescription,
  };
}

/**
 * Hook to get compatibility group colors for UI display.
 */
export function useCompatibilityGroupColors() {
  const getColor = useCallback((group: string): { bg: string; text: string; border: string } => {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
      'fiscal_period': { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
      'daily_series': { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
      'point_in_time': { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
      'event_list': { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
      'market_wide': { bg: 'bg-slate-50', text: 'text-slate-700', border: 'border-slate-200' },
      'options': { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
      'crypto': { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
      'commodity': { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
      'forex': { bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
      'filing': { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
      'intraday': { bg: 'bg-teal-50', text: 'text-teal-700', border: 'border-teal-200' },
      'technical': { bg: 'bg-fuchsia-50', text: 'text-fuchsia-700', border: 'border-fuchsia-200' },
    };
    return colors[group] || { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' };
  }, []);
  
  return { getColor };
}

export default useDatasetCompatibility;

