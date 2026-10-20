import { OBJECT_TYPES } from '@/features/canvas/types';
import type { ObjectTypeResult } from '@/features/canvas/types';

interface SelectedObject {
  symbol: string;
  name?: string;
  objectType: string;
  exchange?: string;
}

interface DataBrowserProps {
  browsingType: string;
  setBrowsingType: (type: string | null) => void;
  browserSearchQuery: string;
  setBrowserSearchQuery: (query: string) => void;
  browserResults: ObjectTypeResult[];
  setBrowserResults: (results: ObjectTypeResult[]) => void;
  searchBrowserSymbols: (query: string, objectType: string) => void;
  workspaceObjects: SelectedObject[];
  handleAddWorkspaceObject: (result: ObjectTypeResult, forceType?: string | null) => void;
}

export default function DataBrowser({
  browsingType,
  setBrowsingType,
  browserSearchQuery,
  setBrowserSearchQuery,
  browserResults,
  setBrowserResults,
  searchBrowserSymbols,
  workspaceObjects,
  handleAddWorkspaceObject,
}: DataBrowserProps) {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white">
      <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3">
        <button onClick={() => { setBrowsingType(null); setBrowserSearchQuery(''); setBrowserResults([]); }} className="p-1.5 hover:bg-slate-100 rounded">
          <svg className="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
        </button>
        <h2 className="text-lg font-semibold text-slate-900">
          Browse {OBJECT_TYPES.find(t => t.id === browsingType)?.name}
        </h2>
      </div>
      <div className="px-6 py-4 border-b border-slate-200">
        <input
          type="text"
          value={browserSearchQuery}
          onChange={(e) => { setBrowserSearchQuery(e.target.value); searchBrowserSymbols(e.target.value, browsingType); }}
          placeholder={`Search ${browsingType}...`}
          className="w-full max-w-2xl px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
        />
      </div>
      <div className="flex-1 overflow-auto p-6">
        {browserResults.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            {browserSearchQuery ? 'No results' : 'Start typing to search'}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {browserResults.map((result) => {
              const isAdded = workspaceObjects.some(o => o.symbol === result.symbol);
              return (
                <button
                  key={result.symbol}
                  onClick={() => !isAdded && handleAddWorkspaceObject(result, browsingType)}
                  disabled={isAdded}
                  className={`p-4 rounded-lg border-2 text-left ${isAdded ? 'border-slate-200 bg-slate-50 cursor-not-allowed' : 'border-slate-200 hover:border-slate-900'}`}
                >
                  <span className={`font-mono text-sm font-semibold ${isAdded ? 'text-slate-400' : 'text-slate-900'}`}>{result.symbol}</span>
                  {result.name && <div className="text-xs text-slate-500 truncate mt-1">{result.name}</div>}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
