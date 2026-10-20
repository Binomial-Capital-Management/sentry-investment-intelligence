"""
Minimal Kafka consumer for price updates.
Following KISS principle - just consume and cache prices.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceConsumer:
    """
    Simple Kafka consumer for price updates.
    Gracefully handles when Kafka is disabled or unavailable.
    """
    
    def __init__(self, config):
        self.config = config
        self.consumer = None
        self.price_cache: Dict[str, dict] = {}  # symbol -> {price, timestamp}
        self.is_connected = False
        
    async def start(self) -> bool:
        """
        Start consuming if enabled.
        Returns True if started successfully.
        """
        if not self.config.is_enabled():
            logger.info("Kafka disabled via KAFKA_ENABLED=false")
            return False
            
        try:
            # Lazy import - only if Kafka is enabled
            from aiokafka import AIOKafkaConsumer
            
            self.consumer = AIOKafkaConsumer(
                self.config.topic_prices,
                **self.config.get_consumer_config(),
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            await self.consumer.start()
            self.is_connected = True
            logger.info(f"Kafka consumer started on topic: {self.config.topic_prices}")
            return True
            
        except ImportError:
            logger.warning("aiokafka not installed. Run: pip install aiokafka")
            return False
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            return False
    
    async def stop(self):
        """Stop consumer gracefully"""
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("Kafka consumer stopped")
            except Exception as e:
                logger.error(f"Error stopping consumer: {e}")
            finally:
                self.is_connected = False
    
    async def consume(self) -> AsyncGenerator[dict, None]:
        """
        Simple consume loop that yields price updates.
        Expected message format: {"symbol": "AAPL", "price": 185.23}
        """
        if not self.consumer or not self.is_connected:
            logger.debug("Consumer not connected, no messages to yield")
            return
            
        try:
            async for msg in self.consumer:
                try:
                    # Update cache
                    data = msg.value
                    self.price_cache[data['symbol']] = {
                        'price': data['price'],
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Yield to subscribers
                    yield data
                    
                    logger.debug(f"Price update: {data['symbol']} = ${data['price']}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
            self.is_connected = False
    
    def get_cached_price(self, symbol: str) -> Optional[float]:
        """Get latest cached price for symbol"""
        cached = self.price_cache.get(symbol)
        return cached['price'] if cached else None
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get all cached prices"""
        return {
            symbol: data['price'] 
            for symbol, data in self.price_cache.items()
        }