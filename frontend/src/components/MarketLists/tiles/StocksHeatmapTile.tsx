import TradingViewHeatmap from '../TradingViewHeatmap';

export default function StocksHeatmapTile() {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <TradingViewHeatmap
        dataMode="stock"
        theme="light"
        height="100%"
        locale="en"
        blockSize="market_cap_basic"
        blockColor="change"
      />
    </div>
  );
}
