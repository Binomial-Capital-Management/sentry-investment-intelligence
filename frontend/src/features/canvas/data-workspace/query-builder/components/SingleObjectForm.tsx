/**
 * SingleObjectForm - Full form for adding a single object dataset
 * 
 * Handles:
 * - Symbol/Market/Options/Forex/Crypto mode selection
 * - Symbol search and selection
 * - Options contract builder with underlying, type, expiry, strike
 * - Forex and Crypto pair dropdowns with search
 * - Source filter tabs (All/FMP/Polygon/UW)
 * - Endpoint browsing by category
 * - Field selection
 * - Parameter configuration
 */

import { useMemo } from 'react';
import { CompatibilityWarning, TabCompatibilityIndicator } from '@/features/canvas/data-workspace/components/CompatibilityBadge';
import type { FormMode, EndpointInfo } from '@/features/canvas/types';
import { ForexDropdown, CryptoDropdown, EndpointBrowser, FieldSelector, ParametersForm, SourceFilter, ModeSelector, SymbolSearchInput, type ModeOption } from './inputs';

const SINGLE_FORM_MODES: ModeOption<FormMode>[] = [
  { mode: 'symbol', label: 'Stock/ETF', color: 'blue' },
  { mode: 'market', label: 'Market', color: 'slate' },
  { mode: 'options', label: 'Options', color: 'purple' },
  { mode: 'forex', label: 'Forex', color: 'green' },
  { mode: 'crypto', label: 'Crypto', color: 'orange' },
];

interface SingleObjectFormProps {
  // Mode
  formMode: FormMode;
  onSetFormMode: (mode: FormMode) => void;
  
  // Symbol state
  formSelectedSymbol: { symbol: string; name: string; objectType: string } | null;
  formSymbolSearch: string;
  formSymbolResults: Array<{ symbol: string; name: string; exchange?: string }>;
  onSetFormSymbolSearch: (search: string) => void;
  onSearchFormSymbol: (query: string) => void;
  onFormSymbolSelect: (result: { symbol: string; name: string; exchange?: string }) => void;
  onClearSelectedSymbol: () => void;
  
  // Custom identifier (options/forex/crypto)
  formCustomIdentifier: string;
  onSetFormCustomIdentifier?: (id: string) => void;
  
  // Endpoints
  formEndpoints: EndpointInfo[];
  formEndpointsLoading: boolean;
  formSelectedEndpoint: EndpointInfo | null;
  formExpandedCategories: Set<string>;
  onSetFormExpandedCategories: (categories: Set<string>) => void;
  onEndpointSelect: (ep: EndpointInfo) => void;
  onLoadFormEndpoints: (objectType: string) => void;
  
  // Fields
  formSelectedFields: string[];
  onFormFieldToggle: (field: string) => void;
  onSelectAllFields: () => void;
  
  // Source filter
  formSourceFilter?: string;
  onSetFormSourceFilter?: (filter: string) => void;
  formEndpointsBySource?: Record<string, number>;
  
  // Options builder state
  optionsUnderlying?: string;
  onSetOptionsUnderlying?: (underlying: string) => void;
  optionsUnderlyingSearch?: string;
  onSetOptionsUnderlyingSearch?: (search: string) => void;
  optionsUnderlyingResults?: Array<{ symbol: string; name: string }>;
  optionsUnderlyingDropdownOpen?: boolean;
  onSetOptionsUnderlyingDropdownOpen?: (open: boolean) => void;
  optionsType?: 'C' | 'P';
  onSetOptionsType?: (type: 'C' | 'P') => void;
  optionsExpiry?: string;
  onSetOptionsExpiry?: (expiry: string) => void;
  optionsExpirations?: string[];
  loadingExpirations?: boolean;
  optionsStrike?: string;
  onSetOptionsStrike?: (strike: string) => void;
  optionsExpiryDropdownOpen?: boolean;
  onSetOptionsExpiryDropdownOpen?: (open: boolean) => void;
  
  // Forex state
  forexPairs?: string[];
  forexDropdownOpen?: boolean;
  onSetForexDropdownOpen?: (open: boolean) => void;
  forexSearch?: string;
  onSetForexSearch?: (search: string) => void;
  filteredForexPairs?: string[];
  loadingForexPairs?: boolean;
  
