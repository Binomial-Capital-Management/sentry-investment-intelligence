/**
 * MultiObjectForm - Form for adding multiple object datasets
 * 
 * Supports two modes:
 * 1. HOMOGENEOUS: Same endpoint for all types (e.g., historical-price for equity + crypto)
 * 2. HETEROGENEOUS: Different endpoint per type (e.g., income-statement for equity + fx-historical for forex)
 * 
 * Refactored to be a controlled component - all state managed by useMultiObjectForm hook
 */

import { useMemo } from 'react';
import type { 
  EndpointInfo, 
  Granularity, 
  EquivalenceGroup,
  EndpointTimeInfo,
  TimeGroupEndpoints,
  JoinStrategy,
} from '@/features/canvas/types';
import { EndpointBrowser, FieldSelector, ParametersForm, GranularitySelector, StructureTypeWarning, SourceFilter, ModeSelector, SymbolSearchInput, type ModeOption } from './inputs';
import { resolveEndpointForType } from '../utils/queryUtils';
import type { TimeStructure } from '@/utils/compatibilityMatrix';

type SearchMode = 'symbol' | 'forex' | 'crypto';

const MULTI_FORM_MODES: ModeOption<SearchMode>[] = [
  { mode: 'symbol', label: 'Stock/ETF', color: 'blue' },
  { mode: 'forex', label: 'Forex', color: 'green' },
  { mode: 'crypto', label: 'Crypto', color: 'orange' },
];

interface SelectedSymbol {
  symbol: string;
  name: string;
  objectType: string;
}

interface DatasetConfig {
  symbol: string;
  endpoint: string;
  params: Record<string, string>;
  fields: string[];
  category: string;
}

type EndpointSelectionMode = 'homogeneous' | 'heterogeneous';

interface MultiObjectFormProps {
  // Search mode
  searchMode: SearchMode;
  setSearchMode: (mode: SearchMode) => void;
  
  // Symbol selection
  selectedSymbols: SelectedSymbol[];
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  showDropdown: boolean;
  setShowDropdown: (show: boolean) => void;
  symbolResults: Array<{ symbol: string; name: string; exchange?: string }>;
  onSearchSymbol: (query: string) => void;
  handleSelectSymbol: (result: { symbol: string; name: string; exchange?: string }) => void;
  handleRemoveSymbol: (symbol: string) => void;
  
  // Forex pairs
  loadingForexPairs: boolean;
  forexDropdownOpen: boolean;
  setForexDropdownOpen: (open: boolean) => void;
  forexSearch: string;
  setForexSearch: (search: string) => void;
  filteredForexPairs: string[];
  handleAddForexPair: (pair: string) => void;
  
  // Crypto pairs
  loadingCryptoPairs: boolean;
  cryptoDropdownOpen: boolean;
  setCryptoDropdownOpen: (open: boolean) => void;
  cryptoSearch: string;
  setCryptoSearch: (search: string) => void;
  filteredCryptoPairs: string[];
  handleAddCryptoPair: (pair: string) => void;
  
  // Endpoint selection mode
  endpointSelectionMode: EndpointSelectionMode;
  setEndpointSelectionMode: (mode: EndpointSelectionMode) => void;
  hasMultipleObjectTypes: boolean;
  
  // HOMOGENEOUS MODE endpoints
  loadingEndpoints: boolean;
  endpointsByCategory: Record<string, EndpointInfo[]>;
  displayEndpoints: EndpointInfo[];
  expandedCategories: Set<string>;
  toggleCategory: (category: string) => void;
  selectedEndpoint: EndpointInfo | null;
  handleEndpointSelect: (ep: EndpointInfo) => void;
  equivalenceGroups: EquivalenceGroup[];
  
  // Source filter (homogeneous mode)
  sourceFilter?: string;
  setSourceFilter?: (filter: string) => void;
  endpointsBySource?: Record<string, number>;
  
