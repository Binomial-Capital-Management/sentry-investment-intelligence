/**
 * Hook for pinning workspace items to Studio Sources
 * 
 * Used by Data Workspace components to pin tables, charts, etc.
 */

import { useChatStore } from '@/stores/chatStore';
import memoryApiService from '@/services/memoryApi';
import toast from 'react-hot-toast';

export interface PinTableParams {
  sheetId: string;
  sheetName: string;
  datasets: { symbol: string; endpoint: string }[];
  rowCount: number;
  columns?: string[];
}

export interface PinChartParams {
  chartId: string;
  chartType: string;
  title?: string;
  xAxis: string;
  ySeries: { field: string }[];
  sourceSheet?: string;
}

export interface PinDatasetParams {
  datasetId: string;
  symbol: string;
  endpoint: string;
  fields: string[];
}

export function usePinToSources() {
  const { currentThreadId } = useChatStore();

  const canPin = !!currentThreadId;

  const pinTable = async (params: PinTableParams) => {
    if (!currentThreadId) {
      toast.error('Open a chat first to pin sources');
      return false;
    }

    try {
      const datasetNames = params.datasets.map(d => d.symbol).join(', ') || 'Custom';
      
      await memoryApiService.createNote(currentThreadId, {
        content: `Table: ${params.sheetName}\nDatasets: ${datasetNames}\nRows: ${params.rowCount}`,
        reference_type: 'table',
        reference_metadata: {
          title: params.sheetName,
          subtitle: `${params.rowCount} rows · ${datasetNames}`,
          sheet_id: params.sheetId,
          datasets: params.datasets,
          columns: params.columns,
        }
      });
      
      toast.success(`Pinned "${params.sheetName}" to Sources`);
      return true;
    } catch (error) {
      console.error('Failed to pin table:', error);
      toast.error('Failed to pin table');
      return false;
    }
  };

  const pinChart = async (params: PinChartParams) => {
    if (!currentThreadId) {
      toast.error('Open a chat first to pin sources');
      return false;
    }

    try {
      const title = params.title || `${params.chartType} Chart`;
      
      await memoryApiService.createNote(currentThreadId, {
        content: `Chart: ${title}\nType: ${params.chartType}\nX-Axis: ${params.xAxis}\nSeries: ${params.ySeries.map(s => s.field).join(', ')}`,
        reference_type: 'chart',
        reference_metadata: {
          title,
          subtitle: `${params.chartType} · ${params.ySeries.length} series`,
          chart_id: params.chartId,
          chart_type: params.chartType,
          x_axis: params.xAxis,
          y_series: params.ySeries,
          source_sheet: params.sourceSheet,
        }
      });
      
      toast.success(`Pinned "${title}" to Sources`);
      return true;
    } catch (error) {
      console.error('Failed to pin chart:', error);
      toast.error('Failed to pin chart');
      return false;
    }
  };

  const pinDataset = async (params: PinDatasetParams) => {
    if (!currentThreadId) {
      toast.error('Open a chat first to pin sources');
      return false;
    }

    try {
      await memoryApiService.createNote(currentThreadId, {
        content: `Dataset: ${params.symbol} - ${params.endpoint}\nFields: ${params.fields.join(', ')}`,
        reference_type: 'dataset',
        reference_metadata: {
          title: `${params.symbol} ${params.endpoint}`,
          subtitle: `${params.fields.length} fields`,
          dataset_id: params.datasetId,
          symbol: params.symbol,
          endpoint: params.endpoint,
          fields: params.fields,
        }
      });
      
      toast.success(`Pinned ${params.symbol} dataset to Sources`);
      return true;
    } catch (error) {
      console.error('Failed to pin dataset:', error);
      toast.error('Failed to pin dataset');
      return false;
    }
  };

  return {
    canPin,
    pinTable,
    pinChart,
    pinDataset,
  };
}

