/**
 * CryptoDropdown - Dropdown for selecting crypto pairs
 * Extracted from SingleObjectForm lines 546-587
 */

interface CryptoDropdownProps {
  formCustomIdentifier: string;
  loadingCryptoPairs: boolean;
  cryptoDropdownOpen: boolean;
  setCryptoDropdownOpen: (open: boolean) => void;
  cryptoSearch: string;
  setCryptoSearch: (search: string) => void;
  filteredCryptoPairs: string[];
  onSelect: (pair: string) => void;
}

export default function CryptoDropdown({
  formCustomIdentifier,
  loadingCryptoPairs,
  cryptoDropdownOpen,
  setCryptoDropdownOpen,
  cryptoSearch,
  setCryptoSearch,
  filteredCryptoPairs,
  onSelect,
}: CryptoDropdownProps) {
  return (
    <div className="relative">
      <div 
        onClick={() => setCryptoDropdownOpen(!cryptoDropdownOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded cursor-pointer hover:bg-slate-100 transition-colors"
      >
        <span className="text-[10px] text-slate-400 w-8">Crypto</span>
        <span className={`flex-1 text-sm ${formCustomIdentifier ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
          {loadingCryptoPairs ? 'Loading...' : formCustomIdentifier ? `${formCustomIdentifier.replace('USD','')}/USD` : 'Select'}
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
            {filteredCryptoPairs.slice(0, 20).map(pair => (
              <div
                key={pair}
                onClick={() => { 
                  onSelect(pair); 
                  setCryptoDropdownOpen(false); 
                  setCryptoSearch(''); 
                }}
                className={`px-3 py-1.5 text-xs cursor-pointer ${formCustomIdentifier === pair ? 'bg-slate-900 text-white' : 'hover:bg-slate-50'}`}
              >
                {pair.replace('USD','')}/USD
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