  // HETEROGENEOUS MODE endpoints
  uniqueObjectTypes: string[];
  endpointsByTimeGroup: Record<string, TimeGroupEndpoints>;
  endpointByType: Record<string, EndpointTimeInfo | null>;
  joinableEndpointsByType: Record<string, EndpointTimeInfo[]>;
  endpointsByCategoryByType: Record<string, Record<string, EndpointTimeInfo[]>>;
  expandedCategoriesByType: Record<string, Set<string>>;
  handleEndpointSelectForType: (objectType: string, ep: EndpointTimeInfo | null) => void;
  toggleCategoryForType: (objectType: string, category: string) => void;
  joinStrategy: JoinStrategy | null;
  allTypesHaveEndpoint: boolean;
  isJoinCompatible: boolean;
  heterogeneousFieldInfo: { common: string[]; byType: Record<string, { endpoint: string; fields: string[] }> } | null;
  fieldsByType: Record<string, string[]>;
  paramsByType: Record<string, Record<string, string>>;
  setParamsForType: (objectType: string, params: Record<string, string>) => void;
  handleFieldToggleForType: (objectType: string, field: string) => void;
  handleSelectAllFieldsForType: (objectType: string) => void;
  
  // Source filter (heterogeneous mode)
  sourceFilterByType?: Record<string, string>;
  setSourceFilterByType?: (filterByType: Record<string, string>) => void;
  endpointsBySourceByType?: Record<string, Record<string, number>>;
  
  // Granularity alignment
  granularitiesDetected?: Granularity[];
  hasMixedGranularity?: boolean;
  targetGranularity?: Granularity | null;
  setTargetGranularity?: (g: Granularity) => void;
  
  // Structure type compatibility
  structureTypesDetected?: TimeStructure[];
  hasIncompatibleStructures?: boolean;
  incompatiblePairs?: [TimeStructure, TimeStructure][];
  endpointsByStructure?: Record<TimeStructure, string[]>;
  
  // Fields (homogeneous mode)
  selectedFields: string[];
  handleFieldToggle: (field: string) => void;
  handleSelectAllFields: () => void;
  formParams: Record<string, string>;
  setFormParams: (params: Record<string, string>) => void;
  
  // Submission
  submitting: boolean;
  setSubmitting: (submitting: boolean) => void;
  
  // Computed
  hasMinimumSymbols: boolean;
  hasAnySymbols: boolean;
  hasUnsavedData: boolean;
  
  // Actions
  onAddDataset: (config: DatasetConfig) => Promise<void>;
  onAddObject: (obj: { symbol: string; name: string; objectType: string }) => void;
  onClose: () => void;
  onCloseWithData?: () => void;
  onSuccess?: () => void;
}

