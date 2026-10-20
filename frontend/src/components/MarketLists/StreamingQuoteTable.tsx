/**
 * StreamingQuoteTable Component
 *
 * Real-time quote streaming table via WebSocket.
 * Displays live market data for tracker lists and screeners.
 */

import React, { useState, useEffect, useRef } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface QuoteData {
  list_id: string;
  list_type: 'tracker' | 'screener';
  symbol: string;
  timestamp: string;
  price: number;
  pe: number;
  volume: number;
  marketCap: number;
  dayChange: number;
  change: number;
  dayLow: number;
  dayHigh: number;
  yearLow: number;
  yearHigh: number;
  previousClose: number;
  open: number;
  name: string;
  exchange: string;
}

interface StreamingQuoteTableProps {
  listId: string;
  listType: 'tracker' | 'screener';
}

export const StreamingQuoteTable: React.FC<StreamingQuoteTableProps> = ({ listId, listType }) => {
  const [quotes, setQuotes] = useState<Map<string, QuoteData>>(new Map());
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Only connect if we have a valid list ID
    if (!listId) return;

    // WebSocket connection - derive from API base URL
    const apiBase = (import.meta as any).env?.VITE_API_BASE ||
      (import.meta as any).env?.VITE_API_BASE_URL ||
      (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 
   window.location.hostname.includes('preprod') ? 'https://api-preprod.binomialsentry.ai' :
   'https://api.binomialsentry.ai');
    const wsUrl = apiBase.replace('http://', 'ws://').replace('https://', 'wss://');
    const ws = new WebSocket(`${wsUrl}/ws/screener`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const data: QuoteData = JSON.parse(event.data);

        // Only update if message is for our list
        if (data.list_id === listId && data.list_type === listType) {
          setQuotes((prev) => {
            const updated = new Map(prev);
            updated.set(data.symbol, data);
            return updated;
          });
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('disconnected');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');
    };

    // Cleanup on unmount
    return () => {
      ws.close();
    };
  }, [listId, listType]);

  // Format number helpers
  const formatPrice = (value: number) => {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatMarketCap = (value: number) => {
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return formatPrice(value);
  };

  const formatVolume = (value: number) => {
    if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
    return value.toLocaleString();
  };

  const formatPercent = (value: number) => {
    const formatted = value.toFixed(2);
    return value >= 0 ? `+${formatted}%` : `${formatted}%`;
  };

  const quotesArray = Array.from(quotes.values()).sort((a, b) => a.symbol.localeCompare(b.symbol));

  return (
    <div className="flex flex-col h-full bg-[#1C1C1E] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#2C2C2E]">
        <h3 className="text-lg font-semibold text-white">
          Live Quotes ({quotesArray.length} stocks)
        </h3>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connectionStatus === 'connected'
                ? 'bg-green-500'
                : connectionStatus === 'connecting'
                ? 'bg-yellow-500 animate-pulse'
                : 'bg-red-500'
            }`}
          />
          <span className="text-sm text-gray-400 capitalize">{connectionStatus}</span>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {quotesArray.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              {connectionStatus === 'connected' ? (
                <>
                  <p>Waiting for market data...</p>
                  <p className="text-sm mt-2">Quotes will appear here in real-time</p>
                </>
              ) : connectionStatus === 'connecting' ? (
                <>
                  <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                  <p>Connecting to market data stream...</p>
                </>
              ) : (
                <>
                  <p>Connection lost</p>
                  <p className="text-sm mt-2">Refresh the page to reconnect</p>
                </>
              )}
            </div>
          </div>
        ) : (
          <table className="w-full">
            <thead className="sticky top-0 bg-[#2C2C2E] z-10">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Symbol
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Price
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Change
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  %
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Volume
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Market Cap
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  P/E
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2C2C2E]">
              {quotesArray.map((quote) => (
                <tr
                  key={quote.symbol}
                  className="hover:bg-[#2C2C2E] transition-colors"
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">{quote.symbol}</span>
                      <span className="text-xs text-gray-500">{quote.exchange}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-400 max-w-xs truncate">
                    {quote.name}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right font-semibold text-white">
                    {formatPrice(quote.price)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right">
                    <span
                      className={`font-semibold ${
                        quote.change >= 0 ? 'text-green-500' : 'text-red-500'
                      }`}
                    >
                      {quote.change >= 0 ? '+' : ''}
                      {formatPrice(quote.change)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right">
                    <div
                      className={`inline-flex items-center gap-1 px-2 py-1 rounded ${
                        quote.dayChange >= 0
                          ? 'bg-green-500/10 text-green-500'
                          : 'bg-red-500/10 text-red-500'
                      }`}
                    >
                      {quote.dayChange >= 0 ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      <span className="font-semibold text-xs">
                        {formatPercent(quote.dayChange)}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-400">
                    {formatVolume(quote.volume)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-400">
                    {formatMarketCap(quote.marketCap)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-400">
                    {quote.pe ? quote.pe.toFixed(2) : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
