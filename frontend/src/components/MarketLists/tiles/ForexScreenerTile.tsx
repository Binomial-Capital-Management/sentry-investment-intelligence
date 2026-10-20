import TradingViewForexScreener from '../TradingViewForexScreener';

export default function ForexScreenerTile() {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <TradingViewForexScreener
        theme="light"
        height="100%"
        locale="en"
        defaultColumn="overview"
        defaultScreen="general"
        market="forex"
        showToolbar={true}
      />
    </div>
  );
}