export default function MultiObjectForm({
  // Search mode
  searchMode,
  setSearchMode,
  
  // Symbol selection
  selectedSymbols,
  searchQuery,
  setSearchQuery,
  showDropdown,
  setShowDropdown,
  symbolResults,
  onSearchSymbol,
  handleSelectSymbol,
  handleRemoveSymbol,
  
  // Forex pairs
  loadingForexPairs,
  forexDropdownOpen,
  setForexDropdownOpen,
  forexSearch,
  setForexSearch,
  filteredForexPairs,
  handleAddForexPair,
  
  // Crypto pairs
  loadingCryptoPairs,
  cryptoDropdownOpen,
  setCryptoDropdownOpen,
  cryptoSearch,
  setCryptoSearch,
  filteredCryptoPairs,
  handleAddCryptoPair,
  
  // Endpoint selection mode
  endpointSelectionMode,
  setEndpointSelectionMode,
  hasMultipleObjectTypes,
  
  // HOMOGENEOUS MODE endpoints
  loadingEndpoints,
  endpointsByCategory,
  displayEndpoints,
  expandedCategories,
  toggleCategory,
  selectedEndpoint,
  handleEndpointSelect,
  equivalenceGroups,
  
  // Source filter (homogeneous mode)
  sourceFilter = 'all',
  setSourceFilter,
  endpointsBySource = {},
  
  // HETEROGENEOUS MODE endpoints
  uniqueObjectTypes,
  endpointsByTimeGroup: _endpointsByTimeGroup,
  endpointByType,
  joinableEndpointsByType: _joinableEndpointsByType,
  endpointsByCategoryByType,
  expandedCategoriesByType,
  handleEndpointSelectForType,
  toggleCategoryForType,
  joinStrategy,
  allTypesHaveEndpoint,
  isJoinCompatible: _isJoinCompatible,
  heterogeneousFieldInfo: _heterogeneousFieldInfo,
  fieldsByType,
  paramsByType,
  setParamsForType,
  handleFieldToggleForType,
  handleSelectAllFieldsForType,
  
  // Source filter (heterogeneous mode)
  sourceFilterByType = {},
  setSourceFilterByType,
  endpointsBySourceByType = {},
  
  // Granularity alignment
  granularitiesDetected = [],
  hasMixedGranularity = false,
  targetGranularity = null,
  setTargetGranularity,
  
  // Structure type compatibility
  structureTypesDetected = [],
  hasIncompatibleStructures = false,
  incompatiblePairs = [],
  endpointsByStructure = { date: [], fiscal: [], snapshot: [], none: [] },
  
  // Fields (homogeneous mode)
  selectedFields,
  handleFieldToggle,
  handleSelectAllFields,
  formParams,
  setFormParams,
  
  // Submission
  submitting,
  setSubmitting,
  
  // Computed
  hasMinimumSymbols,
  hasAnySymbols,
  hasUnsavedData,
  
  // Actions
  onAddDataset,
  onAddObject,
  onClose,
  onCloseWithData,
  onSuccess,
}: MultiObjectFormProps) {
  // Filter out already-selected symbols from results
  const filteredResults = useMemo(() => {
    const selected = new Set(selectedSymbols.map(s => s.symbol));
    return symbolResults.filter(r => !selected.has(r.symbol));
  }, [symbolResults, selectedSymbols]);

  const handleSubmit = async () => {
    if (selectedSymbols.length < 2) return;
    
    setSubmitting(true);
    try {
      if (endpointSelectionMode === 'homogeneous') {
        // HOMOGENEOUS MODE: Same endpoint for all types
        if (!selectedEndpoint || selectedFields.length === 0) return;
        
        for (const symbol of selectedSymbols) {
          onAddObject({
            symbol: symbol.symbol,
            name: symbol.name,
            objectType: symbol.objectType,
          });

          const submitParams: Record<string, string> = { ...formParams };
          if (symbol.objectType === 'equity') {
            submitParams.symbol = symbol.symbol;
          } else if (symbol.objectType === 'forex') {
            submitParams.fx_ticker = symbol.symbol;
            submitParams.symbol = symbol.symbol;
          } else if (symbol.objectType === 'crypto') {
            submitParams.crypto_ticker = symbol.symbol;
            submitParams.symbol = symbol.symbol;
            submitParams.symbols = symbol.symbol;
          }

          const resolvedEndpoint = selectedEndpoint.equivalenceGroup
            ? resolveEndpointForType(selectedEndpoint.equivalenceGroup, symbol.objectType, equivalenceGroups)
            : selectedEndpoint.endpoint;

          await onAddDataset({
            symbol: symbol.symbol,
            endpoint: resolvedEndpoint,
            params: submitParams,
            fields: selectedFields,
            category: selectedEndpoint.category,
          });
        }
      } else {
        // HETEROGENEOUS MODE: Different endpoint per type
        if (!allTypesHaveEndpoint) return;
        
        for (const symbol of selectedSymbols) {
          const typeEndpoint = endpointByType[symbol.objectType];
          if (!typeEndpoint) continue;
          
          const typeFields = fieldsByType[symbol.objectType] || [];
          if (typeFields.length === 0) continue;
          
          onAddObject({
            symbol: symbol.symbol,
            name: symbol.name,
            objectType: symbol.objectType,
          });

          // Use user-edited params from paramsByType
          const submitParams: Record<string, string> = {
            ...(paramsByType[symbol.objectType] || {}),
          };
          
          // Add symbol identifiers
          if (symbol.objectType === 'equity') {
            submitParams.symbol = symbol.symbol;
          } else if (symbol.objectType === 'forex') {
            submitParams.fx_ticker = symbol.symbol;
            submitParams.symbol = symbol.symbol;
          } else if (symbol.objectType === 'crypto') {
            submitParams.crypto_ticker = symbol.symbol;
            submitParams.symbol = symbol.symbol;
            submitParams.symbols = symbol.symbol;
          }

          await onAddDataset({
            symbol: symbol.symbol,
            endpoint: typeEndpoint.endpoint,
            params: submitParams,
            fields: typeFields,
            category: typeEndpoint.category,
          });
        }
      }

      onSuccess?.();
    } catch (error) {
      console.error('Error adding datasets:', error);
    } finally {
      setSubmitting(false);
    }
  };

  // Compute disabled state based on mode
  const isHomogeneousReady = selectedEndpoint && selectedFields.length > 0;
  const isHeterogeneousReady = allTypesHaveEndpoint && 
    uniqueObjectTypes.every(ot => (fieldsByType[ot] || []).length > 0);
  
  const isDisabled = !hasMinimumSymbols || submitting || hasIncompatibleStructures ||
    (endpointSelectionMode === 'homogeneous' ? !isHomogeneousReady : !isHeterogeneousReady);

  const handleBack = () => {
    if (hasUnsavedData && onCloseWithData) {
      onCloseWithData();
    } else {
      onClose();
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50/50 overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={handleBack} className="text-slate-400 hover:text-slate-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
          </button>
          <span className="text-sm font-medium text-slate-900">
            Add Multi-Object Dataset
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSubmit}
            disabled={isDisabled}
            className="px-4 py-1.5 text-xs font-medium bg-slate-900 text-white rounded hover:bg-slate-800 disabled:opacity-50"
          >
            {submitting ? 'Adding...' : 'Add to Workspace'}
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left panel - Symbol selector + Endpoint browser */}
        <div className="w-80 border-r border-slate-200 bg-white flex flex-col">
          {/* Mode Selector */}
          <ModeSelector
            modes={MULTI_FORM_MODES}
            selectedMode={searchMode}
            onModeChange={(mode) => {
              setSearchMode(mode);
              setSearchQuery('');
              setShowDropdown(false);
              setForexDropdownOpen(false);
              setCryptoDropdownOpen(false);
            }}
          />

          {/* Symbol Input - changes based on mode */}
          <div className="p-4 border-b border-slate-100">
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              Add Symbols (minimum 2)
            </label>

            {/* Stock/ETF mode */}
            {searchMode === 'symbol' && (
              <SymbolSearchInput
                mode="additive"
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
                onSearch={onSearchSymbol}
                results={filteredResults}
                onSelect={handleSelectSymbol}
                showDropdown={showDropdown}
                onShowDropdownChange={setShowDropdown}
                placeholder="Search ticker to add..."
                maxResults={8}
                label=""
              />
            )}

            {/* Forex mode */}
            {searchMode === 'forex' && (
              <div className="relative">
                <div 
                  onClick={() => setForexDropdownOpen(!forexDropdownOpen)}
                  className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded cursor-pointer hover:bg-slate-100 transition-colors border border-slate-200"
                >
                  <span className="text-[10px] text-slate-400 w-8">FX</span>
                  <span className="flex-1 text-sm text-slate-400">
                    {loadingForexPairs ? 'Loading...' : 'Select pair to add'}
                  </span>
                  <svg className="w-3 h-3 text-slate-400" viewBox="0 0 12 12" fill="currentColor"><path d="M3 4.5L6 7.5L9 4.5"/></svg>
                </div>
                {forexDropdownOpen && (
                  <div className="absolute z-50 w-full mt-1 bg-white rounded shadow-lg border border-slate-100 overflow-hidden">
                    <input
                      type="text"
                      value={forexSearch}
                      onChange={e => setForexSearch(e.target.value.toUpperCase())}
                      placeholder="Search"
                      className="w-full px-3 py-2 text-xs border-b border-slate-100 focus:outline-none"
                      autoFocus
                    />
                    <div className="max-h-36 overflow-y-auto">
                      {filteredForexPairs.slice(0, 20).map(pair => {
                        const isSelected = selectedSymbols.some(s => s.symbol === pair);
                        return (
                          <div
                            key={pair}
                            onClick={() => handleAddForexPair(pair)}
                            className={`px-3 py-1.5 text-xs cursor-pointer ${isSelected ? 'bg-slate-100 text-slate-400' : 'hover:bg-slate-50'}`}
                          >
                            {pair.slice(0,3)}/{pair.slice(3)} {isSelected && '✓'}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Crypto mode */}
            {searchMode === 'crypto' && (
              <div className="relative">
                <div 
                  onClick={() => setCryptoDropdownOpen(!cryptoDropdownOpen)}
                  className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded cursor-pointer hover:bg-slate-100 transition-colors border border-slate-200"
                >
                  <span className="text-[10px] text-slate-400 w-12">Crypto</span>
                  <span className="flex-1 text-sm text-slate-400">
                    {loadingCryptoPairs ? 'Loading...' : 'Select pair to add'}
                  </span>
                  <svg className="w-3 h-3 text-slate-400" viewBox="0 0 12 12" fill="currentColor"><path d="M3 4.5L6 7.5L9 4.5"/></svg>
                </div>
                {cryptoDropdownOpen && (
                  <div className="absolute z-50 w-full mt-1 bg-white rounded shadow-lg border border-slate-100 overflow-hidden">
                    <input
                      type="text"
                      value={cryptoSearch}
                      onChange={e => setCryptoSearch(e.target.value.toUpperCase())}
                      placeholder="Search"
                      className="w-full px-3 py-2 text-xs border-b border-slate-100 focus:outline-none"
                      autoFocus
                    />
                    <div className="max-h-36 overflow-y-auto">
                      {filteredCryptoPairs.slice(0, 20).map(pair => {
                        const isSelected = selectedSymbols.some(s => s.symbol === pair);
                        return (
                          <div
                            key={pair}
                            onClick={() => handleAddCryptoPair(pair)}
                            className={`px-3 py-1.5 text-xs cursor-pointer ${isSelected ? 'bg-slate-100 text-slate-400' : 'hover:bg-slate-50'}`}
                          >
                            {pair.replace('USD','')}/USD {isSelected && '✓'}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {/* Selected symbols as chips */}
            {selectedSymbols.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedSymbols.map(s => (
                  <div
                    key={s.symbol}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 rounded-full text-sm"
                  >
                    <span className="font-mono font-medium text-slate-700">{s.symbol}</span>
                    <span className="text-[10px] text-slate-400">{s.objectType}</span>
                    <button
                      onClick={() => handleRemoveSymbol(s.symbol)}
                      className="ml-0.5 text-slate-400 hover:text-slate-600"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            {/* Minimum symbols message */}
            {!hasMinimumSymbols && (
              <div className="mt-3 flex items-center gap-2 p-2 bg-amber-50 rounded text-amber-700">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="text-xs">
                  {selectedSymbols.length === 0 
                    ? 'Add at least 2 symbols to enable cross-asset comparison'
                    : `Add ${2 - selectedSymbols.length} more symbol to continue`}
                </span>
              </div>
            )}
          </div>

          {/* Endpoint Selection - shows when 2+ symbols selected */}
          {hasMinimumSymbols && (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Mode toggle when multiple object types are selected */}
              {hasMultipleObjectTypes && hasMinimumSymbols && (
                <div className="p-4 pb-2 border-b border-slate-100">
                  <label className="block text-[10px] font-medium text-slate-500 mb-1.5 uppercase tracking-wide">
                    Endpoint Selection Mode
                  </label>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEndpointSelectionMode('homogeneous')}
                      className={`flex-1 px-2 py-1.5 text-[10px] font-medium rounded transition-colors ${
                        endpointSelectionMode === 'homogeneous'
                          ? 'bg-slate-900 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      Same Endpoint
                    </button>
                    <button
                      onClick={() => setEndpointSelectionMode('heterogeneous')}
                      className={`flex-1 px-2 py-1.5 text-[10px] font-medium rounded transition-colors ${
                        endpointSelectionMode === 'heterogeneous'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      Per-Type Endpoint
                    </button>
                  </div>
                  <p className="mt-1 text-[9px] text-slate-400">
                    {endpointSelectionMode === 'homogeneous'
                      ? 'Same endpoint for all symbols (e.g., prices for equity + crypto)'
                      : 'Different endpoint per type (e.g., financials + FX rates)'}
                  </p>
                </div>
              )}

              {/* HOMOGENEOUS MODE: Single endpoint browser */}
              {endpointSelectionMode === 'homogeneous' && (
                <>
                  <div className="p-4 pb-2">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <label className="text-xs font-medium text-slate-600">
                        {selectedEndpoint 
                          ? `${selectedEndpoint.endpoint}`
                          : 'Select an Endpoint'}
                      </label>
                      {/* Source filter */}
                      {setSourceFilter && (
                        <SourceFilter
                          sourceFilter={sourceFilter}
                          onSourceFilterChange={setSourceFilter}
                          endpointsBySource={endpointsBySource}
                        />
                      )}
                    </div>
                    {hasMinimumSymbols && (
                      <div className="text-[10px] text-slate-400">
                        Showing {displayEndpoints.length} endpoint{displayEndpoints.length !== 1 ? 's' : ''} compatible with all selected symbols
                      </div>
                    )}
                  </div>
                  
                  <EndpointBrowser
                    loading={loadingEndpoints}
                    endpointsByCategory={endpointsByCategory}
                    expandedCategories={expandedCategories}
                    onToggleCategory={toggleCategory}
                    selectedEndpoint={selectedEndpoint}
                    onEndpointSelect={handleEndpointSelect}
                    emptyMessage={hasMinimumSymbols 
                      ? 'No compatible endpoints found for selected symbols'
                      : 'No endpoints found'}
                  />
                </>
              )}

              {/* HETEROGENEOUS MODE: Per-type endpoint pickers */}
              {endpointSelectionMode === 'heterogeneous' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                  {/* Join strategy indicator at top */}
                  {allTypesHaveEndpoint && joinStrategy && (
                    <div className={`mx-4 mt-3 p-2 rounded text-xs flex-shrink-0 ${
                      joinStrategy.strategy === 'incompatible'
                        ? 'bg-red-50 text-red-700'
                        : joinStrategy.strategy === 'snapshot_stack'
                        ? 'bg-emerald-50 text-emerald-700'
                        : joinStrategy.needs_aggregation
                        ? 'bg-amber-50 text-amber-700'
                        : 'bg-emerald-50 text-emerald-700'
                    }`}>
                      {joinStrategy.strategy === 'incompatible' ? (
                        <>⚠️ {joinStrategy.error || 'Cannot join these endpoints'}</>
                      ) : joinStrategy.strategy === 'snapshot_stack' ? (
                        <>✓ Snapshot data - will stack by symbol</>
                      ) : joinStrategy.needs_aggregation ? (
                        <>⚙️ Will aggregate to {joinStrategy.aggregation_target}</>
                      ) : (
                        <>✓ Joinable on {joinStrategy.common_time_key}</>
                      )}
                    </div>
                  )}
                  
                  {/* Scrollable endpoint browsers per type */}
                  <div className="flex-1 overflow-auto">
                    {uniqueObjectTypes.map((objType) => {
                      const typeSymbols = selectedSymbols.filter(s => s.objectType === objType);
                      const selectedTypeEndpoint = endpointByType[objType];
                      const expandedCats = expandedCategoriesByType[objType] || new Set();
                      const categorized = endpointsByCategoryByType[objType] || {};
                      
                      // Convert EndpointTimeInfo to EndpointInfo format for EndpointBrowser
                      const endpointsByCategoryForBrowser: Record<string, EndpointInfo[]> = {};
                      Object.entries(categorized).forEach(([cat, eps]) => {
                        endpointsByCategoryForBrowser[cat] = eps.map(ep => ({
                          endpoint: ep.endpoint,
                          category: ep.category,
                          fields: ep.fields,
                          source: ep.source || 'fmp',
                          structureType: ep.structure_type,
                          granularity: ep.granularity,
                          required_params: ep.required_params || [],
                        }));
                      });
                      
                      // Convert selected endpoint
                      const selectedEndpointForBrowser: EndpointInfo | null = selectedTypeEndpoint ? {
                        endpoint: selectedTypeEndpoint.endpoint,
                        category: selectedTypeEndpoint.category,
                        fields: selectedTypeEndpoint.fields,
                        source: selectedTypeEndpoint.source || 'fmp',
                        structureType: selectedTypeEndpoint.structure_type,
                        granularity: selectedTypeEndpoint.granularity,
                        required_params: selectedTypeEndpoint.required_params || [],
                      } : null;
                      
                      const typeSourceFilter = sourceFilterByType[objType] || 'all';
                      const typeEndpointsBySource = endpointsBySourceByType[objType] || { all: 0, fmp: 0, polygon: 0, uw: 0 };
                      
                      return (
                        <div key={objType} className="border-b border-slate-100 last:border-b-0">
                          {/* Type header */}
                          <div className="p-3 bg-slate-50/50 sticky top-0 z-10">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-slate-700 uppercase">
                                  {objType}
                                </span>
                                <span className="text-[10px] text-slate-400">
                                  ({typeSymbols.map(s => s.symbol).join(', ')})
                                </span>
                              </div>
                              {selectedTypeEndpoint ? (
                                <button
                                  onClick={() => handleEndpointSelectForType(objType, null)}
                                  className="text-[10px] font-mono text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded hover:bg-emerald-100 flex items-center gap-1"
                                >
                                  {selectedTypeEndpoint.endpoint}
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                  </svg>
                                </button>
                              ) : setSourceFilterByType && (
                                <SourceFilter
                                  sourceFilter={typeSourceFilter}
                                  onSourceFilterChange={(filter) => setSourceFilterByType({ ...sourceFilterByType, [objType]: filter })}
                                  endpointsBySource={typeEndpointsBySource}
                                />
                              )}
                            </div>
                          </div>
                          
                          {/* Reuse EndpointBrowser component */}
                          <div className="max-h-48 overflow-y-auto">
                            <EndpointBrowser
                              loading={false}
                              endpointsByCategory={endpointsByCategoryForBrowser}
                              expandedCategories={expandedCats}
                              onToggleCategory={(cat) => toggleCategoryForType(objType, cat)}
                              selectedEndpoint={selectedEndpointForBrowser}
                              onEndpointSelect={(ep) => {
                                // Convert back to EndpointTimeInfo
                                const timeInfo = Object.values(categorized)
                                  .flat()
                                  .find(e => e.endpoint === ep.endpoint);
                                if (timeInfo) {
                                  handleEndpointSelectForType(objType, timeInfo);
                                }
                              }}
                              emptyMessage={`No endpoints available for ${objType}`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right panel - Fields & Params */}
        <div className="flex-1 flex flex-col bg-white overflow-hidden">
          {!hasAnySymbols ? (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
              Add symbols to see available endpoints
            </div>
          ) : endpointSelectionMode === 'homogeneous' && !selectedEndpoint ? (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
              Select an endpoint from the left panel
            </div>
          ) : endpointSelectionMode === 'heterogeneous' && !allTypesHaveEndpoint ? (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
              Select an endpoint for each object type
            </div>
          ) : endpointSelectionMode === 'homogeneous' && selectedEndpoint ? (
            /* HOMOGENEOUS MODE: Single endpoint field selection */
            <div className="flex-1 flex flex-col overflow-auto p-6">
              {/* Endpoint header */}
              <div className="mb-4 pb-4 border-b border-slate-100">
                <h3 className="text-sm font-medium text-slate-900 font-mono">{selectedEndpoint.endpoint}</h3>
                <p className="text-xs text-slate-500 mt-1">{selectedEndpoint.category}</p>
                {selectedEndpoint.equivalenceGroup && selectedEndpoint.equivalenceGroup !== selectedEndpoint.endpoint && (
                  <p className="text-[10px] text-emerald-600 mt-1">
                    ✓ Smart-matched via "{selectedEndpoint.equivalenceGroup}" equivalence group
                  </p>
                )}
                <p className="text-[10px] text-slate-400 mt-1">
                  Will fetch data for: {selectedSymbols.map(s => s.symbol).join(', ')}
                </p>
              </div>

              {/* Granularity alignment warning */}
              {hasMixedGranularity && setTargetGranularity && (
                <GranularitySelector
                  granularitiesDetected={granularitiesDetected}
                  selectedGranularity={targetGranularity}
                  onChange={setTargetGranularity}
                />
              )}

              {/* Field selection */}
              <FieldSelector
                fields={selectedEndpoint.fields}
                selectedFields={selectedFields}
                onFieldToggle={handleFieldToggle}
                onSelectAll={handleSelectAllFields}
              />

              {/* Parameters section */}
              <ParametersForm
                params={selectedEndpoint.required_params}
                formParams={formParams}
                onSetFormParams={setFormParams}
              />

              {/* Summary */}
              {selectedFields.length > 0 && (
                <div className="mt-6 p-3 bg-slate-50 rounded-lg">
                  <p className="text-xs text-slate-600">
                    <span className="font-medium">{selectedSymbols.length}</span> symbols × <span className="font-medium">{selectedFields.length}</span> fields = <span className="font-medium">{selectedSymbols.length}</span> datasets to create
                  </p>
                </div>
              )}
            </div>
          ) : (
            /* HETEROGENEOUS MODE: Per-type field selection */
            <div className="flex-1 flex flex-col overflow-auto p-6">
              {/* Header showing selected endpoints */}
              <div className="mb-4 pb-4 border-b border-slate-100">
                <h3 className="text-sm font-medium text-slate-900">Multi-Endpoint Join</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Select fields for each endpoint below
                </p>
                {joinStrategy?.needs_aggregation && (
                  <p className="text-[10px] text-amber-600 mt-1">
                    ⚙️ Data will be aggregated to {joinStrategy.aggregation_target} granularity
                  </p>
                )}
              </div>

              {/* Granularity selector for heterogeneous mode */}
              {hasMixedGranularity && setTargetGranularity && (
                <GranularitySelector
                  granularitiesDetected={granularitiesDetected}
                  selectedGranularity={targetGranularity}
                  onChange={setTargetGranularity}
                />
              )}

              {/* Structure type incompatibility warning */}
              {hasIncompatibleStructures && incompatiblePairs.length > 0 && (
                <StructureTypeWarning
                  structureTypesDetected={structureTypesDetected}
                  endpointsByStructure={endpointsByStructure}
                  incompatiblePairs={incompatiblePairs}
                />
              )}

              {/* Per-type field selection */}
              {uniqueObjectTypes.map((objType) => {
                const ep = endpointByType[objType];
                if (!ep) return null;
                
                const typeFields = fieldsByType[objType] || [];
                const typeSymbols = selectedSymbols.filter(s => s.objectType === objType);
                
                return (
                  <div key={objType} className="mb-6 last:mb-0">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-xs font-semibold text-slate-700 uppercase">
                          {objType}
                        </span>
                        <span className="ml-2 text-[10px] font-mono text-slate-500">
                          {ep.endpoint}
                        </span>
                      </div>
                      <button
                        onClick={() => handleSelectAllFieldsForType(objType)}
                        className="text-[10px] text-blue-600 hover:underline"
                      >
                        Select All
                      </button>
                    </div>
                    <div className="text-[10px] text-slate-400 mb-2">
                      Symbols: {typeSymbols.map(s => s.symbol).join(', ')}
                    </div>
                    <div className="grid grid-cols-2 gap-1 max-h-32 overflow-y-auto border border-slate-100 rounded p-2">
                      {ep.fields.map((field) => (
                        <label
                          key={field}
                          className="flex items-center gap-1.5 cursor-pointer hover:bg-slate-50 p-1 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={typeFields.includes(field)}
                            onChange={() => handleFieldToggleForType(objType, field)}
                            className="w-3 h-3 text-emerald-600 rounded"
                          />
                          <span className="text-xs text-slate-700 font-mono truncate">
                            {field}
                          </span>
                        </label>
                      ))}
                    </div>
                    <div className="mt-1 text-[10px] text-slate-400">
                      {typeFields.length} of {ep.fields.length} fields selected
                    </div>
                    
                    {/* Parameters for this type's endpoint */}
                    {ep.required_params && ep.required_params.length > 0 && (
                      <div className="mt-3">
                        <ParametersForm
                          params={ep.required_params}
                          formParams={paramsByType[objType] || {}}
                          onSetFormParams={(newParams) => setParamsForType(objType, newParams)}
                        />
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Summary */}
              {uniqueObjectTypes.every(ot => (fieldsByType[ot] || []).length > 0) && (
                <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                  <p className="text-xs text-slate-600">
                    <span className="font-medium">{selectedSymbols.length}</span> symbols across <span className="font-medium">{uniqueObjectTypes.length}</span> types → <span className="font-medium">{selectedSymbols.length}</span> datasets to create
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Re-export state interface for type compatibility
export type { MultiObjectFormProps };