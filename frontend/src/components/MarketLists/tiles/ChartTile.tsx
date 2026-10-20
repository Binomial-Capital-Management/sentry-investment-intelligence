import { useState } from 'react';
import TradingViewWidget from '../TradingViewWidget';
import { TickerSearch } from '../TickerSearch';

export default function ChartTile() {
  const [symbol, setSymbol] = useState('NASDAQ:AAPL');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      {/* Symbol picker */}
      <div style={{
        padding: '6px 10px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafafa',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      }}>
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Symbol
        </span>
        <TickerSearch
          onSelect={(result) => setSymbol(`${result.exchange}:${result.symbol}`)}
          placeholder="Search ticker…"
        />
        <span style={{ fontSize: '12px', fontWeight: '600', color: '#111827' }}>{symbol}</span>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <TradingViewWidget
          symbol={symbol}
          theme="light"
          height="100%"
          autosize={true}
          interval="D"
          allowSymbolChange={true}
          backgroundColor="#ffffff"
          gridColor="rgba(46,46,46,0.06)"
          hideTopToolbar={false}
          hideSideToolbar={true}
          hideLegend={false}
          hideVolume={false}
          saveImage={true}
        />
      </div>
    </div>
  );
}
