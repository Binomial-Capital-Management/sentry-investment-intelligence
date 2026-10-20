/**
 * Form State Slice - Form persistence per tab
 * 
 * Handles saving and retrieving form state for each tab,
 * so form data persists when switching between tabs.
 * 
 * This slice provides:
 * - Granular setters for each form field (single source of truth)
 * - Batch updates for bulk changes
 * - Reset functionality
 */

import { StateCreator } from 'zustand';
import type { TabFormState, SingleObjectFormState, MultiObjectFormState, AddDatasetPanelState } from '../types';
import type { EndpointInfo, FormMode } from '@/features/canvas/types';
import type { CoreSlice } from './coreSlice';
import type { VisualizationSlice } from './visualizationSlice';

type SelectedSymbol = { symbol: string; name: string; objectType: string };

export interface FormStateSlice {
  // Bulk operations (keep for backward compatibility)
  saveTabFormState: (tabId: string, formState: TabFormState) => void;
  getTabFormState: (tabId: string) => TabFormState | undefined;
  
  // ============================================================================
  // SINGLE FORM ACTIONS - Operate on active tab's formState.single
  // ============================================================================
  setFormMode: (mode: FormMode) => void;
  setFormSelectedSymbol: (symbol: SelectedSymbol | null) => void;
  setFormCustomIdentifier: (identifier: string) => void;
  setFormSelectedEndpoint: (endpoint: EndpointInfo | null) => void;
  setFormSelectedFields: (fields: string[]) => void;
  setFormParams: (params: Record<string, string>) => void;
  setFormExpandedCategories: (categories: string[]) => void;
  setFormSourceFilter: (filter: string) => void;
  resetSingleForm: () => void;
  
  // ============================================================================
  // MULTI FORM ACTIONS - Operate on active tab's formState.multi
  // ============================================================================
  setMultiSelectedSymbols: (symbols: SelectedSymbol[]) => void;
  addMultiSelectedSymbol: (symbol: SelectedSymbol) => void;
  removeMultiSelectedSymbol: (symbolId: string) => void;
  setMultiSearchMode: (mode: 'symbol' | 'forex' | 'crypto') => void;
  setMultiEndpointSelectionMode: (mode: 'homogeneous' | 'heterogeneous') => void;
  setMultiSelectedEndpoint: (endpoint: EndpointInfo | null) => void;
  setMultiSelectedFields: (fields: string[]) => void;
  setMultiFormParams: (params: Record<string, string>) => void;
  setMultiExpandedCategories: (categories: string[]) => void;
  setMultiSourceFilter: (filter: string) => void;
  setMultiEndpointByType: (endpointByType: Record<string, any>) => void;
  setMultiFieldsByType: (fieldsByType: Record<string, string[]>) => void;
  setMultiParamsByType: (paramsByType: Record<string, Record<string, string>>) => void;
  setMultiExpandedCategoriesByType: (categoriesByType: Record<string, string[]>) => void;
  setMultiSourceFilterByType: (filterByType: Record<string, string>) => void;
  setMultiTargetGranularity: (granularity: string | undefined) => void;
  resetMultiForm: () => void;
  
  // ============================================================================
  // ADD DATA PANEL ACTIONS - Operate on active tab's formState.addDataPanel
  // ============================================================================
  setAddDataPanelEndpointMode: (mode: 'homogeneous' | 'heterogeneous') => void;
  setAddDataPanelSourceFilter: (filter: string) => void;
  // Homogeneous mode
  setAddDataPanelSelectedEndpoint: (endpoint: EndpointInfo | null) => void;
  setAddDataPanelSelectedFields: (fields: string[]) => void;
  setAddDataPanelFormParams: (params: Record<string, string>) => void;
  setAddDataPanelExpandedCategories: (categories: string[]) => void;
  // Heterogeneous mode
  setAddDataPanelSelectedEndpointByType: (endpointByType: Record<string, EndpointInfo | null>) => void;
  setAddDataPanelFieldsByType: (fieldsByType: Record<string, string[]>) => void;
  setAddDataPanelParamsByType: (paramsByType: Record<string, Record<string, string>>) => void;
  setAddDataPanelExpandedCategoriesByType: (categoriesByType: Record<string, string[]>) => void;
  // Scroll position
  setAddDataPanelScrollPosition: (position: number) => void;
  // Sidebar symbol selection
  setAddDataPanelFormMode: (mode: FormMode) => void;
  setAddDataPanelSelectedSymbol: (symbol: { symbol: string; name: string; objectType: string } | null) => void;
  setAddDataPanelCustomIdentifier: (identifier: string) => void;
  resetAddDataPanel: () => void;

