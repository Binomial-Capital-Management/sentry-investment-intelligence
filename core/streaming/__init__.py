"""
Minimal Kafka streaming module for live price updates.
Following KISS principle - starts with single use case.
"""

from .config import KafkaConfig
from .consumer import PriceConsumer
from .kafka_producer import MarketDataProducer

__all__ = ['KafkaConfig', 'PriceConsumer', 'MarketDataProducer']