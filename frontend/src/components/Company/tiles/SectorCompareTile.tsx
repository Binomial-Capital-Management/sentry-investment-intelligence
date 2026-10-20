import { useEffect, useRef, useState } from 'react';
import { useCompanyDetail } from '../mosaic/CompanyDetailContext';

const GICS_SECTOR_ETFS: { label: string; etf: string }[] = [
  { label: 'Technology',       etf: 'XLK'  },
  { label: 'Healthcare',       etf: 'XLV'  },
  { label: 'Financials',       etf: 'XLF'  },
  { label: 'Consumer Disc.',   etf: 'XLY'  },
  { label: 'Consumer Staples', etf: 'XLP'  },
  { label: 'Industrials',      etf: 'XLI'  },
  { label: 'Energy',           etf: 'XLE'  },
  { label: 'Materials',        etf: 'XLB'  },
  { label: 'Utilities',        etf: 'XLU'  },
  { label: 'Real Estate',      etf: 'XLRE' },
  { label: 'Communications',   etf: 'XLC'  },
  { label: 'S&P 500',          etf: 'SPY'  },
  { label: 'Nasdaq 100',       etf: 'QQQ'  },
];

export default function SectorCompareTile() {
  const { ticker } = useCompanyDetail();
  const [selectedEtf, setSelectedEtf] = useState('XLK');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !ticker) return;
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
    script.type = 'text/javascript';
    script.async = true;

    const sectorLabel = GICS_SECTOR_ETFS.find(s => s.etf === selectedEtf)?.label ?? selectedEtf;

    script.innerHTML = JSON.stringify({
      symbols: [
        [ticker,    `${ticker}|12M`],
        [selectedEtf, `${selectedEtf}|12M`],
      ],
      chartOnly: false,
      width: '100%',
      height: '100%',
      locale: 'en',
      colorTheme: 'light',
      autosize: true,
      showVolume: false,
      showMA: false,
      hideDateRanges: false,
      hideMarketStatus: false,
      hideSymbolLogo: false,
      scalePosition: 'right',
      scaleMode: 'Normal',
      fontFamily: '-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif',
      fontSize: '10',
      noTimeScale: false,
      valuesTracking: '1',
      changeMode: 'price-and-percent',
      chartType: 'area',
      lineType: 0,
      dateRanges: ['1m|1D', '6m|120', '12m|1D', '60m|1W', 'all|1M'],
      lineWidth: 2,
      title: `${ticker} vs ${sectorLabel} (${selectedEtf})`,
    });

    containerRef.current.appendChild(script);
    return () => { if (containerRef.current) containerRef.current.innerHTML = ''; };
  }, [ticker, selectedEtf]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      {/* Sector picker */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 10px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafafa',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Compare vs
        </span>
        <select
          value={selectedEtf}
          onChange={(e) => setSelectedEtf(e.target.value)}
          style={{
            fontSize: '12px',
            fontWeight: '500',
            color: '#111827',
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            padding: '3px 8px',
            cursor: 'pointer',
            fontFamily: 'inherit',
            outline: 'none',
          }}
        >
          {GICS_SECTOR_ETFS.map(({ label, etf }) => (
            <option key={etf} value={etf}>
              {label} ({etf})
            </option>
          ))}
        </select>
      </div>

      {/* Chart */}
      <div
        className="tradingview-widget-container"
        ref={containerRef}
        style={{ flex: 1, minHeight: 0, width: '100%' }}
      >
        <div className="tradingview-widget-container__widget" style={{ height: '100%', width: '100%' }} />
      </div>
    </div>
  );
}