  // Crypto state
  cryptoPairs?: string[];
  cryptoDropdownOpen?: boolean;
  onSetCryptoDropdownOpen?: (open: boolean) => void;
  cryptoSearch?: string;
  onSetCryptoSearch?: (search: string) => void;
  filteredCryptoPairs?: string[];
  loadingCryptoPairs?: boolean;
  
  // Parameters
  formParams?: Record<string, string>;
  onSetFormParams?: (params: Record<string, string>) => void;
  uwEnums?: Record<string, string[]>;
  onFetchUwEnum?: (enumName: string) => void;
  // UW Expirations (for options endpoints needing expiry param)
  uwExpirations?: Record<string, string[]>;
  uwExpirationsLoading?: Set<string>;
  onFetchUwExpirations?: (ticker: string) => void;
  
  // Compatibility
  compatibilityWarning: { tabGroup: string; newGroup: string; pendingConfig: any } | null;
  onCreateNewSheetForIncompatible: () => void;
  onDismissCompatibilityWarning: () => void;
  currentSheetCompatibilityGroup?: string | null;
  workspaceDatasetsCount?: number;
  
  // Actions
  editingDatasetId: string | null;
  onClose: () => void;
  onSubmit: () => void;
}

export default function SingleObjectForm({
  formMode,
  onSetFormMode,
  formSelectedSymbol,
  formSymbolSearch,
  formSymbolResults,
  onSetFormSymbolSearch,
  onSearchFormSymbol,
  onFormSymbolSelect,
  onClearSelectedSymbol,
  formCustomIdentifier,
  onSetFormCustomIdentifier,
  formEndpoints,
  formEndpointsLoading,
  formSelectedEndpoint,
  formExpandedCategories,
  onSetFormExpandedCategories,
  onEndpointSelect,
  onLoadFormEndpoints,
  formSelectedFields,
  onFormFieldToggle,
  onSelectAllFields,
  formSourceFilter = 'all',
  onSetFormSourceFilter,
  formEndpointsBySource = {},
  // Options
  optionsUnderlying = '',
  onSetOptionsUnderlying,
  optionsUnderlyingSearch = '',
  onSetOptionsUnderlyingSearch,
  optionsUnderlyingResults = [],
  optionsUnderlyingDropdownOpen = false,
  onSetOptionsUnderlyingDropdownOpen,
  optionsType = 'C',
  onSetOptionsType,
  optionsExpiry = '',
  onSetOptionsExpiry,
  optionsExpirations = [],
  loadingExpirations = false,
  optionsStrike = '',
  onSetOptionsStrike,
  optionsExpiryDropdownOpen = false,
  onSetOptionsExpiryDropdownOpen,
  // Forex
  forexPairs = [],
  forexDropdownOpen = false,
  onSetForexDropdownOpen,
  forexSearch = '',
  onSetForexSearch,
  filteredForexPairs,
  loadingForexPairs = false,
  // Crypto
  cryptoPairs = [],
  cryptoDropdownOpen = false,
  onSetCryptoDropdownOpen,
  cryptoSearch = '',
  onSetCryptoSearch,
  filteredCryptoPairs,
  loadingCryptoPairs = false,
  // Params
  formParams = {},
  onSetFormParams,
  uwEnums = {},
  onFetchUwEnum,
  uwExpirations = {},
  uwExpirationsLoading = new Set(),
  onFetchUwExpirations,
  compatibilityWarning,
  onCreateNewSheetForIncompatible,
  onDismissCompatibilityWarning,
  currentSheetCompatibilityGroup,
  workspaceDatasetsCount = 0,
  editingDatasetId,
  onClose,
  onSubmit,
}: SingleObjectFormProps) {
  // Group endpoints by category with source filtering
  const formEndpointsByCategory = useMemo(() => {
    const grouped: Record<string, EndpointInfo[]> = {};
    formEndpoints
      .filter(ep => {
        if (formSourceFilter === 'all') return true;
        // Normalize source: "unusualwhales" -> "uw"
        const normalizedSource = ep.source === 'unusualwhales' ? 'uw' : ep.source;
        return normalizedSource === formSourceFilter;
      })
      .forEach(ep => {
        const cat = ep.category || 'Other';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(ep);
      });
    return grouped;
  }, [formEndpoints, formSourceFilter]);

  // Use filteredForexPairs if provided, otherwise filter locally
  const displayForexPairs = useMemo(() => {
    if (filteredForexPairs) return filteredForexPairs;
    if (!forexSearch) return forexPairs;
    const search = forexSearch.toUpperCase();
    return forexPairs.filter(pair => pair.includes(search));
  }, [filteredForexPairs, forexPairs, forexSearch]);

  const displayCryptoPairs = useMemo(() => {
    if (filteredCryptoPairs) return filteredCryptoPairs;
    if (!cryptoSearch) return cryptoPairs;
    const search = cryptoSearch.toUpperCase();
    return cryptoPairs.filter(pair => pair.includes(search));
  }, [filteredCryptoPairs, cryptoPairs, cryptoSearch]);

  const isDisabled = !formSelectedEndpoint || 
    formSelectedFields.length === 0 || 
    (formMode === 'symbol' && !formSelectedSymbol) ||
    (formMode === 'options' && !formCustomIdentifier) ||
    (formMode === 'forex' && !formCustomIdentifier) ||
    (formMode === 'crypto' && !formCustomIdentifier);

  const handleModeChange = (mode: FormMode) => {
    onSetFormMode(mode);
    onClearSelectedSymbol();
    onSetFormCustomIdentifier?.('');
    // Reset dropdowns
    onSetForexDropdownOpen?.(false);
    onSetCryptoDropdownOpen?.(false);
    onSetForexSearch?.('');
    onSetCryptoSearch?.('');
    // Reset options
    onSetOptionsUnderlying?.('');
    onSetOptionsUnderlyingSearch?.('');
    onSetOptionsUnderlyingDropdownOpen?.(false);
    onSetOptionsType?.('C');
    onSetOptionsExpiry?.('');
    onSetOptionsStrike?.('');
    onSetOptionsExpiryDropdownOpen?.(false);
    // Load endpoints
    const objectType = mode === 'market' ? 'market' : 
                       mode === 'options' ? 'options' :
                       mode === 'forex' ? 'forex' :
                       mode === 'crypto' ? 'crypto' : 'equity';
    onLoadFormEndpoints(objectType);
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50/50 overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
          </button>
          <span className="text-sm font-medium text-slate-900">
            {editingDatasetId ? 'Edit Dataset' : 'Add Single Object Dataset'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Show sheet's compatibility group when adding to existing datasets */}
          {!editingDatasetId && workspaceDatasetsCount > 0 && currentSheetCompatibilityGroup && (
            <TabCompatibilityIndicator group={currentSheetCompatibilityGroup} />
          )}
          <button
            onClick={onSubmit}
            disabled={isDisabled}
            className="px-4 py-1.5 text-xs font-medium bg-slate-900 text-white rounded hover:bg-slate-800 disabled:opacity-50"
          >
            {editingDatasetId ? 'Save Changes' : 'Add to Workspace'}
          </button>
        </div>
      </div>

      {/* Compatibility Warning */}
      {compatibilityWarning && (
        <div className="px-6 pt-2">
          <CompatibilityWarning
            tabGroup={compatibilityWarning.tabGroup}
            newGroup={compatibilityWarning.newGroup}
            onCreateNewSheet={onCreateNewSheetForIncompatible}
            onDismiss={onDismissCompatibilityWarning}
          />
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Left panel - Identifier + Endpoint browser */}
        <div className="w-80 border-r border-slate-200 bg-white flex flex-col">
          {/* Mode Selector */}
          <ModeSelector
            modes={SINGLE_FORM_MODES}
            selectedMode={formMode}
            onModeChange={handleModeChange}
          />
          
          {/* Identifier Input - changes based on mode */}
          <div className="p-4 border-b border-slate-100">
            {/* Symbol mode */}
            {formMode === 'symbol' && (
              <SymbolSearchInput
                mode="single"
                searchQuery={formSymbolSearch}
                onSearchQueryChange={onSetFormSymbolSearch}
                onSearch={onSearchFormSymbol}
                results={formSymbolResults}
                onSelect={onFormSymbolSelect}
                selectedSymbol={formSelectedSymbol}
                onClearSelected={onClearSelectedSymbol}
                showDropdown={formSymbolResults.length > 0}
                onShowDropdownChange={() => {}}
                placeholder="Search ticker..."
              />
            )}

            {/* Market mode */}
            {formMode === 'market' && (
              <div className="py-2">
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                  <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
                  </svg>
                  <div>
                    <p className="text-xs font-medium text-slate-700">Market-wide data</p>
                    <p className="text-[10px] text-slate-500">No symbol needed - select an endpoint</p>
                  </div>
                </div>
              </div>
            )}

            {/* Options mode - Contract Builder */}
            {formMode === 'options' && (
              <div className="space-y-2">
                {/* Underlying */}
                <div className="relative">
                  <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded">
                    <span className="text-[10px] text-slate-400 w-12">Ticker</span>
                    <input
                      type="text"
                      value={optionsUnderlyingSearch}
                      onChange={e => { 
                        onSetOptionsUnderlyingSearch?.(e.target.value.toUpperCase()); 
                        onSetOptionsUnderlyingDropdownOpen?.(true); 
                      }}
                      onFocus={() => onSetOptionsUnderlyingDropdownOpen?.(true)}
                      placeholder="AAPL"
                      className="flex-1 text-sm font-medium bg-transparent focus:outline-none"
                    />
                    {optionsUnderlying && (
                      <span className="text-[10px] text-slate-500">{optionsUnderlying}</span>
                    )}
                  </div>
                  {optionsUnderlyingDropdownOpen && optionsUnderlyingResults.length > 0 && (
                    <div className="absolute z-50 w-full mt-1 bg-white rounded shadow-lg border border-slate-100 max-h-32 overflow-y-auto">
                      {optionsUnderlyingResults.map(r => (
                        <div 
                          key={r.symbol} 
                          onClick={() => { 
                            onSetOptionsUnderlying?.(r.symbol); 
                            onSetOptionsUnderlyingSearch?.(r.symbol); 
                            onSetOptionsUnderlyingDropdownOpen?.(false); 
                          }}
                          className="px-3 py-1.5 text-xs cursor-pointer hover:bg-slate-50 flex justify-between"
                        >
                          <span className="font-medium">{r.symbol}</span>
                          <span className="text-slate-400 truncate ml-2">{r.name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* Type Toggle */}
                <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded">
                  <span className="text-[10px] text-slate-400 w-12">Type</span>
                  <div className="flex-1 flex gap-1">
                    <button 
                      type="button" 
                      onClick={() => onSetOptionsType?.('C')}
                      className={`flex-1 py-1 text-xs rounded transition-colors ${optionsType === 'C' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-200'}`}
                    >
                      Call
                    </button>
                    <button 
                      type="button" 
                      onClick={() => onSetOptionsType?.('P')}
                      className={`flex-1 py-1 text-xs rounded transition-colors ${optionsType === 'P' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-200'}`}
                    >
                      Put
                    </button>
                  </div>
                </div>
                
                {/* Expiry */}
                <div className="relative">
                  <div 
                    onClick={() => optionsUnderlying && onSetOptionsExpiryDropdownOpen?.(!optionsExpiryDropdownOpen)}
                    className={`flex items-center gap-2 px-3 py-2 bg-slate-50 rounded ${optionsUnderlying ? 'cursor-pointer hover:bg-slate-100' : 'opacity-50'}`}
                  >
                    <span className="text-[10px] text-slate-400 w-12">Expiry</span>
                    <span className={`flex-1 text-sm ${optionsExpiry ? 'text-slate-900' : 'text-slate-400'}`}>
                      {loadingExpirations ? '...' : optionsExpiry || 'Select'}
                    </span>
                    <svg className="w-3 h-3 text-slate-400" viewBox="0 0 12 12" fill="currentColor"><path d="M3 4.5L6 7.5L9 4.5"/></svg>
                  </div>
                  {optionsExpiryDropdownOpen && optionsExpirations.length > 0 && (
                    <div className="absolute z-50 w-full mt-1 bg-white rounded shadow-lg border border-slate-100 max-h-32 overflow-y-auto">
                      {optionsExpirations.slice(0, 12).map(exp => (
                        <div 
                          key={exp} 
                          onClick={() => { onSetOptionsExpiry?.(exp); onSetOptionsExpiryDropdownOpen?.(false); }}
                          className={`px-3 py-1.5 text-xs cursor-pointer ${optionsExpiry === exp ? 'bg-slate-900 text-white' : 'hover:bg-slate-50'}`}
                        >
                          {exp}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* Strike */}
                <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded">
                  <span className="text-[10px] text-slate-400 w-12">Strike</span>
                  <span className="text-slate-400">$</span>
                  <input 
                    type="number" 
                    value={optionsStrike} 
                    onChange={e => onSetOptionsStrike?.(e.target.value)}
                    placeholder="150" 
                    step="0.5" 
                    min="0"
                    className="flex-1 text-sm font-medium bg-transparent focus:outline-none"
                  />
                </div>
                
              </div>
            )}

            {/* Forex mode */}
            {formMode === 'forex' && (
              <ForexDropdown
                formCustomIdentifier={formCustomIdentifier}
                loadingForexPairs={loadingForexPairs}
                forexDropdownOpen={forexDropdownOpen}
                setForexDropdownOpen={(open) => onSetForexDropdownOpen?.(open)}
                forexSearch={forexSearch}
                setForexSearch={(search) => onSetForexSearch?.(search)}
                filteredForexPairs={displayForexPairs}
                onSelect={(pair) => onSetFormCustomIdentifier?.(pair)}
              />
            )}

            {/* Crypto mode */}
            {formMode === 'crypto' && (
              <CryptoDropdown
                formCustomIdentifier={formCustomIdentifier}
                loadingCryptoPairs={loadingCryptoPairs}
                cryptoDropdownOpen={cryptoDropdownOpen}
                setCryptoDropdownOpen={(open) => onSetCryptoDropdownOpen?.(open)}
                cryptoSearch={cryptoSearch}
                setCryptoSearch={(search) => onSetCryptoSearch?.(search)}
                filteredCryptoPairs={displayCryptoPairs}
                onSelect={(pair) => onSetFormCustomIdentifier?.(pair)}
              />
            )}
          </div>

          {/* Endpoint Browser */}
          {((formMode === 'symbol' && formSelectedSymbol) || 
            formMode === 'market' || 
            (formMode === 'options' && formCustomIdentifier) ||
            (formMode === 'forex' && formCustomIdentifier) ||
            (formMode === 'crypto' && formCustomIdentifier)) && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="p-4 pb-2">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <label className="text-xs font-medium text-slate-600">
                    {formSelectedEndpoint 
                      ? `${formSelectedEndpoint.endpoint} (${formSelectedFields.length} fields selected)`
                      : 'Select an Endpoint'}
                  </label>
                  {/* Source filter */}
                  {onSetFormSourceFilter && (
                    <SourceFilter
                      sourceFilter={formSourceFilter}
                      onSourceFilterChange={onSetFormSourceFilter}
                      endpointsBySource={formEndpointsBySource}
                    />
                  )}
                </div>
              </div>
              <EndpointBrowser
                loading={formEndpointsLoading}
                endpointsByCategory={formEndpointsByCategory}
                expandedCategories={formExpandedCategories}
                onToggleCategory={(category) => {
                  const next = new Set(formExpandedCategories);
                  if (next.has(category)) next.delete(category);
                  else next.add(category);
                  onSetFormExpandedCategories(next);
                }}
                selectedEndpoint={formSelectedEndpoint}
                onEndpointSelect={onEndpointSelect}
              />
            </div>
          )}
        </div>

        {/* Right panel - Fields + Parameters */}
        <div className="flex-1 flex flex-col bg-white overflow-hidden">
          {!formSelectedEndpoint ? (
            <div className="flex-1 flex items-center justify-center text-slate-400">
              <p className="text-sm">Select an endpoint from the left panel</p>
            </div>
          ) : (
            <div className="flex-1 flex flex-col overflow-auto p-6">
              {/* Endpoint header */}
              <div className="mb-4 pb-4 border-b border-slate-100">
                <h3 className="text-sm font-medium text-slate-900 font-mono">{formSelectedEndpoint.endpoint}</h3>
                <p className="text-xs text-slate-500 mt-1">{formSelectedEndpoint.category}</p>
              </div>

              {/* Field selection */}
              <FieldSelector
                fields={formSelectedEndpoint.fields}
                selectedFields={formSelectedFields}
                onFieldToggle={onFormFieldToggle}
                onSelectAll={onSelectAllFields}
              />

              {/* Parameters section */}
              {onSetFormParams && (
                <ParametersForm
                  params={formSelectedEndpoint.required_params}
                  formParams={formParams}
                  onSetFormParams={onSetFormParams}
                  uwEnums={uwEnums}
                  onFetchUwEnum={onFetchUwEnum}
                  ticker={formSelectedSymbol?.symbol}
                  isUwSource={formSelectedEndpoint.source === 'unusualwhales'}
                  uwExpirations={uwExpirations}
                  uwExpirationsLoading={uwExpirationsLoading}
                  onFetchUwExpirations={onFetchUwExpirations}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
