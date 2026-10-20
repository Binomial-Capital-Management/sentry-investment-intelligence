/**
 * SymbolSearchInput - Symbol search with dropdown results
 * 
 * Supports two modes:
 * - single: Shows selected symbol in input, displays name/type below
 * - additive: Always empty for adding, no selected state display
 */

interface SearchResult {
  symbol: string;
  name: string;
  exchange?: string;
}

interface SelectedSymbol {
  symbol: string;
  name: string;
  objectType: string;
}

interface SymbolSearchInputProps {
  // Core props
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  onSearch: (query: string) => void;
  results: SearchResult[];
  onSelect: (result: SearchResult) => void;
  
  // Mode: single select vs additive (multi)
  mode?: 'single' | 'additive';
  
  // For single mode - selected symbol state
  selectedSymbol?: SelectedSymbol | null;
  onClearSelected?: () => void;
  
  // Dropdown control
  showDropdown: boolean;
  onShowDropdownChange: (show: boolean) => void;
  
  // Customization
  placeholder?: string;
  maxResults?: number;
  label?: string;
}

export default function SymbolSearchInput({
  searchQuery,
  onSearchQueryChange,
  onSearch,
  results,
  onSelect,
  mode = 'single',
  selectedSymbol = null,
  onClearSelected,
  showDropdown,
  onShowDropdownChange,
  placeholder = 'Search ticker...',
  maxResults = 5,
  label = 'Symbol',
}: SymbolSearchInputProps) {
  const handleChange = (value: string) => {
    if (mode === 'single' && selectedSymbol) {
      onClearSelected?.();
    }
    onSearchQueryChange(value);
    onSearch(value);
    // For additive mode, show dropdown when typing
    if (mode === 'additive') {
      onShowDropdownChange(value.length >= 1);
    }
  };

  const displayValue = mode === 'single' && selectedSymbol 
    ? selectedSymbol.symbol 
    : searchQuery;

  const showResults = mode === 'single' 
    ? results.length > 0 && !selectedSymbol
    : showDropdown && results.length > 0;

  return (
    <>
      {label && (
        <label className="block text-xs font-medium text-slate-600 mb-1.5">{label}</label>
      )}
      <div className="relative">
        <input
          type="text"
          value={displayValue}
          onChange={e => handleChange(e.target.value)}
          onFocus={() => {
            if (mode === 'additive' && searchQuery.length >= 1) {
              onShowDropdownChange(true);
            }
          }}
          placeholder={placeholder}
          className="w-full px-3 py-2 text-sm border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-slate-400"
        />
        
        {/* Clear button for single mode */}
        {mode === 'single' && selectedSymbol && onClearSelected && (
          <button
            onClick={onClearSelected}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
        
        {/* Results dropdown */}
        {showResults && (
          <div className={`absolute z-10 w-full mt-1 border border-slate-200 rounded bg-white shadow-lg overflow-y-auto ${
            mode === 'single' ? 'shadow-sm max-h-32' : 'max-h-40'
          }`}>
            {results.slice(0, maxResults).map((r, i) => (
              <button
                key={i}
                onClick={() => onSelect(r)}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${
                  mode === 'additive' ? 'border-b border-slate-100 last:border-b-0' : ''
                }`}
              >
                <span className="font-mono font-medium">{r.symbol}</span>
                <span className={`text-slate-400 ml-2 ${mode === 'additive' ? 'text-xs' : ''}`}>
                  {r.name?.slice(0, mode === 'additive' ? 30 : 25)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
      
      {/* Selected symbol info for single mode */}
      {mode === 'single' && selectedSymbol && (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-slate-500">{selectedSymbol.name}</span>
          <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 rounded text-slate-500">
            {selectedSymbol.objectType}
          </span>
        </div>
      )}
    </>
  );
}
