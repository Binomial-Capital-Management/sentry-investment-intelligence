import TradingViewCryptoScreener from '../TradingViewCryptoScreener';

export default function CryptoScreenerTile() {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <TradingViewCryptoScreener
        theme="light"
        height="100%"
        locale="en"
        defaultColumn="overview"
        defaultScreen="top_gainers"
        showToolbar={true}
      />
    </div>
  );
}
