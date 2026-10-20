"""
Chart Registry - Singleton pattern for chart type management.

Simple, clean implementation without unnecessary complexity.
"""

from typing import Dict, Callable, List, Optional, Any, Awaitable
import asyncio
import logging
from functools import lru_cache

from .models import ChartType, ChartSpec, ChartFigure, ChartListItem

logger = logging.getLogger(__name__)


class ChartRegistry:
    """Singleton registry for chart types and builders"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._builders: Dict[ChartType, Callable] = {}
            self._schemas: Dict[ChartType, ChartListItem] = {}
            self._initialized = True
            self._initialize_builders()
    
    def _initialize_builders(self):
        """Register all chart builders"""
        # Import builders lazily to avoid circular imports
        try:
            from .builders import CHART_BUILDERS
            for chart_type, builder_info in CHART_BUILDERS.items():
                self.register(
                    chart_type=chart_type,
                    builder=builder_info['builder'],
                    schema=builder_info['schema']
                )
        except ImportError:
            # Builders not yet implemented
            logger.info("Chart builders not yet available")
    
    def register(
        self, 
        chart_type: ChartType, 
        builder: Callable[[ChartSpec, Dict[str, Any]], Awaitable[ChartFigure]], 
        schema: ChartListItem
    ):
        """Register a chart builder"""
        self._builders[chart_type] = builder
        self._schemas[chart_type] = schema
    
    @lru_cache(maxsize=1)
    def list_charts(self) -> List[ChartListItem]:
        """List all available chart types"""
        return list(self._schemas.values())
    
    def get_schema(self, chart_type: ChartType) -> Optional[ChartListItem]:
        """Get schema for a specific chart type"""
        return self._schemas.get(chart_type)
    
    async def build_chart(
        self, 
        spec: ChartSpec, 
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 1.5
    ) -> Optional[ChartFigure]:
        """Build a chart with timeout and error handling"""
        
        builder = self._builders.get(spec.type)
        if not builder:
            logger.warning(f"No builder for chart type: {spec.type}")
            return None
        
        # Use resolver chain to get data
        from .resolvers import create_resolver_chain
        resolver_chain = create_resolver_chain()
        
        # Convert spec to dict for resolver
        spec_dict = {
            'type': spec.type.value if hasattr(spec.type, 'value') else spec.type,
            'inputs': spec.inputs
        }
        
        # Ensure shared MCP servers available in context
        ctx = dict(context or {})
        if 'mcp_servers' not in ctx:
            try:
                from .tools import _get_shared_mcp_servers
                ctx['mcp_servers'] = _get_shared_mcp_servers()
            except Exception:
                pass

        # Resolve data
        resolved_data = await resolver_chain.resolve(spec_dict, ctx)
        
        if not resolved_data:
            logger.info(f"No data resolved for {spec.type} - charts are optional")
            return None
        
        # Update spec with resolved data
        spec.inputs = resolved_data
        
        try:
            # Run builder with timeout
            result = await asyncio.wait_for(
                builder(spec, context or {}),
                timeout=timeout
            )
            
            # Validate result
            if not isinstance(result, ChartFigure):
                logger.error(f"Builder returned invalid type: {type(result)}")
                return None
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Chart build timeout: {spec.type}")
            return None
        except Exception as e:
            # Log at INFO level with truncated error
            error_msg = str(e)[:100]
            logger.info(f"Chart build failed: {spec.type} - {error_msg}")
            return None
    
    def get_default_charts(self, analysis_type: str, max_charts: int = 3) -> List[ChartType]:
        """Get default chart types for an analysis type"""
        from .models import DEFAULT_CHARTS
        
        defaults = DEFAULT_CHARTS.get(analysis_type, [])
        return defaults[:max_charts]
    
    def clear(self):
        """Clear all registered builders (mainly for testing)"""
        self._builders.clear()
        self._schemas.clear()
        self.list_charts.cache_clear()


# Global registry instance
chart_registry = ChartRegistry()