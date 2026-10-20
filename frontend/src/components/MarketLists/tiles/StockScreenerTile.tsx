import TradingViewStockScreener from '../TradingViewStockScreener';

export default function StockScreenerTile() {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <TradingViewStockScreener
        theme="light"
        height="100%"
        locale="en"
        defaultColumn="overview"
        defaultScreen="general"
        market="america"
        showToolbar={true}
      />
    </div>
  );
}
