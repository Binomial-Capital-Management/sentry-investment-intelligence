import { useDataWorkspaceStore } from '../dataWorkspaceStore';
import { selectDatasets, selectSymbols } from '../selectors';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Mock localStorage for Node environment
const createStorageMock = () => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((i: number) => Object.keys(store)[i] || null),
  };
};

const localStorageMock = createStorageMock();

// @ts-ignore - mocking global
global.localStorage = localStorageMock;

// Mock fetch for addDatasetWithMetadata
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      endpoint: '/api/test',
      structure_type: 'time_series',
      compatibility_group: 'price',
      time_key: 'date',
      cardinality: 'multi',
    }),
  })
) as any;

describe('Critical Paths - Single Source of Truth (Tabs)', () => {
  beforeEach(() => {
    // Clear localStorage and reset store
    localStorageMock.clear();
    vi.clearAllMocks();
    
    // Reset store to initial state
    const store = useDataWorkspaceStore.getState();
    store.resetWorkspace();
  });

  afterEach(() => {
    localStorageMock.clear();
  });

  describe('Tab Switching', () => {
    it('preserves dataset state when switching tabs', () => {
      const store = useDataWorkspaceStore.getState();
      
      // Add dataset to tab 1
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/test',
        params: {},
        fields: ['price', 'volume'],
      });
      
      const tab1Id = store.activeTabId;
      
      // Verify using selectors
      let state = useDataWorkspaceStore.getState();
      expect(selectDatasets(state)).toHaveLength(1);
      
      // Create and switch to tab 2
      const tab2Id = state.addTab('single', 'Tab 2');
      
      // Verify switch happened
      state = useDataWorkspaceStore.getState();
      expect(state.activeTabId).toBe(tab2Id);
      
      // Tab 2 should be empty (via selector)
      expect(selectDatasets(state)).toHaveLength(0);
      
      // Switch back to tab 1
      state.setActiveTab(tab1Id!);
      
      // Tab 1 should still have its dataset (via selector)
      state = useDataWorkspaceStore.getState();
      expect(selectDatasets(state)).toHaveLength(1);
      expect(selectDatasets(state)[0].symbol).toBe('AAPL');
    });

    it('maintains correct activeTabId after multiple tab operations', () => {
      const store = useDataWorkspaceStore.getState();
      
      const tab1Id = store.activeTabId;
      const tab2Id = store.addTab('multi', 'Tab 2');
      
      // After addTab, we need to get fresh state
      let currentStore = useDataWorkspaceStore.getState();
      const tab3Id = currentStore.addTab('single', 'Tab 3');
      
      currentStore = useDataWorkspaceStore.getState();
      expect(currentStore.activeTabId).toBe(tab3Id);
      
      currentStore.setActiveTab(tab1Id!);
      currentStore = useDataWorkspaceStore.getState();
      expect(currentStore.activeTabId).toBe(tab1Id);
      
      currentStore.removeTab(tab2Id);
      currentStore = useDataWorkspaceStore.getState();
      expect(currentStore.activeTabId).toBe(tab1Id); // Should stay on tab1
      
      currentStore.removeTab(tab1Id!);
      currentStore = useDataWorkspaceStore.getState();
      expect(currentStore.activeTabId).toBe(tab3Id); // Should switch to remaining tab
    });
  });

  describe('Dataset Management via Selectors', () => {
    it('selectDatasets returns active tab datasets', () => {
      const store = useDataWorkspaceStore.getState();
      
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      let state = useDataWorkspaceStore.getState();
      const datasets = selectDatasets(state);
      
      expect(datasets).toHaveLength(1);
      expect(datasets[0].symbol).toBe('AAPL');
    });

    it('selectSymbols returns active tab symbols', () => {
      const store = useDataWorkspaceStore.getState();
      
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      let state = useDataWorkspaceStore.getState();
      state.addDataset({
        symbol: 'MSFT',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      state = useDataWorkspaceStore.getState();
      const symbols = selectSymbols(state);
      
      expect(symbols).toHaveLength(2);
      expect(symbols.map(s => s.symbol).sort()).toEqual(['AAPL', 'MSFT']);
    });

    it('prevents duplicate datasets (same symbol + endpoint)', () => {
      const store = useDataWorkspaceStore.getState();
      
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      // Get fresh state
      let state = useDataWorkspaceStore.getState();
      
      // Try to add duplicate
      state.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['open'],
      });
      
      state = useDataWorkspaceStore.getState();
      expect(selectDatasets(state)).toHaveLength(1);
    });

    it('removes dataset and cleans up orphaned symbols', () => {
      const store = useDataWorkspaceStore.getState();
      
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      let state = useDataWorkspaceStore.getState();
      
      state.addDataset({
        symbol: 'MSFT',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      state = useDataWorkspaceStore.getState();
      expect(selectSymbols(state)).toHaveLength(2);
      
      // Remove AAPL dataset
      const aaplDataset = selectDatasets(state).find(d => d.symbol === 'AAPL');
      state.removeDataset(aaplDataset!.id);
      
      state = useDataWorkspaceStore.getState();
      expect(selectDatasets(state)).toHaveLength(1);
      expect(selectSymbols(state)).toHaveLength(1);
      expect(selectSymbols(state)[0].symbol).toBe('MSFT');
    });
  });

  describe('Form State Persistence', () => {
    it('saves and retrieves form state per tab', () => {
      const store = useDataWorkspaceStore.getState();
      const tab1Id = store.activeTabId!;
      
      // Save form state to tab 1
      store.saveTabFormState(tab1Id, {
        single: {
          formMode: 'symbol',
          formSelectedSymbol: { symbol: 'AAPL', name: 'Apple', objectType: 'equity' },
          formCustomIdentifier: '',
          formSelectedEndpoint: null,
          formSelectedFields: ['close', 'volume'],
          formParams: {},
          formExpandedCategories: ['price'],
          formSourceFilter: 'all',
        },
      });
      
      let currentStore = useDataWorkspaceStore.getState();
      
      // Create new tab
      const tab2Id = currentStore.addTab('single', 'Tab 2');
      currentStore = useDataWorkspaceStore.getState();
      
      // Tab 2 should NOT have tab 1's form state (no leaking)
      expect(currentStore.getTabFormState(tab2Id)?.single).toBeUndefined();
      
      // Tab 1 should still have its form state
      const tab1FormState = currentStore.getTabFormState(tab1Id);
      expect(tab1FormState?.single?.formSelectedSymbol?.symbol).toBe('AAPL');
      expect(tab1FormState?.single?.formSelectedFields).toEqual(['close', 'volume']);
    });
  });

  describe('Reset Workspace', () => {
    it('clears all data and creates fresh default tab', () => {
      const store = useDataWorkspaceStore.getState();
      
      // Add multiple tabs and datasets
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      let currentStore = useDataWorkspaceStore.getState();
      currentStore.addTab('multi', 'Tab 2');
      
      currentStore = useDataWorkspaceStore.getState();
      currentStore.addDataset({
        symbol: 'MSFT',
        endpoint: '/api/fundamentals',
        params: {},
        fields: ['revenue'],
      });
      
      currentStore = useDataWorkspaceStore.getState();
      expect(currentStore.tabs).toHaveLength(2);
      
      // Reset
      currentStore.resetWorkspace();
      
      const state = useDataWorkspaceStore.getState();
      expect(state.tabs).toHaveLength(1);
      expect(selectDatasets(state)).toHaveLength(0);
      expect(selectSymbols(state)).toHaveLength(0);
      expect(state.tabs[0].mode).toBe('empty');
    });
  });

  describe('Pivot/Chart References', () => {
    it('pivot tab references correct source tab', () => {
      const store = useDataWorkspaceStore.getState();
      
      // Add data to first tab
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close', 'volume'],
      });
      
      let currentStore = useDataWorkspaceStore.getState();
      const sourceTabId = currentStore.activeTabId;
      
      // Create pivot tab referencing the source
      const pivotTabId = currentStore.createPivotTab(sourceTabId!, 'legacy-sheet', {
        rows: ['date'],
        values: [{ field: 'close', aggregation: 'avg' }],
      });
      
      currentStore = useDataWorkspaceStore.getState();
      
      // Verify pivot config points to correct source
      const pivotTab = currentStore.tabs.find(t => t.id === pivotTabId);
      expect(pivotTab?.pivotConfig?.sourceTabId).toBe(sourceTabId);
    });

    it('chart result is added to source tab with correct config', () => {
      const store = useDataWorkspaceStore.getState();

      // Add data to first tab
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close', 'volume'],
      });

      let currentStore = useDataWorkspaceStore.getState();
      const sourceTabId = currentStore.activeTabId;

      // Create chart (now adds inline result instead of new tab)
      const chartLocalId = currentStore.createChartTab(sourceTabId!, 'legacy-sheet', {
        chartType: 'line',
        xAxis: 'date',
        ySeries: [{ field: 'close' }],
      });

      currentStore = useDataWorkspaceStore.getState();

      // Verify chart result was added to the source tab
      const sourceTab = currentStore.tabs.find(t => t.id === sourceTabId);
      const chartResult = sourceTab?.chartResults?.find(cr => cr.localId === chartLocalId);
      expect(chartResult).toBeDefined();
      expect(chartResult?.config?.sourceTabId).toBe(sourceTabId);
      expect(chartResult?.config?.chartType).toBe('line');

      // Verify contentView points to the chart
      expect(sourceTab?.contentView?.type).toBe('chart');
      if (sourceTab?.contentView?.type === 'chart') {
        expect(sourceTab.contentView.chartLocalId).toBe(chartLocalId);
      }
    });

    it('loadTabs remaps pivot tab references correctly', () => {
      const store = useDataWorkspaceStore.getState();
      
      // Add data to first tab
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close', 'volume'],
      });
      
      let currentStore = useDataWorkspaceStore.getState();
      const sourceTabId = currentStore.activeTabId;
      
      // Create pivot tab referencing the source
      const pivotTabId = currentStore.createPivotTab(sourceTabId!, 'legacy-sheet', {
        rows: ['date'],
        values: [{ field: 'close', aggregation: 'avg' }],
      });
      
      currentStore = useDataWorkspaceStore.getState();
      
      // Simulate reload via loadTabs (which remaps IDs)
      const tabsToLoad = JSON.parse(JSON.stringify(currentStore.tabs));
      currentStore.resetWorkspace();
      
      currentStore = useDataWorkspaceStore.getState();
      currentStore.loadTabs(tabsToLoad, pivotTabId);
      
      // After reload, pivot should still reference correct source
      // (IDs will be different, but relationship preserved)
      const reloadedState = useDataWorkspaceStore.getState();
      const reloadedPivotTab = reloadedState.tabs.find(t => t.type === 'pivot');
      const reloadedSourceTab = reloadedState.tabs.find(t => t.type === 'single');
      
      expect(reloadedPivotTab?.pivotConfig?.sourceTabId).toBe(reloadedSourceTab?.id);
    });
  });

  describe('Async Race Conditions', () => {
    it('addDatasetWithMetadata targets correct tab even if tab switches during async', async () => {
      const store = useDataWorkspaceStore.getState();
      const tab1Id = store.activeTabId;
      
      // Start async add (will take time due to metadata fetch)
      const addPromise = store.addDatasetWithMetadata({
        symbol: 'AAPL',
        endpoint: '/api/test',
        params: {},
        fields: ['price'],
      });
      
      // Immediately switch tabs (simulating user action during async)
      let currentStore = useDataWorkspaceStore.getState();
      const tab2Id = currentStore.addTab('single', 'Tab 2');
      
      // Wait for async to complete
      await addPromise;
      
      // Re-fetch state after async
      currentStore = useDataWorkspaceStore.getState();
      
      // Dataset should be in tab 1 (where it was initiated), NOT tab 2
      const tab1Datasets = currentStore.tabs.find(t => t.id === tab1Id)?.datasets;
      const tab2Datasets = currentStore.tabs.find(t => t.id === tab2Id)?.datasets;
      
      // After refactor: dataset lands in the correct tab
      expect(tab1Datasets).toHaveLength(1);
      expect(tab2Datasets).toHaveLength(0);
      expect(tab1Datasets![0].symbol).toBe('AAPL');
    });
  });

  describe('No Flat State Leakage', () => {
    it('tab data is isolated - adding to one tab does not affect another', () => {
      const store = useDataWorkspaceStore.getState();
      const tab1Id = store.activeTabId;
      
      // Add to tab 1
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      let state = useDataWorkspaceStore.getState();
      
      // Create tab 2 and switch to it
      state.addTab('single', 'Tab 2');
      state = useDataWorkspaceStore.getState();
      
      // Add different data to tab 2
      state.addDataset({
        symbol: 'MSFT',
        endpoint: '/api/fundamentals',
        params: {},
        fields: ['revenue'],
      });
      
      state = useDataWorkspaceStore.getState();
      
      // Tab 2 (active) should only have MSFT
      expect(selectDatasets(state)).toHaveLength(1);
      expect(selectDatasets(state)[0].symbol).toBe('MSFT');
      
      // Tab 1 should still only have AAPL
      const tab1Data = state.tabs.find(t => t.id === tab1Id)?.datasets;
      expect(tab1Data).toHaveLength(1);
      expect(tab1Data![0].symbol).toBe('AAPL');
    });

    it('switching tabs changes selector results correctly', () => {
      const store = useDataWorkspaceStore.getState();
      const tab1Id = store.activeTabId;
      
      // Add to tab 1
      store.addDataset({
        symbol: 'AAPL',
        endpoint: '/api/price',
        params: {},
        fields: ['close'],
      });
      
      let state = useDataWorkspaceStore.getState();
      
      // Create tab 2
      const tab2Id = state.addTab('single', 'Tab 2');
      state = useDataWorkspaceStore.getState();
      
      // Add to tab 2
      state.addDataset({
        symbol: 'MSFT',
        endpoint: '/api/price',
        params: {},
        fields: ['open'],
      });
      
      state = useDataWorkspaceStore.getState();
      
      // Currently on tab 2 - selectors should return MSFT
      expect(selectDatasets(state).map(d => d.symbol)).toEqual(['MSFT']);
      
      // Switch to tab 1 - selectors should return AAPL
      state.setActiveTab(tab1Id!);
      state = useDataWorkspaceStore.getState();
      expect(selectDatasets(state).map(d => d.symbol)).toEqual(['AAPL']);
      
      // Switch back to tab 2 - selectors should return MSFT
      state.setActiveTab(tab2Id);
      state = useDataWorkspaceStore.getState();
      expect(selectDatasets(state).map(d => d.symbol)).toEqual(['MSFT']);
    });
  });
});
