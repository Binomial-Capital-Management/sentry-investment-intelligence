import React, { useState, useEffect, useRef } from 'react';
import { Download, FileSpreadsheet, X, Send, ChevronDown, Info } from 'lucide-react';
import WorkingContentRenderer from '@/components/Chat/WorkingContentRenderer';
import api from '@/services/api';
import { dataToCSV, downloadCSV } from '@/utils/export';

const SCREENER_SESSION_KEY = 'screener_session_id';
const SCREENER_RESULTS_KEY = 'screener_last_results';
const SCREENER_MODE_KEY = 'screener_mode';
const POLL_INTERVAL_MS = 5000;

type ScreenerMode = 'stocks' | 'flow' | 'options' | 'analysts';

const SCREENER_MODES: { value: ScreenerMode; label: string; short: string }[] = [
  { value: 'stocks', label: 'Stocks', short: 'FMP' },
  { value: 'flow', label: 'Flow', short: 'UW' },
  { value: 'options', label: 'Options', short: 'UW' },
  { value: 'analysts', label: 'Analysts', short: 'UW' },
];

const MODE_PLACEHOLDERS: Record<ScreenerMode, string> = {
  stocks: 'Large cap tech stocks with high volume...',
  flow: 'High IV rank tech stocks with bullish flow...',
  options: 'High volume 0DTE calls in S&P 500...',
  analysts: 'Recent upgrades in technology sector...',
};

const MODE_FILTERS: Record<ScreenerMode, { filters: string[]; examples: string[] }> = {
  stocks: {
    filters: [
      'sector — Technology, Healthcare, Financial Services, Energy, Consumer Cyclical, etc.',
      'industry — specific industry name',
      'marketCap — mega $50B+, large $10B+, mid $2-10B, small $300M-2B, micro <$300M',
      'price — min/max stock price',
      'P/E ratio — value <15, growth >25',
      'beta — defensive <1, volatile >1.5',
      'volume — daily trading volume',
      'dividend — yield as decimal (0.03 = 3%)',
      'exchange — NASDAQ, NYSE',
    ],
    examples: [
      'Large cap tech stocks',
      'Value stocks with dividends over 3%',
      'Volatile small caps with beta over 1.5',
    ],
  },
  flow: {
    filters: [
      'sectors — Technology, Healthcare, Energy, Financial Services, etc.',
      'is_s_p_500 — S&P 500 stocks only',
      'has_dividends — dividend payers only',
      'iv_rank — IV percentile 0-100',
      'premium — total options premium',
      'net_premium — calls minus puts (positive = bullish)',
      'put_call_ratio — P/C ratio',
      'volume — options volume',
      'call_volume / put_volume — specific side volume',
      'oi — open interest',
      'implied_move — expected move $ or %',
      'underlying_price — stock price range',
      'marketcap — market cap range',
      'change — price change %',
      'issue_types — Common Stock, ETF, Index, ADR',
    ],
    examples: [
      'High IV rank tech stocks',
      'S&P 500 with bullish net premium',
      'High premium large caps',
    ],
  },
  options: {
    filters: [
      'ticker — specific stock(s), comma-separated',
      'type — call or put',
      'dte — days to expiration (0 = 0DTE)',
      'is_otm — out-of-the-money only',
      'vol_greater_oi — unusual activity (volume > open interest)',
      'volume — contract volume',
      'premium — total premium',
      'oi — open interest',
      'iv — implied volatility',
      'delta — option delta',
      'sectors — Technology, Healthcare, etc.',
      'issue_types — Common Stock, ETF, Index, ADR',
      'expiry_dates — specific expiration dates',
    ],
    examples: [
      'High volume 0DTE calls',
      'Unusual OTM puts',
      'Tech sector high premium options',
    ],
  },
  analysts: {
    filters: [
      'ticker — specific stock',
      'action — initiated, reiterated, downgraded, upgraded, maintained',
      'recommendation — buy, hold, sell',
    ],
    examples: [
      'Recent upgrades',
      'AAPL analyst ratings',
      'Buy recommendations',
    ],
  },
};

