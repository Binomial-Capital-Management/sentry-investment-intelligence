"""
Kafka producer that publishes real market data to Kafka topics.
Uses FMP's async API for true parallel streaming.
"""
import asyncio
import aiohttp
import json
import orjson  # Fast JSON serialization (5-10x speedup)
import logging
import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketDataProducer:
    """
    Publishes real market data to Kafka.
    Uses FMP's async API for true parallel data fetching.
    """
    
    def __init__(self, config):
        self.config = config
        self.producer = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.fmp_api_key = os.getenv("FMP_API_KEY")
        self.fmp_base_url = "https://financialmodelingprep.com/api"
        
    async def start(self) -> bool:
        """Initialize producer and HTTP session if Kafka is enabled"""
        if not self.config.is_enabled():
            return False
        
        # Check FMP API key
        if not self.fmp_api_key:
            logger.error("FMP_API_KEY not set in environment")
            return False
            
        try:
            from aiokafka import AIOKafkaProducer
            
            # Start Kafka producer
            security_kwargs = {}
            try:
                # Prefer env-driven security config (MSK friendly)
                security_kwargs = getattr(self.config, 'get_client_security_kwargs', lambda: {})()
            except Exception:
                security_kwargs = {}

            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=lambda v: orjson.dumps(v),  # orjson returns bytes directly
                request_timeout_ms=self.config.request_timeout_ms,
                metadata_max_age_ms=self.config.metadata_max_age_ms,
                **security_kwargs,
            )

            # Add timeout to producer start to prevent hanging
            await asyncio.wait_for(self.producer.start(), timeout=45.0)
            
            # Create aiohttp session for FMP API
            self.session = aiohttp.ClientSession()
            
            logger.info("Kafka producer and FMP session started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start producer: {e}")
            return False
    
    async def publish_price(self, symbol: str, price: float, source: str = "yahoo"):
        """Publish a real price update to Kafka"""
        if not self.producer:
            return
            
        message = {
            "symbol": symbol,
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "source": source
        }
        
        try:
            await self.producer.send(self.config.topic_prices, message)
            logger.debug(f"Published: {symbol} = ${price} from {source}")
        except Exception as e:
            logger.error(f"Failed to publish price: {e}")
    
    
    def _safe_float(self, value, default=0.0):
        """Safely convert value to float, handling None and non-numeric values"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    async def publish_screener_data(self, symbol: str, data: dict):
        """Publish normalized screening data to Kafka with defined schema"""
        if not self.producer:
            return

        # Transform FMP quote data to simple schema
        # FMP fields: price, changesPercentage, change, dayLow, dayHigh,
        # yearHigh, yearLow, marketCap, priceAvg50, priceAvg200, volume,
        # avgVolume, exchange, open, previousClose, eps, pe, sharesOutstanding
        message = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            # FMP uses 'price' directly
            "price": self._safe_float(data.get('price')),
            # FMP uses 'pe' directly
            "pe": self._safe_float(data.get('pe')),
            # FMP uses 'volume' directly
            "volume": self._safe_float(data.get('volume')),
            # FMP uses 'marketCap' directly
            "marketCap": self._safe_float(data.get('marketCap')),
            # FMP uses 'changesPercentage' for day change
            "dayChange": self._safe_float(data.get('changesPercentage')),
            # Add 'change' field for absolute change
            "change": self._safe_float(data.get('change'))
        }
        
        try:
            await self.producer.send(self.config.topic_screener, message)
            logger.debug(f"Published normalized data: {symbol} price=${message['price']:.2f}")
        except Exception as e:
            logger.error(f"Failed to publish screener data: {e}")
    
    
    async def fetch_fmp_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch quote data from FMP API (truly async with aiohttp).
        Uses the fast /v3/quote endpoint for screener data.
        """
        if not self.session:
            logger.error("HTTP session not initialized")
            return None
            
        url = f"{self.fmp_base_url}/v3/quote/{symbol}"
        params = {"apikey": self.fmp_api_key}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # FMP returns array, get first element
                    if data and isinstance(data, list) and len(data) > 0:
                        return data[0]
                    logger.warning(f"No data for {symbol}")
                    return None
                else:
                    logger.error(f"FMP API error for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {symbol} from FMP: {e}")
            return None
    
    async def _fetch_and_publish(self, symbol: str):
        """Fetch and publish single symbol data - for parallel execution"""
        try:
            # Use FMP's async quote API
            quote_data = await self.fetch_fmp_quote(symbol)
            if quote_data:
                await self.publish_screener_data(symbol, quote_data)
                logger.debug(f"Published {symbol}")
                return symbol
            return None
        except Exception as e:
            logger.error(f"Error with {symbol}: {e}")
            return None
    
    async def stream_screener_universe(self, symbols: list = None):
        """Stream comprehensive data for stock screening with technical indicators"""
        if not symbols:
            # Expanded universe for a real screener - top 50 liquid stocks
            symbols = [
                # Tech giants
                'AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN',
                # More tech
                'AMD', 'INTC', 'CRM', 'ORCL', 'ADBE', 'NFLX', 'AVGO', 'QCOM',
                # Financial
                'JPM', 'BAC', 'WFC', 'GS', 'MS', 'BRK-B', 'V', 'MA',
                # Healthcare
                'JNJ', 'UNH', 'PFE', 'LLY', 'ABBV', 'MRK', 'CVS',
                # Consumer
                'WMT', 'PG', 'KO', 'PEP', 'MCD', 'DIS', 'NKE', 'SBUX',
                # Energy & Industrial  
                'XOM', 'CVX', 'BA', 'CAT', 'GE', 'MMM',
                # Market Indices (direct symbols)
                '^GSPC', '^IXIC', '^DJI', '^RUT', '^VIX',
                # ETFs
                'SPY', 'QQQ', 'DIA', 'IWM', 'VTI'
            ]
        
        logger.info(f"Starting screener stream for {len(symbols)} symbols using FMP")
        
        # Get config from environment (NO HARDCODING)
        update_interval = self.config.screener_update_interval
        batch_size = self.config.screener_batch_size
        
        while True:
            success_count = 0
            start_time = time.time()
            
            # Process in parallel batches - truly async with FMP
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                
                # Fetch batch in PARALLEL - now truly async with aiohttp!
                tasks = [self._fetch_and_publish(symbol) for symbol in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successful publishes
                success_count += sum(1 for r in results if r and not isinstance(r, Exception))
                
                # Small delay between batches to respect FMP rate limits
                if i + batch_size < len(symbols):
                    await asyncio.sleep(2.0)  # Increased delay to respect FMP rate limits
            
            elapsed = time.time() - start_time
            logger.info(f"Streamed {success_count}/{len(symbols)} symbols in {elapsed:.1f}s")
            
            # Configurable cycle delay (not hardcoded)
            await asyncio.sleep(max(0, update_interval - elapsed))
    
    async def stream_tracker_list(self, list_id: str, tickers: List[str]):
        """
        Stream quotes for user's manual tracker list.
        Polls FMP quote endpoint every 30s for the specific tickers.

        Args:
            list_id: UUID of the tracker list
            tickers: List of ticker symbols to track
        """
        logger.info(f"Starting tracker list stream: {list_id} with {len(tickers)} tickers")

        while True:
            try:
                # Fetch quotes in parallel batches
                for i in range(0, len(tickers), self.config.screener_batch_size):
                    batch = tickers[i:i + self.config.screener_batch_size]

                    tasks = [self.fetch_fmp_quote(sym) for sym in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Publish with list_id metadata
                    for ticker, quote_data in zip(batch, results):
                        if quote_data and not isinstance(quote_data, Exception):
                            message = {
                                "list_id": list_id,
                                "list_type": "tracker",
                                "symbol": ticker,
                                "timestamp": datetime.now().isoformat(),
                                **self._normalize_quote(quote_data)
                            }
                            await self.producer.send(self.config.topic_screener, message)

                    # Small delay between batches
                    if i + self.config.screener_batch_size < len(tickers):
                        await asyncio.sleep(2.0)

                # Wait before next refresh cycle
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Error streaming tracker list {list_id}: {e}")
                await asyncio.sleep(10)  # Back off on error

    async def stream_screener(self, list_id: str, filters: Dict[str, Any]):
        """
        Stream quotes for screener (dynamic filtered list).
        Polls FMP company-screener endpoint to get matching stocks,
        then streams their quotes.

        Args:
            list_id: UUID of the screener
            filters: FMP screener filter parameters
        """
        logger.info(f"Starting screener stream: {list_id} with filters: {filters}")

        while True:
            try:
                # Query FMP screener endpoint
                url = f"{self.fmp_base_url}/v3/stock-screener"
                params = {"apikey": self.fmp_api_key, **filters}

                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        matches = await response.json()
                        logger.info(f"Screener {list_id} found {len(matches)} matches")

                        # Stream quotes for matching stocks
                        for i in range(0, len(matches), self.config.screener_batch_size):
                            batch = matches[i:i + self.config.screener_batch_size]

                            tasks = [self.fetch_fmp_quote(stock['symbol']) for stock in batch]
                            results = await asyncio.gather(*tasks, return_exceptions=True)

                            # Publish with list_id metadata
                            for stock, quote_data in zip(batch, results):
                                if quote_data and not isinstance(quote_data, Exception):
                                    message = {
                                        "list_id": list_id,
                                        "list_type": "screener",
                                        "symbol": stock['symbol'],
                                        "timestamp": datetime.now().isoformat(),
                                        **self._normalize_quote(quote_data)
                                    }
                                    await self.producer.send(self.config.topic_screener, message)

                            # Small delay between batches
                            if i + self.config.screener_batch_size < len(batch):
                                await asyncio.sleep(2.0)
                    else:
                        logger.error(f"FMP screener API error: {response.status}")

                # Screeners refresh slower (60s) since they're more expensive
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error streaming screener {list_id}: {e}")
                await asyncio.sleep(15)  # Back off on error

    def _normalize_quote(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize FMP quote data to consistent format"""
        return {
            "price": self._safe_float(quote_data.get('price')),
            "pe": self._safe_float(quote_data.get('pe')),
            "volume": self._safe_float(quote_data.get('volume')),
            "marketCap": self._safe_float(quote_data.get('marketCap')),
            "dayChange": self._safe_float(quote_data.get('changesPercentage')),
            "change": self._safe_float(quote_data.get('change')),
            "dayLow": self._safe_float(quote_data.get('dayLow')),
            "dayHigh": self._safe_float(quote_data.get('dayHigh')),
            "yearLow": self._safe_float(quote_data.get('yearLow')),
            "yearHigh": self._safe_float(quote_data.get('yearHigh')),
            "previousClose": self._safe_float(quote_data.get('previousClose')),
            "open": self._safe_float(quote_data.get('open')),
            "name": quote_data.get('name', ''),
            "exchange": quote_data.get('exchange', '')
        }

    async def stop(self):
        """Stop producer and cleanup resources gracefully"""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

        if self.session:
            await self.session.close()
            logger.info("FMP session closed")