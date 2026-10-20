"""
Minimal WebSocket endpoint for streaming price updates and workflow events.
Following KISS principle - simple implementation, feature flag control.
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Query
from typing import Set, Optional
import asyncio
import json

from core.streaming import KafkaConfig
from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])

# Simple connection manager (no over-engineering)
class ConnectionManager:
    """Minimal WebSocket connection manager"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
        
    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        if not self.active_connections:
            return
            
        # Remove disconnected clients
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
                
        self.active_connections -= disconnected


# Global instances (simple singleton pattern)
manager = ConnectionManager()
kafka_config = KafkaConfig()
price_consumer = None


# Removed startup_event and separate PriceConsumer to avoid mixed consumer models
# All streaming now goes through the ScreenerHub in app_fastapi.py lifespan


@router.websocket("/screener")
async def websocket_screener(
    websocket: WebSocket,
    min_price: float = 0,
    max_price: float = 10000,
    min_pe: float = 0,
    max_pe: float = 100
):
    """Stream filtered stocks from shared ScreenerHub (no consumer per connection)"""
    await manager.connect(websocket)
    client_id = None
    
    try:
        # Get hub from app state (set in lifespan)
        app = websocket.scope.get('app')
        hub = getattr(app.state, 'screener_hub', None) if app else None
        
        if not hub:
            await websocket.send_json({
                'type': 'error',
                'message': 'Screener hub not initialized'
            })
            logger.warning("ScreenerHub not found in app state")
            return
        
        # Create filter function for this client (FMP fields)
        def filter_fn(msg: dict) -> bool:
            try:
                symbol = msg.get('symbol', '')
                # Skip filters for index symbols (starting with ^)
                if symbol.startswith('^'):
                    return True

                # FMP uses simple field names: price, pe
                price = float(msg.get('price', 0))
                pe = float(msg.get('pe', 0))
                return (min_price <= price <= max_price and
                       min_pe <= pe <= max_pe)
            except (TypeError, ValueError):
                return False
        
        # Register client with hub
        client_id = hub.register(websocket, filter_fn)
        logger.info(f"Screener WebSocket registered: {client_id} (filters: ${min_price}-${max_price}, PE {min_pe}-{max_pe})")
        
        # Send initial status
        await websocket.send_json({
            'type': 'status',
            'message': 'Connected to screener stream',
            'filters': {
                'price': f"${min_price}-${max_price}",
                'pe': f"{min_pe}-{max_pe}"
            }
        })
        
        # Stream from client's queue (hub handles everything)
        await hub.stream_to_client(client_id)
        
    except WebSocketDisconnect:
        logger.info(f"Screener WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket screener error: {e}")
    finally:
        # Always unregister to prevent leaks
        if client_id:
            app = websocket.scope.get('app')
            hub = getattr(app.state, 'screener_hub', None) if app else None
            if hub:
                hub.unregister(client_id)
        manager.disconnect(websocket)


@router.get("/health")
async def screener_health(request: Request):
    """Get ScreenerHub health metrics for monitoring"""
    hub = getattr(request.app.state, 'screener_hub', None)
    
    if not hub:
        return {"status": "not_initialized", "kafka_enabled": kafka_config.is_enabled()}
    
    stats = hub.get_stats()
    
    return {
        "status": "healthy" if stats["running"] else "stopped",
        "clients": stats["client_count"],
        "queue_depth": stats["incoming_queue_size"],
        "messages_processed": stats["messages_processed"],
        "uptime_seconds": stats["uptime"],
        "memory_usage_mb": stats["estimated_memory_mb"],
        "config": stats["config"]
    }


@router.websocket("/prices")
async def websocket_prices(websocket: WebSocket):
    """
    WebSocket endpoint for real-time price updates.
    Now uses the same ScreenerHub as /screener to avoid mixed consumer models.
    """
    await manager.connect(websocket)
    client_id = None
    
    try:
        # Get hub from app state (same as screener)
        app = websocket.scope.get('app')
        hub = getattr(app.state, 'screener_hub', None) if app else None
        
        if not hub:
            await websocket.send_json({
                "type": "status",
                "message": "Streaming disabled",
                "kafka_enabled": False
            })
            return
            
        # No filter for prices endpoint - get all data
        def filter_fn(msg: dict) -> bool:
            return True  # Accept all messages
        
        # Register client with hub
        client_id = hub.register(websocket, filter_fn)
        logger.info(f"Price WebSocket registered: {client_id}")
        
        await websocket.send_json({
            "type": "status", 
            "message": "Connected to price stream",
            "kafka_enabled": True
        })
        
        # Stream from client's queue
        await hub.stream_to_client(client_id)
                
    except WebSocketDisconnect:
        logger.info(f"Price WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Unregister from hub
        if client_id and hub:
            hub.unregister(client_id)
        manager.disconnect(websocket)


# Workflow WebSocket endpoint removed - use polling instead
# See GET /api/workflows/workflow-runs/{run_id} for status polling
# Supports ETag/Last-Modified headers for efficient polling every 2 seconds