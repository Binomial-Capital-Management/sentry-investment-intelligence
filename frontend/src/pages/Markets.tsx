import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

export default function Markets() {
  // Live indices data from WebSocket (mapped from ETFs)
  const [indices, setIndices] = useState([
    { symbol: 'S&P 500', name: 'S&P 500', value: 0, change: 0, changePercent: 0, status: 'up' },
    { symbol: 'DOW JONES', name: 'DOW JONES', value: 0, change: 0, changePercent: 0, status: 'up' },
    { symbol: 'NASDAQ', name: 'NASDAQ', value: 0, change: 0, changePercent: 0, status: 'up' },
    { symbol: 'RUSSELL 2000', name: 'RUSSELL 2000', value: 0, change: 0, changePercent: 0, status: 'up' },
    { symbol: 'VOLATILITY', name: 'VOLATILITY', value: 0, change: 0, changePercent: 0, status: 'up' },
  ]);

  const [watchlist, setWatchlist] = useState<Map<string, any>>(new Map());
  const [wsStatus, setWsStatus] = useState<'disconnected' | 'connected'>('disconnected');
  const [wsRef, setWsRef] = useState<WebSocket | null>(null);
  const [filters, setFilters] = useState({
    minPrice: 10,
    maxPrice: 500,
    minPE: 0,
    maxPE: 40,
  });
  const [sortBy, setSortBy] = useState<'symbol' | 'price' | 'changePercent' | 'marketCap'>('marketCap');

  // WebSocket connection function
  const connectWebSocket = (filterParams: typeof filters) => {
    // Close existing connection if any
    if (wsRef) {
      wsRef.close();
      setWsRef(null); // Clear the ref to ensure clean reconnection
    }

    // Clear existing watchlist when new filters are applied
    setWatchlist(new Map());

    // Build query params from filters
    const params = new URLSearchParams({
      min_price: filterParams.minPrice.toString(),
      max_price: filterParams.maxPrice.toString(),
      min_pe: filterParams.minPE.toString(),
      max_pe: filterParams.maxPE.toString(),
    });

    // Derive WebSocket URL from API base URL
    const apiBase = (import.meta as any).env?.VITE_API_BASE ||
      (import.meta as any).env?.VITE_API_BASE_URL ||
      (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');
    const wsBase = apiBase.replace('http://', 'ws://').replace('https://', 'wss://');
    const wsUrl = `${wsBase}/ws/screener?${params}`;

    console.log('Connecting to WebSocket with filters:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setWsStatus('connected');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setWsStatus('disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      console.log('WebSocket message:', event.data);
      const msg = JSON.parse(event.data);
      if (msg.type === 'screener_match' && msg.data) {
        const symbol = msg.data.symbol;

        // Check if this is a market index and update indices
        const indexMap: { [key: string]: { index: string, name: string } } = {
          '^GSPC': { index: 'S&P 500', name: 'S&P 500' },
          '^DJI': { index: 'DOW JONES', name: 'DOW JONES' },
          '^IXIC': { index: 'NASDAQ', name: 'NASDAQ' },
          '^RUT': { index: 'RUSSELL 2000', name: 'RUSSELL 2000' },
          '^VIX': { index: 'VOLATILITY', name: 'VOLATILITY' },
        };

        if (indexMap[symbol]) {
          const { index } = indexMap[symbol];
          const price = msg.data.price || 0;
          const change = msg.data.change || 0;
          const changePercent = msg.data.dayChange || 0;

          setIndices(prev => prev.map(idx =>
            idx.symbol === index
              ? {
                  ...idx,
                  value: price,
                  change: change,
                  changePercent: changePercent,
                  status: change >= 0 ? 'up' : 'down',
                }
              : idx,
          ));
        }

        // Also update watchlist for regular stocks
        setWatchlist(prev => {
          const updated = new Map(prev);
          updated.set(msg.data.symbol, {
            symbol: msg.data.symbol,
            price: msg.data.price || 0,
            change: msg.data.change || 0,
            changePercent: msg.data.dayChange || 0,
            volume: msg.data.volume ? (msg.data.volume / 1000000).toFixed(1) + 'M' : '0M',
            high: msg.data.dayHigh || msg.data.price || 0,
            low: msg.data.dayLow || msg.data.price || 0,
            pe: msg.data.pe || 0,
            marketCap: msg.data.marketCap || 0,
          });
          return updated;
        });
      }
    };

    setWsRef(ws);
    return ws;
  };

  // Initial connection on mount
  useEffect(() => {
    const ws = connectWebSocket(filters);
    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, []); // Only run once on mount

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-base)' }}>
      {/* Command Bar */}
      <div style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border-light)', boxShadow: 'var(--shadow-sm)' }}>
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-4">
            <span style={{ color: 'var(--text-primary)', fontSize: 'var(--fs-base)', fontWeight: 'var(--fw-medium)' }}>
              Market Data
            </span>
            <div style={{ width: '1px', height: '16px', background: 'var(--border)' }} />
            <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-base)' }}>
              Live Feed
            </span>
            <div style={{ width: '8px', height: '8px', background: wsStatus === 'connected' ? '#10b981' : '#ef4444', borderRadius: '50%', animation: wsStatus === 'connected' ? 'pulse 2s infinite' : 'none' }} />
          </div>
          <div className="flex items-center gap-2">
            <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--fs-xs)' }}>
              Last Update: {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>

      {/* Filter Controls */}
      <div style={{ background: 'var(--bg-card)', padding: '12px', margin: '8px 8px 0', borderRadius: '8px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', alignItems: 'end' }}>
          {/* Price Range */}
          <div>
            <label style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)', display: 'block', marginBottom: '4px' }}>
              Price Range ($)
            </label>
            <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
              <input
                type="number"
                value={filters.minPrice}
                onChange={(e) => setFilters({ ...filters, minPrice: +e.target.value })}
                style={{
                  background: '#FFFFFF',
                  color: '#323130',
                  border: '1px solid #C8C6C4',
                  borderRadius: '4px',
                  padding: '6px 12px',
                  width: '80px',
                  fontSize: '14px',
                  height: '32px',
                }}
              />
              <span style={{ color: 'var(--text-secondary)' }}>-</span>
              <input
                type="number"
                value={filters.maxPrice}
                onChange={(e) => setFilters({ ...filters, maxPrice: +e.target.value })}
                style={{
                  background: '#FFFFFF',
                  color: '#323130',
                  border: '1px solid #C8C6C4',
                  borderRadius: '4px',
                  padding: '6px 12px',
                  width: '80px',
                  fontSize: '14px',
                  height: '32px',
                }}
              />
            </div>
          </div>

          {/* PE Range */}
          <div>
            <label style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)', display: 'block', marginBottom: '4px' }}>
              PE Ratio
            </label>
            <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
              <input
                type="number"
                value={filters.minPE}
                onChange={(e) => setFilters({ ...filters, minPE: +e.target.value })}
                style={{
                  background: '#FFFFFF',
                  color: '#323130',
                  border: '1px solid #C8C6C4',
                  borderRadius: '4px',
                  padding: '6px 12px',
                  width: '80px',
                  fontSize: '14px',
                  height: '32px',
                }}
              />
              <span style={{ color: 'var(--text-secondary)' }}>-</span>
              <input
                type="number"
                value={filters.maxPE}
                onChange={(e) => setFilters({ ...filters, maxPE: +e.target.value })}
                style={{
                  background: '#FFFFFF',
                  color: '#323130',
                  border: '1px solid #C8C6C4',
                  borderRadius: '4px',
                  padding: '6px 12px',
                  width: '80px',
                  fontSize: '14px',
                  height: '32px',
                }}
              />
            </div>
          </div>

          {/* Sort By */}
          <div>
            <label style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)', display: 'block', marginBottom: '4px' }}>
              Sort By
            </label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              style={{
                background: '#FFFFFF',
                color: '#323130',
                border: '1px solid #C8C6C4',
                borderRadius: '4px',
                padding: '6px 12px',
                width: '100%',
                fontSize: '14px',
                height: '32px',
                cursor: 'pointer',
              }}
            >
              <option value="marketCap">Market Cap</option>
              <option value="price">Price</option>
              <option value="changePercent">Change %</option>
              <option value="symbol">Symbol</option>
            </select>
          </div>

          {/* Apply/Reset Buttons */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => connectWebSocket(filters)}
              style={{
                background: '#0078D4',
                color: '#FFFFFF',
                padding: '8px 20px',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500',
                height: '32px',
              }}
            >
              Apply
            </button>
            <button
              onClick={() => {
                const defaults = { minPrice: 10, maxPrice: 500, minPE: 0, maxPE: 40 };
                setFilters(defaults);
                connectWebSocket(defaults);
              }}
              style={{
                background: '#FFFFFF',
                color: '#605E5C',
                border: '1px solid #C8C6C4',
                padding: '8px 20px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px',
                height: '32px',
              }}
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 p-2 overflow-auto">
        {/* Market Indices */}
        <div className="mb-2" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)', borderRadius: '8px', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ background: 'var(--bg-surface)', padding: '10px 16px', borderBottom: '1px solid var(--border-light)' }}>
            <span style={{ color: 'var(--text-primary)', fontSize: 'var(--fs-sm)', fontWeight: 'var(--fw-medium)' }}>
              Market Indices
            </span>
          </div>
          <div className="grid grid-cols-5 gap-0">
            {indices.map((index) => (
              <div key={index.symbol} className="border-r border-gray-200 last:border-r-0 p-3">
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  {index.symbol}
                </div>
                <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '2px' }}>
                  {index.value.toLocaleString()}
                </div>
                <div className="flex items-center gap-1">
                  {index.status === 'up' ? (
                    <TrendingUp size={12} style={{ color: '#10b981' }} />
                  ) : (
                    <TrendingDown size={12} style={{ color: '#ef4444' }} />
                  )}
                  <span style={{
                    fontSize: 'var(--fs-base)',
                    color: index.status === 'up' ? '#10b981' : '#ef4444',
                  }}>
                    {index.change > 0 ? '+' : ''}{index.change.toFixed(2)} ({index.changePercent > 0 ? '+' : ''}{index.changePercent.toFixed(2)}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Watchlist */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)', borderRadius: '8px', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ background: 'var(--bg-surface)', padding: '10px 16px', borderBottom: '1px solid var(--border-light)' }}>
            <span style={{ color: 'var(--text-primary)', fontSize: 'var(--fs-sm)', fontWeight: 'var(--fw-medium)' }}>
              Watchlist
            </span>
          </div>
          <table className="w-full" style={{ fontSize: 'var(--fs-base)' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-light)' }}>
                <th className="text-left px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>SYMBOL</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>PRICE</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>CHANGE</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>%</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>VOLUME</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>MKT CAP</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>HIGH</th>
                <th className="text-right px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>LOW</th>
                <th className="text-center px-3 py-2" style={{ fontWeight: 'var(--fw-medium)', color: 'var(--text-secondary)', fontSize: 'var(--fs-xs)' }}>CHART</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(watchlist.values()).sort((a, b) => {
                switch (sortBy) {
                  case 'symbol': return a.symbol.localeCompare(b.symbol);
                  case 'price': return b.price - a.price;
                  case 'changePercent': return b.changePercent - a.changePercent;
                  default: return b.marketCap - a.marketCap;
                }
              }).map((stock) => (
                <tr key={stock.symbol} className="hover:bg-gray-50" style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td className="px-3 py-2" style={{ fontWeight: 'var(--fw-medium)' }}>{stock.symbol}</td>
                  <td className="px-3 py-2 text-right">{stock.price.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right" style={{
                    color: stock.change > 0 ? '#10b981' : '#ef4444',
                  }}>
                    {stock.change > 0 ? '+' : ''}{stock.change.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-right" style={{
                    color: stock.changePercent > 0 ? '#10b981' : '#ef4444',
                  }}>
                    {stock.changePercent > 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-right">{stock.volume}</td>
                  <td className="px-3 py-2 text-right" style={{ fontSize: 'var(--fs-base)' }}>
                    {stock.marketCap > 1e12 ? `${(stock.marketCap / 1e12).toFixed(1)}T` :
                     stock.marketCap > 1e9 ? `${(stock.marketCap / 1e9).toFixed(1)}B` :
                     stock.marketCap > 1e6 ? `${(stock.marketCap / 1e6).toFixed(0)}M` :
                     stock.marketCap.toFixed(0)}
                  </td>
                  <td className="px-3 py-2 text-right">{stock.high.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{stock.low.toFixed(2)}</td>
                  <td className="px-3 py-2 text-center">
                    <Activity size={14} style={{ color: 'var(--text-secondary)', margin: '0 auto' }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
