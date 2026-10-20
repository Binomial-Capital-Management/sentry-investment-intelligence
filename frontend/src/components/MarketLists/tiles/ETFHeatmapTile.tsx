import TradingViewETFHeatmap from '../TradingViewETFHeatmap';

export default function ETFHeatmapTile() {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <TradingViewETFHeatmap
        theme="light"
        height="100%"
        locale="en"
        blockSize="volume"
        blockColor="change"
        grouping="asset_class"
      />
    </div>
  );
}