export const AIScreenerInterface: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<ScreenerMode>(() => {
    return (localStorage.getItem(SCREENER_MODE_KEY) as ScreenerMode) || 'stocks';
  });
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem(SCREENER_SESSION_KEY);
  });
  const [error, setError] = useState<string | null>(null);
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const [showFilterGuide, setShowFilterGuide] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const filterGuideRef = useRef<HTMLDivElement>(null);

  // Save mode to localStorage
  useEffect(() => {
    localStorage.setItem(SCREENER_MODE_KEY, mode);
  }, [mode]);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(event.target as Node)) {
        setModeMenuOpen(false);
      }
      if (filterGuideRef.current && !filterGuideRef.current.contains(event.target as Node)) {
        setShowFilterGuide(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Restore results from localStorage on mount
  useEffect(() => {
    const savedResults = localStorage.getItem(SCREENER_RESULTS_KEY);
    if (savedResults && !results) {
      try {
        setResults(savedResults);
      } catch (e) {
        console.warn('Failed to restore screener results:', e);
      }
    }
  }, []);

  // Poll for session updates when loading
  useEffect(() => {
    if (!isLoading || !sessionId) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }

    const pollSession = async () => {
      try {
        const response = await api.get(`/v6/screener/session/${sessionId}`);
        const { status, response: aiResponse } = response.data;

        if (status === 'completed' && aiResponse) {
          setResults(aiResponse);
          setIsLoading(false);
          localStorage.setItem(SCREENER_RESULTS_KEY, aiResponse);
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        } else if (status === 'failed') {
          setError('Screening request failed. Please try again.');
          setIsLoading(false);
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      } catch (e) {
        console.warn('Polling error:', e);
      }
    };

    pollSession();
    pollIntervalRef.current = setInterval(pollSession, POLL_INTERVAL_MS);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [isLoading, sessionId]);

  const handleSend = async () => {
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setResults(null);
    setError(null);
    setSessionId(null);
    localStorage.removeItem(SCREENER_RESULTS_KEY);
    localStorage.removeItem(SCREENER_SESSION_KEY);

    try {
      const response = await api.post('/v6/screener/chat', {
        message: query,
        session_id: null,
        mode: mode,
      });

      const { response: aiResponse, session_id: newSessionId, status } = response.data;

      if (newSessionId && newSessionId !== sessionId) {
        setSessionId(newSessionId);
        localStorage.setItem(SCREENER_SESSION_KEY, newSessionId);
      }

      if (status === 'completed' && aiResponse) {
        setResults(aiResponse);
        localStorage.setItem(SCREENER_RESULTS_KEY, aiResponse);
        setIsLoading(false);
      }
    } catch (error: any) {
      console.error('Screener error:', error);
      setError(error.response?.data?.detail || error.message);
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setResults(null);
    setError(null);
    setQuery('');
    localStorage.removeItem(SCREENER_RESULTS_KEY);
  };

  const parseMarkdownTable = (markdown: string): any[] => {
    const lines = markdown.split('\n');

    // Find the first contiguous table block
    let tableStart = -1;
    let tableEnd = -1;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        if (tableStart === -1) tableStart = i;
        tableEnd = i;
      } else if (tableStart !== -1 && tableEnd !== -1) {
        // End of first table block
        break;
      }
    }

    if (tableStart === -1 || tableEnd - tableStart < 2) return [];

    const tableLines = lines.slice(tableStart, tableEnd + 1);

    // Parse header (first line)
    const headerLine = tableLines[0];
    const headers = headerLine.split('|').slice(1, -1).map((h) => h.trim());

    // Skip separator line (contains dashes) and get data rows
    const dataRows = tableLines.slice(2).filter((row) => {
      const trimmed = row.trim();
      // Skip separator lines and empty rows
      return trimmed.startsWith('|') && !trimmed.match(/^\|[\s\-:]+\|$/);
    });

    return dataRows.map((row) => {
      const values = row.split('|').slice(1, -1).map((v) => v.trim());
      const obj: any = {};
      headers.forEach((header, i) => {
        obj[header] = values[i] || '';
      });
      return obj;
    });
  };

  const handleExportCSV = () => {
    if (!results) return;
    const data = parseMarkdownTable(results);
    if (data.length === 0) {
      alert('No table data found in results');
      return;
    }
    const csvContent = dataToCSV(data);
    downloadCSV('screener_results.csv', csvContent);
  };

  const handleExportExcel = async () => {
    if (!results) return;
    const data = parseMarkdownTable(results);
    if (data.length === 0) {
      alert('No table data found in results');
      return;
    }
    try {
      const XLSX = await import('xlsx');
      const worksheet = XLSX.utils.json_to_sheet(data);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Screener Results');
      XLSX.writeFile(workbook, 'screener_results.xlsx');
    } catch (error) {
      console.error('Excel export error:', error);
      alert('Failed to export to Excel. Please try CSV export instead.');
    }
  };

  const hasContent = results || error || isLoading;

  return (
    <div className="flex flex-col w-full max-w-full" style={{ height: '700px' }}>
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-semibold text-gray-900">Screener</h2>
          {/* Info Button */}
          <div className="relative" ref={filterGuideRef}>
            <button
              onClick={() => setShowFilterGuide(!showFilterGuide)}
              className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
              title="Available filters"
            >
              <Info size={16} />
            </button>

            {/* Filter Guide Popover */}
            {showFilterGuide && (
              <div className="absolute top-full left-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl z-20 overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-900">
                      {SCREENER_MODES.find(m => m.value === mode)?.label} Filters
                    </span>
                    <span className="text-[10px] text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded">
                      {SCREENER_MODES.find(m => m.value === mode)?.short}
                    </span>
                  </div>
                </div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  <div className="space-y-3">
                    <div>
                      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Available Filters</p>
                      <ul className="space-y-1">
                        {MODE_FILTERS[mode].filters.map((filter, i) => (
                          <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                            <span className="text-gray-400 mt-0.5">•</span>
                            <span>{filter}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="pt-2 border-t border-gray-100">
                      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Example Queries</p>
                      <ul className="space-y-1">
                        {MODE_FILTERS[mode].examples.map((example, i) => (
                          <li key={i} className="text-xs text-gray-700 font-mono bg-gray-50 px-2 py-1 rounded">
                            "{example}"
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {hasContent && (
            <button
              onClick={handleClear}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <X size={14} />
              Clear
            </button>
          )}
          <button
            onClick={handleExportExcel}
            disabled={!results || isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <FileSpreadsheet size={14} />
            Excel
          </button>
          <button
            onClick={handleExportCSV}
            disabled={!results || isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download size={14} />
            CSV
          </button>
        </div>
      </div>

      {/* Results Area */}
      <div
        className="border border-gray-200 rounded-xl overflow-y-auto mb-4 flex flex-col flex-1"
        style={{
          background: !results && !isLoading && !error
            ? '#fafbfc'
            : '#ffffff',
          backgroundImage: !results && !isLoading && !error
            ? 'radial-gradient(circle, #d1d5db 1px, transparent 1px)'
            : 'none',
          backgroundSize: '16px 16px',
        }}
      >
        {isLoading ? (
          <div className="flex items-center justify-center flex-1">
            <div className="text-center">
              <div className="relative inline-flex items-center justify-center w-16 h-16 mb-4">
                <div className="absolute w-16 h-16 border-4 border-gray-200 rounded-full"></div>
                <div className="absolute w-16 h-16 border-4 border-blue-500 rounded-full border-t-transparent animate-spin"></div>
                <div className="absolute w-10 h-10 border-4 border-blue-300 rounded-full border-b-transparent animate-spin" style={{ animationDirection: 'reverse', animationDuration: '0.8s' }}></div>
              </div>
              <p className="text-base font-medium text-gray-700">Screening...</p>
              <p className="text-xs text-gray-500 mt-1">Analyzing market data</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center flex-1">
            <div className="text-center max-w-md px-4">
              <p className="text-sm font-medium text-red-600 mb-1">Error</p>
              <p className="text-xs text-gray-500">{error}</p>
            </div>
          </div>
        ) : results ? (
          <div className="p-4">
            <WorkingContentRenderer content={results} />
          </div>
        ) : (
          <div className="flex items-center justify-center flex-1">
            <p className="text-gray-400 text-sm">Enter a query below to screen</p>
          </div>
        )}
      </div>

      {/* Input Area with Integrated Mode Selector */}
      <div className="relative flex items-center bg-white border border-gray-200 rounded-xl focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
        {/* Mode Dropdown */}
        <div className="relative" ref={modeMenuRef}>
          <button
            onClick={() => setModeMenuOpen(!modeMenuOpen)}
            disabled={isLoading}
            className="flex items-center gap-1 pl-3 pr-2 py-3 text-sm font-medium text-gray-700 hover:text-gray-900 border-r border-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {SCREENER_MODES.find((m) => m.value === mode)?.label}
            <span className="text-[10px] text-gray-400 ml-0.5">
              {SCREENER_MODES.find((m) => m.value === mode)?.short}
            </span>
            <ChevronDown size={14} className={`text-gray-400 transition-transform ${modeMenuOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Dropdown Menu */}
          {modeMenuOpen && (
            <div className="absolute bottom-full left-0 mb-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-10">
              {SCREENER_MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => {
                    setMode(m.value);
                    setModeMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2 text-left text-sm flex items-center justify-between hover:bg-gray-50 transition-colors ${
                    mode === m.value ? 'text-blue-600 bg-blue-50' : 'text-gray-700'
                  }`}
                >
                  <span>{m.label}</span>
                  <span className="text-[10px] text-gray-400">{m.short}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Input Field */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={MODE_PLACEHOLDERS[mode]}
          className="flex-1 px-3 py-3 text-sm bg-transparent focus:outline-none placeholder:text-gray-400"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isLoading}
        />

        {/* Send Button */}
        <button
          onClick={handleSend}
          disabled={!query.trim() || isLoading}
          className="mr-2 p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
          title="Send"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};
