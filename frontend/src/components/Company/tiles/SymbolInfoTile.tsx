import { useEffect, useRef } from 'react';
import { useCompanyDetail } from '../mosaic/CompanyDetailContext';

export default function SymbolInfoTile() {
  const { ticker } = useCompanyDetail();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !ticker) return;
    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-info.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbol: ticker,
      width: '100%',
      colorTheme: 'light',
      isTransparent: false,
      locale: 'en',
    });
    containerRef.current.appendChild(script);

    return () => { if (containerRef.current) containerRef.current.innerHTML = ''; };
  }, [ticker]);

  return (
    <div
      className="tradingview-widget-container"
      ref={containerRef}
      style={{ width: '100%', height: '100%', overflow: 'hidden' }}
    >
      <div className="tradingview-widget-container__widget" />
    </div>
  );
}
