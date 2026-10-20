"""
Shared Kafka screener consumer hub - single consumer for all WebSocket connections.
Following CODING_RULES.md: NO HARDCODING, async-first, backpressure-safe.
"""
import asyncio
import json
import orjson  # Fast JSON serialization (5-10x speedup)
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from fastapi import WebSocket

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from .config import KafkaConfig
from .indicators import IndicatorCalculator

logger = logging.getLogger(__name__)


@dataclass
class ClientHandle:
    """Handle for a connected WebSocket client"""
    websocket: WebSocket
    filter_fn: Callable[[Dict[str, Any]], bool]
    queue: asyncio.Queue
    client_id: str


class ScreenerHub:
    """
    Shared Kafka consumer hub that fans out messages to WebSocket clients.
    Single consumer per app instance to eliminate rebalancing on client churn.
    """
    
    def __init__(self, config: KafkaConfig):
        """
        Initialize the screener hub with configuration from environment.
        
        Args:
            config: Kafka configuration with all settings from env vars
        """
        self.config = config
        
        # Kafka consumer (created once)
        self.consumer: Optional[AIOKafkaConsumer] = None
        
        # Incoming queue for Kafka messages (bounded, drop-oldest)
        self.incoming_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)
        
        # Registry of connected clients
        self.clients: Dict[str, ClientHandle] = {}
        self.client_counter = 0
        
        # Background tasks
        self.consume_task: Optional[asyncio.Task] = None
        self.dispatch_task: Optional[asyncio.Task] = None
        
        # Ring buffer for last N messages (configurable size)
        self.recent_messages = deque(maxlen=config.snapshot_size)
        
        # Pre-enrichment with technical indicators
        self.indicator_calculator = IndicatorCalculator(window_size=100)
        
        # Metrics
        self.messages_processed = 0
        self.start_time = None
        
        # State
        self.running = False
        self._lock = asyncio.Lock()
    
    async def start(self) -> bool:
        """
        Start the hub (idempotent).
        Returns True if started successfully.
        """
        async with self._lock:
            if self.running:
                logger.info("ScreenerHub already running")
                return True
            
            if not self.config.is_enabled():
                logger.info("Kafka disabled, ScreenerHub not starting")
                return False
            
            try:
                # Create Kafka consumer with NO consumer group (avoids rebalancing)
                self.consumer = AIOKafkaConsumer(
                    self.config.topic_screener,
                    bootstrap_servers=self.config.bootstrap_servers,
                    group_id=None,  # NO GROUP = NO REBALANCING
                    auto_offset_reset='latest',
                    value_deserializer=None,  # Handle JSON errors manually
                    enable_auto_commit=False,  # No commits without group
                )
                
                await self.consumer.start()
                logger.info(f"ScreenerHub: Kafka consumer started (topic={self.config.topic_screener}, no group)")
                
                # Start background tasks
                self.consume_task = asyncio.create_task(self._consume_loop())
                self.dispatch_task = asyncio.create_task(self._dispatch_loop())
                
                self.running = True
                self.start_time = time.time()
                logger.info("ScreenerHub: Started successfully with single consumer")
                return True
                
            except Exception as e:
                logger.error(f"ScreenerHub: Failed to start - {e}")
                await self._cleanup()
                return False
    
    async def stop(self):
        """Stop the hub (idempotent)."""
        async with self._lock:
            if not self.running:
                return
            
            logger.info("ScreenerHub: Stopping...")
            self.running = False
            
            # Cancel tasks
            if self.consume_task:
                self.consume_task.cancel()
                try:
                    await self.consume_task
                except asyncio.CancelledError:
                    pass
            
            if self.dispatch_task:
                self.dispatch_task.cancel()
                try:
                    await self.dispatch_task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup
            await self._cleanup()
            logger.info("ScreenerHub: Stopped")
    
    async def _cleanup(self):
        """Clean up resources."""
        if self.consumer:
            try:
                await self.consumer.stop()
            except Exception as e:
                logger.error(f"ScreenerHub: Error stopping consumer - {e}")
            self.consumer = None
        
        # Clear queues and clients
        self.clients.clear()
        while not self.incoming_queue.empty():
            try:
                self.incoming_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    async def _consume_loop(self):
        """
        Background task: Read from Kafka, push to incoming queue.
        Never blocks on WebSocket operations. Resilient to JSON errors.
        """
        logger.info("ScreenerHub: Consume loop started")
        
        while self.running and self.consumer:
            try:
                # Fetch messages from Kafka (with timeout to allow cancellation)
                messages = await asyncio.wait_for(
                    self.consumer.getmany(timeout_ms=1000, max_records=10),
                    timeout=2.0
                )
                
                for topic_partition, records in messages.items():
                    for record in records:
                        try:
                            # Parse JSON with orjson (faster, handle errors gracefully)
                            try:
                                message = orjson.loads(record.value)
                            except (orjson.JSONDecodeError, AttributeError, TypeError) as e:
                                logger.error(f"ScreenerHub: Invalid JSON in Kafka message - {e}")
                                continue  # Skip bad message
                            
                            # Pre-enrich message with technical indicators
                            message = self.indicator_calculator.enrich_message(message)
                            
                            # Add to incoming queue (aggressive backpressure handling)
                            if self.incoming_queue.full():
                                # Drop multiple oldest messages to recover quickly during bursts
                                dropped = 0
                                while self.incoming_queue.full() and dropped < 10:
                                    try:
                                        self.incoming_queue.get_nowait()
                                        dropped += 1
                                    except asyncio.QueueEmpty:
                                        break
                                if dropped > 0:
                                    logger.debug(f"ScreenerHub: Dropped {dropped} oldest messages from incoming queue")
                            
                            self.incoming_queue.put_nowait(message)
                            
                            # Add to recent messages buffer
                            self.recent_messages.append(message)
                            
                        except Exception as e:
                            logger.error(f"ScreenerHub: Error processing message - {e}")
                            continue  # Don't crash on single message error
                            
            except asyncio.TimeoutError:
                # Normal timeout, continue
                continue
            except asyncio.CancelledError:
                logger.info("ScreenerHub: Consume loop cancelled")
                break
            except KafkaError as e:
                logger.error(f"ScreenerHub: Kafka error - {e}")
                await asyncio.sleep(1)  # Brief pause before retry
            except Exception as e:
                logger.error(f"ScreenerHub: Unexpected error in consume loop - {e}")
                await asyncio.sleep(1)
        
        logger.info("ScreenerHub: Consume loop ended")
    
    async def _dispatch_loop(self):
        """
        Background task: Pop from incoming queue and fan-out to clients.
        Applies per-client filters and manages backpressure.
        """
        logger.info("ScreenerHub: Dispatch loop started")
        
        while self.running:
            try:
                # Wait for message (with timeout for cancellation)
                try:
                    message = await asyncio.wait_for(
                        self.incoming_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                self.messages_processed += 1
                
                # Log periodically
                if self.messages_processed % 100 == 0:
                    queue_depth = self.incoming_queue.qsize()
                    logger.info(f"ScreenerHub: {len(self.clients)} clients, queue depth: {queue_depth}, processed: {self.messages_processed}")
                
                # Fan out to all registered clients
                dead_clients = []
                
                for client_id, client in list(self.clients.items()):
                    try:
                        # Apply client's filter (handle filter errors)
                        try:
                            if not client.filter_fn(message):
                                continue
                        except Exception as e:
                            logger.debug(f"ScreenerHub: Filter error for {client_id} - {e}")
                            continue
                        
                        # Add to client queue (aggressive backpressure handling)
                        if client.queue.full():
                            # Drop multiple oldest messages to recover quickly during bursts
                            dropped = 0
                            while client.queue.full() and dropped < 5:
                                try:
                                    client.queue.get_nowait()
                                    dropped += 1
                                except asyncio.QueueEmpty:
                                    break
                            if dropped > 0:
                                logger.debug(f"ScreenerHub: Dropped {dropped} oldest for client {client_id}")
                        
                        client.queue.put_nowait(message)
                        
                    except Exception as e:
                        logger.debug(f"ScreenerHub: Error dispatching to {client_id} - {e}")
                        dead_clients.append(client_id)
                
                # Remove dead clients
                for client_id in dead_clients:
                    self.unregister(client_id)
                    
            except asyncio.CancelledError:
                logger.info("ScreenerHub: Dispatch loop cancelled")
                break
            except Exception as e:
                logger.error(f"ScreenerHub: Error in dispatch loop - {e}")
                await asyncio.sleep(0.1)
        
        logger.info("ScreenerHub: Dispatch loop ended")
    
    def register(self, websocket: WebSocket, filter_fn: Callable[[Dict[str, Any]], bool]) -> str:
        """
        Register a new client with the hub.
        
        Args:
            websocket: The WebSocket connection
            filter_fn: Function to filter messages for this client
            
        Returns:
            Client ID for later unregistration
        """
        self.client_counter += 1
        client_id = f"client_{self.client_counter}"
        
        client = ClientHandle(
            websocket=websocket,
            filter_fn=filter_fn,
            queue=asyncio.Queue(maxsize=self.config.max_queue_size),
            client_id=client_id
        )
        
        self.clients[client_id] = client
        
        # Prime with recent messages (apply filter)
        primed_count = 0
        for msg in self.recent_messages:
            try:
                if filter_fn(msg):
                    client.queue.put_nowait(msg)
                    primed_count += 1
            except asyncio.QueueFull:
                break
            except Exception:
                pass  # Ignore filter errors during priming
        
        logger.info(f"ScreenerHub: Registered {client_id} (total: {len(self.clients)}, primed: {primed_count})")
        return client_id
    
    def unregister(self, client_id: str):
        """
        Unregister a client from the hub.
        
        Args:
            client_id: The client ID to unregister
        """
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"ScreenerHub: Unregistered {client_id} (remaining: {len(self.clients)})")
    
    async def stream_to_client(self, client_id: str) -> None:
        """
        Stream messages to a specific client from its queue.
        This is called from the WebSocket handler.
        
        Args:
            client_id: The client to stream to
        """
        if client_id not in self.clients:
            logger.error(f"ScreenerHub: Client {client_id} not found")
            return
        
        client = self.clients[client_id]
        
        while client_id in self.clients:
            try:
                # Wait for message in client's queue
                message = await asyncio.wait_for(client.queue.get(), timeout=30.0)
                
                # Send to WebSocket with timeout
                try:
                    await asyncio.wait_for(
                        client.websocket.send_json({
                            'type': 'screener_match',
                            'data': message
                        }),
                        timeout=self.config.websocket_send_timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"ScreenerHub: Send timeout for {client_id}")
                    break  # Client too slow, disconnect
                
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await asyncio.wait_for(
                        client.websocket.send_json({'type': 'ping'}),
                        timeout=self.config.websocket_send_timeout
                    )
                except:
                    break  # WebSocket closed or slow
            except Exception as e:
                logger.debug(f"ScreenerHub: Error streaming to {client_id} - {e}")
                break
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get hub statistics for monitoring.
        
        Returns:
            Dictionary with metrics
        """
        uptime = time.time() - self.start_time if self.start_time else 0
        
        # Estimate memory usage (rough)
        queue_items = self.incoming_queue.qsize()
        client_queue_items = sum(c.queue.qsize() for c in self.clients.values())
        snapshot_items = len(self.recent_messages)
        
        # Assume ~1KB per message average
        estimated_memory_mb = (queue_items + client_queue_items + snapshot_items) * 0.001
        
        return {
            "running": self.running,
            "client_count": len(self.clients),
            "incoming_queue_size": queue_items,
            "total_client_queue_items": client_queue_items,
            "snapshot_size": snapshot_items,
            "messages_processed": self.messages_processed,
            "uptime": round(uptime, 1),
            "estimated_memory_mb": round(estimated_memory_mb, 2),
            "config": {
                "topic": self.config.topic_screener,
                "max_queue_size": self.config.max_queue_size,
                "snapshot_size": self.config.snapshot_size,
                "send_timeout": self.config.websocket_send_timeout
            }
        }