  // Global fallback for add data panel when no tab is active
  globalAddDataPanel: AddDatasetPanelState;
}

type CombinedSlice = CoreSlice & VisualizationSlice & FormStateSlice;

// Default form states
const defaultSingleFormState: SingleObjectFormState = {
  formMode: 'symbol',
  formSelectedSymbol: null,
  formCustomIdentifier: '',
  formSelectedEndpoint: null,
  formSelectedFields: [],
  formParams: {},
  formExpandedCategories: [],
  formSourceFilter: 'all',
};

const defaultMultiFormState: MultiObjectFormState = {
  selectedSymbols: [],
  searchMode: 'symbol',
  endpointSelectionMode: 'homogeneous',
  selectedEndpoint: null,
  selectedFields: [],
  formParams: {},
  expandedCategories: [],
  sourceFilter: 'all',
  endpointByType: {},
  fieldsByType: {},
  paramsByType: {},
  expandedCategoriesByType: {},
  sourceFilterByType: {},
  targetGranularity: undefined,
};

const defaultAddDataPanelState: AddDatasetPanelState = {
  endpointSelectionMode: 'homogeneous',
  sourceFilter: 'all',
  selectedEndpoint: null,
  selectedFields: [],
  formParams: {},
  expandedCategories: [],
  selectedEndpointByType: {},
  fieldsByType: {},
  paramsByType: {},
  expandedCategoriesByType: {},
  scrollPosition: 0,
  sidebarFormMode: 'symbol',
  sidebarSelectedSymbol: null,
  sidebarCustomIdentifier: '',
};

// Helper to update single form state on active tab
function updateSingleForm(
  state: { tabs: any[]; activeTabId: string | null },
  updater: (current: SingleObjectFormState) => Partial<SingleObjectFormState>
) {
  const { tabs, activeTabId } = state;
  if (!activeTabId) return state;
  
  return {
    tabs: tabs.map(tab => {
      if (tab.id !== activeTabId) return tab;
      
      const currentSingle = tab.formState?.single ?? defaultSingleFormState;
      return {
        ...tab,
        formState: {
          ...tab.formState,
          single: { ...currentSingle, ...updater(currentSingle) },
        },
      };
    }),
    lastUpdated: new Date().toISOString(),
  };
}

// Helper to update multi form state on active tab
function updateMultiForm(
  state: { tabs: any[]; activeTabId: string | null },
  updater: (current: MultiObjectFormState) => Partial<MultiObjectFormState>
) {
  const { tabs, activeTabId } = state;
  if (!activeTabId) return state;
  
  return {
    tabs: tabs.map(tab => {
      if (tab.id !== activeTabId) return tab;
      
      const currentMulti = tab.formState?.multi ?? defaultMultiFormState;
      return {
        ...tab,
        formState: {
          ...tab.formState,
          multi: { ...currentMulti, ...updater(currentMulti) },
        },
      };
    }),
    lastUpdated: new Date().toISOString(),
  };
}

