import TradingViewCryptoHeatmap from '../TradingViewCryptoHeatmap';

export default function CryptoHeatmapTile() {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <TradingViewCryptoHeatmap theme="light" height="100%" locale="en" />
    </div>
  );
}
