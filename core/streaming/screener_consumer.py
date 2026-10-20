"""
Kafka consumer for screener data.
Cloned from PriceConsumer but uses screener topic and format.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ScreenerConsumer:
    """
    Kafka consumer for screener data stream.
    Consumes from screener-data topic with full stock metrics.
    """
    
    def __init__(self, config):
        self.config = config
        self.consumer = None
        self.screener_cache: Dict[str, dict] = {}  # symbol -> full metrics
        self.is_connected = False
        
    async def start(self) -> bool:
        """
        Start consuming screener data if enabled.
        Returns True if started successfully.
        """
        if not self.config.is_enabled():
            logger.info("Kafka disabled via KAFKA_ENABLED=false")
            return False
            
        try:
            # Lazy import - only if Kafka is enabled
            from aiokafka import AIOKafkaConsumer
            
            self.consumer = AIOKafkaConsumer(
                self.config.topic_screener,  # Use screener topic
                **self.config.get_consumer_config(),
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            await self.consumer.start()
            self.is_connected = True
            logger.info(f"Screener consumer started on topic: {self.config.topic_screener}")
            return True
            
        except ImportError:
            logger.warning("aiokafka not installed. Run: pip install aiokafka")
            return False
        except Exception as e:
            logger.error(f"Failed to start screener consumer: {e}")
            return False
    
    async def stop(self):
        """Stop consumer gracefully"""
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("Screener consumer stopped")
            except Exception as e:
                logger.error(f"Error stopping consumer: {e}")
            finally:
                self.is_connected = False
    
    async def consume(self) -> AsyncGenerator[dict, None]:
        """
        Consume loop that yields screener data.
        Expected format: {"symbol": "AAPL", "price": 185.23, "pe": 32.5, ...}
        """
        if not self.consumer or not self.is_connected:
            logger.debug("Consumer not connected, no messages to yield")
            return
            
        try:
            async for msg in self.consumer:
                try:
                    # Update cache with full metrics
                    data = msg.value
                    self.screener_cache[data['symbol']] = data
                    
                    # Yield to subscribers
                    yield data
                    
                    logger.debug(f"Screener update: {data['symbol']} = ${data.get('price', 0)}")
                    
                except Exception as e:
                    logger.error(f"Error processing screener message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Screener consumer loop error: {e}")
            self.is_connected = False
    
    def get_cached_metrics(self, symbol: str) -> Optional[dict]:
        """Get latest cached metrics for symbol"""
        return self.screener_cache.get(symbol)
    
    def get_all_stocks(self) -> Dict[str, dict]:
        """Get all cached stock metrics"""
        return self.screener_cache.copy()