// Helper to update addDataPanel state on active tab
function updateAddDataPanel(
  state: { tabs: any[]; activeTabId: string | null; globalAddDataPanel: AddDatasetPanelState },
  updater: (current: AddDatasetPanelState) => Partial<AddDatasetPanelState>
) {
  const { tabs, activeTabId } = state;

  // No active tab — write to global fallback
  if (!activeTabId) {
    const current = state.globalAddDataPanel;
    return {
      globalAddDataPanel: { ...current, ...updater(current) },
      lastUpdated: new Date().toISOString(),
    };
  }

  return {
    tabs: tabs.map(tab => {
      if (tab.id !== activeTabId) return tab;

      const currentPanel = tab.formState?.addDataPanel ?? defaultAddDataPanelState;
      return {
        ...tab,
        formState: {
          ...tab.formState,
          addDataPanel: { ...currentPanel, ...updater(currentPanel) },
        },
      };
    }),
    lastUpdated: new Date().toISOString(),
  };
}

export const createFormStateSlice: StateCreator<
  CombinedSlice,
  [],
  [],
  FormStateSlice
> = (set, get) => ({
  // Global fallback for add data panel when no tab is active
  globalAddDataPanel: { ...defaultAddDataPanelState },

  // ============================================================================
  // BULK OPERATIONS (for backward compatibility and batch updates)
  // ============================================================================
  
  saveTabFormState: (tabId, formState) => {
    set(state => ({
      tabs: state.tabs.map(tab =>
        tab.id === tabId
          ? { ...tab, formState: { ...tab.formState, ...formState } }
          : tab
      ),
      lastUpdated: new Date().toISOString(),
    }));
  },
  
  getTabFormState: (tabId) => {
    const tab = get().tabs.find(t => t.id === tabId);
    return tab?.formState;
  },
  
  // ============================================================================
  // SINGLE FORM ACTIONS
  // ============================================================================
  
  setFormMode: (mode) => {
    set(state => updateSingleForm(state, () => ({ formMode: mode })));
  },
  
  setFormSelectedSymbol: (symbol) => {
    set(state => updateSingleForm(state, () => ({ formSelectedSymbol: symbol })));
  },
  
  setFormCustomIdentifier: (identifier) => {
    set(state => updateSingleForm(state, () => ({ formCustomIdentifier: identifier })));
  },
  
  setFormSelectedEndpoint: (endpoint) => {
    set(state => updateSingleForm(state, () => ({ formSelectedEndpoint: endpoint })));
  },
  
  setFormSelectedFields: (fields) => {
    set(state => updateSingleForm(state, () => ({ formSelectedFields: fields })));
  },
  
  setFormParams: (params) => {
    set(state => updateSingleForm(state, () => ({ formParams: params })));
  },
  
  setFormExpandedCategories: (categories) => {
    set(state => updateSingleForm(state, () => ({ formExpandedCategories: categories })));
  },
  
  setFormSourceFilter: (filter) => {
    set(state => updateSingleForm(state, () => ({ formSourceFilter: filter })));
  },
  
  resetSingleForm: () => {
    set(state => updateSingleForm(state, () => defaultSingleFormState));
  },
  
  // ============================================================================
  // MULTI FORM ACTIONS
  // ============================================================================
  
  setMultiSelectedSymbols: (symbols) => {
    set(state => updateMultiForm(state, () => ({ selectedSymbols: symbols })));
  },
  
  addMultiSelectedSymbol: (symbol) => {
    set(state => updateMultiForm(state, (current) => ({
      selectedSymbols: current.selectedSymbols.some(s => s.symbol === symbol.symbol)
        ? current.selectedSymbols
        : [...current.selectedSymbols, symbol],
    })));
  },
  
  removeMultiSelectedSymbol: (symbolId) => {
    set(state => updateMultiForm(state, (current) => ({
      selectedSymbols: current.selectedSymbols.filter(s => s.symbol !== symbolId),
    })));
  },
  
  setMultiSearchMode: (mode) => {
    set(state => updateMultiForm(state, () => ({ searchMode: mode })));
  },
  
  setMultiEndpointSelectionMode: (mode) => {
    set(state => updateMultiForm(state, () => ({ endpointSelectionMode: mode })));
  },
  
  setMultiSelectedEndpoint: (endpoint) => {
    set(state => updateMultiForm(state, () => ({ selectedEndpoint: endpoint })));
  },
  
  setMultiSelectedFields: (fields) => {
    set(state => updateMultiForm(state, () => ({ selectedFields: fields })));
  },
  
  setMultiFormParams: (params) => {
    set(state => updateMultiForm(state, () => ({ formParams: params })));
  },
  
  setMultiExpandedCategories: (categories) => {
    set(state => updateMultiForm(state, () => ({ expandedCategories: categories })));
  },
  
  setMultiSourceFilter: (filter) => {
    set(state => updateMultiForm(state, () => ({ sourceFilter: filter })));
  },
  
  setMultiEndpointByType: (endpointByType) => {
    set(state => updateMultiForm(state, () => ({ endpointByType })));
  },
  
  setMultiFieldsByType: (fieldsByType) => {
    set(state => updateMultiForm(state, () => ({ fieldsByType })));
  },
  
  setMultiParamsByType: (paramsByType) => {
    set(state => updateMultiForm(state, () => ({ paramsByType })));
  },
  
  setMultiExpandedCategoriesByType: (categoriesByType) => {
    set(state => updateMultiForm(state, () => ({ expandedCategoriesByType: categoriesByType })));
  },
  
  setMultiSourceFilterByType: (filterByType) => {
    set(state => updateMultiForm(state, () => ({ sourceFilterByType: filterByType })));
  },
  
  setMultiTargetGranularity: (granularity) => {
    set(state => updateMultiForm(state, () => ({ targetGranularity: granularity })));
  },
  
  resetMultiForm: () => {
    set(state => updateMultiForm(state, () => defaultMultiFormState));
  },
  
  // ============================================================================
  // ADD DATA PANEL ACTIONS
  // ============================================================================
  
  setAddDataPanelEndpointMode: (mode) => {
    set(state => updateAddDataPanel(state, () => ({ endpointSelectionMode: mode })));
  },
  
  setAddDataPanelSourceFilter: (filter) => {
    set(state => updateAddDataPanel(state, () => ({ sourceFilter: filter })));
  },
  
  setAddDataPanelSelectedEndpoint: (endpoint) => {
    set(state => updateAddDataPanel(state, () => ({ selectedEndpoint: endpoint })));
  },
  
  setAddDataPanelSelectedFields: (fields) => {
    set(state => updateAddDataPanel(state, () => ({ selectedFields: fields })));
  },
  
  setAddDataPanelFormParams: (params) => {
    set(state => updateAddDataPanel(state, () => ({ formParams: params })));
  },
  
  setAddDataPanelExpandedCategories: (categories) => {
    set(state => updateAddDataPanel(state, () => ({ expandedCategories: categories })));
  },
  
  setAddDataPanelSelectedEndpointByType: (endpointByType) => {
    set(state => updateAddDataPanel(state, () => ({ selectedEndpointByType: endpointByType })));
  },
  
  setAddDataPanelFieldsByType: (fieldsByType) => {
    set(state => updateAddDataPanel(state, () => ({ fieldsByType })));
  },
  
  setAddDataPanelParamsByType: (paramsByType) => {
    set(state => updateAddDataPanel(state, () => ({ paramsByType })));
  },
  
  setAddDataPanelExpandedCategoriesByType: (categoriesByType) => {
    set(state => updateAddDataPanel(state, () => ({ expandedCategoriesByType: categoriesByType })));
  },
  
  setAddDataPanelScrollPosition: (position) => {
    set(state => updateAddDataPanel(state, () => ({ scrollPosition: position })));
  },

  setAddDataPanelFormMode: (mode) => {
    set(state => updateAddDataPanel(state, () => ({ sidebarFormMode: mode })));
  },

  setAddDataPanelSelectedSymbol: (symbol) => {
    set(state => updateAddDataPanel(state, () => ({ sidebarSelectedSymbol: symbol })));
  },

  setAddDataPanelCustomIdentifier: (identifier) => {
    set(state => updateAddDataPanel(state, () => ({ sidebarCustomIdentifier: identifier })));
  },

  resetAddDataPanel: () => {
    set(state => updateAddDataPanel(state, () => defaultAddDataPanelState));
  },
});
