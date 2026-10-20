/**
 * ForexDropdown - Dropdown for selecting forex pairs
 * Extracted from SingleObjectForm lines 504-544
 */

interface ForexDropdownProps {
  formCustomIdentifier: string;
  loadingForexPairs: boolean;
  forexDropdownOpen: boolean;
  setForexDropdownOpen: (open: boolean) => void;
  forexSearch: string;
  setForexSearch: (search: string) => void;
  filteredForexPairs: string[];
  onSelect: (pair: string) => void;
}

export default function ForexDropdown({
  formCustomIdentifier,
  loadingForexPairs,
  forexDropdownOpen,
  setForexDropdownOpen,
  forexSearch,
  setForexSearch,
  filteredForexPairs,
  onSelect,
}: ForexDropdownProps) {
  return (
    <div className="relative">
      <div 
        onClick={() => setForexDropdownOpen(!forexDropdownOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded cursor-pointer hover:bg-slate-100 transition-colors"
      >
        <span className="text-[10px] text-slate-400 w-8">FX</span>
        <span className={`flex-1 text-sm ${formCustomIdentifier ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
          {loadingForexPairs ? 'Loading...' : formCustomIdentifier ? `${formCustomIdentifier.slice(0,3)}/${formCustomIdentifier.slice(3)}` : 'Select'}
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
            {filteredForexPairs.slice(0, 20).map(pair => (
              <div
                key={pair}
                onClick={() => { 
                  onSelect(pair); 
                  setForexDropdownOpen(false); 
                  setForexSearch(''); 
                }}
                className={`px-3 py-1.5 text-xs cursor-pointer ${formCustomIdentifier === pair ? 'bg-slate-900 text-white' : 'hover:bg-slate-50'}`}
              >
                {pair.slice(0,3)}/{pair.slice(3)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
