"""
Chart Data Resolvers - Layered resolution system for chart data.

Simple chain: Arrays → Risk Results → Portfolio → Market Data → None
NO pattern matching. NO field discovery. MCP servers handle field mapping.
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


class ChartDataResolver(ABC):
    """Base resolver interface"""
    
    @abstractmethod
    async def resolve(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Resolve data for chart inputs.
        
        Args:
            spec: Chart spec with type and inputs
            context: Runtime context (agent state, mcp servers, etc)
            
        Returns:
            Resolved data dict or None if cannot resolve
        """
        pass
    
    def _get_next_resolver(self) -> Optional['ChartDataResolver']:
        """Get next resolver in chain"""
        return getattr(self, '_next', None)
    
    def set_next(self, resolver: 'ChartDataResolver') -> 'ChartDataResolver':
        """Set next resolver in chain"""
        self._next = resolver
        return resolver


class ArrayDataResolver(ChartDataResolver):
    """Check if data already in array format (including inline data)"""
    
    async def resolve(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use arrays if present, prioritizing inline data convention"""
        inputs = spec.get('inputs', {})
        
        # First check for inline data convention (data or data_dict fields)
        from .utils.validation import extract_inline_data
        inline_data = extract_inline_data(inputs)
        
        if inline_data is not None:
            logger.info("ArrayResolver: Found inline data")
            # Just keep the inline data as-is, no aliasing
            # Charts will need to check for 'data' field
            if isinstance(inline_data, list):
                return {**inputs, 'data': inline_data}
            elif isinstance(inline_data, dict):
                return {**inputs, 'data_dict': inline_data}
        
        # Fall back to checking for any array data
        has_arrays = any(
            isinstance(v, list) and len(v) > 0 
            for v in inputs.values()
        )
        
        if has_arrays:
            logger.info("ArrayResolver: Found existing array data")
            return inputs
        
        # Pass to next
        next_resolver = self._get_next_resolver()
        if next_resolver:
            return await next_resolver.resolve(spec, context)
        return None


class RiskResultResolver(ChartDataResolver):
    """Extract from risk analysis results"""
    
    async def resolve(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract data from risk results"""
        
        risk_results = context.get('risk_results') or context.get('last_risk_analysis', {})
        if not risk_results:
            next_resolver = self._get_next_resolver()
            if next_resolver:
                return await next_resolver.resolve(spec, context)
            return None
        
        inputs = spec.get('inputs', {})
        
        # Just merge risk results with inputs - no pattern matching
        # The builder knows what fields it needs from its schema
        merged = {**inputs, **risk_results}
        
        logger.info(f"RiskResultResolver: Merged {len(risk_results)} fields from risk results")
        return merged


class PortfolioResolver(ChartDataResolver):
    """Extract from portfolio context"""
    
    async def resolve(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract portfolio data from context"""
        
        portfolio = context.get('portfolio') or context.get('current_portfolio', {})
        if not portfolio:
            next_resolver = self._get_next_resolver()
            if next_resolver:
                return await next_resolver.resolve(spec, context)
            return None
        
        inputs = spec.get('inputs', {})
        
        # Just merge portfolio data with inputs - no pattern matching
        merged = {**inputs, **portfolio}
        
        logger.info(f"PortfolioResolver: Merged {len(portfolio)} fields from portfolio")
        return merged


class MarketDataResolver(ChartDataResolver):
    """
    Fetch market data via MCP servers.
    MCP servers handle all field mapping internally.
    """
    
    async def resolve(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch market data using MCP servers"""
        
        inputs = spec.get('inputs', {})
        
        # Get symbol(s) from inputs
        symbol = inputs.get('symbol') or inputs.get('ticker')
        symbols = inputs.get('symbols') or inputs.get('tickers', [])
        
        if not symbol and not symbols:
            # No symbols to fetch
            next_resolver = self._get_next_resolver()
            if next_resolver:
                return await next_resolver.resolve(spec, context)
            return None
        
        # Get MCP server from context
        market_server = self._get_market_server(context)
        if not market_server:
            logger.warning("No MCP market server available")
            next_resolver = self._get_next_resolver()
            if next_resolver:
                return await next_resolver.resolve(spec, context)
            return None
        
        # Get time parameters (default shorter to avoid rate/size issues)
        period = inputs.get('period', '1M')
        start_date = inputs.get('start_date') or inputs.get('from')
        end_date = inputs.get('end_date') or inputs.get('to')
        
        try:
            if symbol:
                # Check server type and use appropriate method
                if hasattr(market_server, 'get_historical_data'):
                    # YFinanceServer
                    data = await market_server.get_historical_data(
                        symbol,
                        period=period,
                        start=start_date,
                        end=end_date
                    )
                    
                    if data:
                        # Parse if JSON string
                        parsed = json.loads(data) if isinstance(data, str) else data
                        # Merge with inputs
                        return {**inputs, **parsed}
                
                elif hasattr(market_server, 'historical_data'):
                    # Refactored FMP server - use the historical_data helper
                    data = await market_server.historical_data.get_historical_data(
                        symbol,
                        period=period,
                        start=start_date,
                        end=end_date
                    )
                    
                    if data:
                        # Parse if JSON string
                        parsed = json.loads(data) if isinstance(data, str) else data
                        # Merge with inputs
                        return {**inputs, **parsed}
                
                else:
                    # Other server without historical data support
                    logger.info(f"Server type {type(market_server).__name__} doesn't support historical data")
                    return None
            
            elif symbols:
                # Multiple symbols - fetch for each
                all_data = {}
                for sym in symbols:
                    data = await market_server.get_historical_data(
                        sym,
                        period=period,
                        start=start_date,
                        end=end_date
                    )
                    
                    if data:
                        parsed = json.loads(data) if isinstance(data, str) else data
                        all_data[sym] = parsed
                
                if all_data:
                    return {**inputs, 'symbol_data': all_data}
        
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
        
        # Pass to next
        next_resolver = self._get_next_resolver()
        if next_resolver:
            return await next_resolver.resolve(spec, context)
        return None
    
    def _get_market_server(self, context: Dict[str, Any]):
        """Get MCP server - create FMP with YFinance fallback"""
        # Try from context first (if provided)
        if 'mcp_servers' in context:
            servers = context['mcp_servers']
            server = servers.get('fmp') or servers.get('market')
            if server:
                return server
        
        # Try from agent
        if 'agent' in context:
            agent = context['agent']
            if hasattr(agent, 'market_server'):
                return agent.market_server
        
        # Create our own FMP server (like risk tools do)
        try:
            # Load environment variables
            from dotenv import load_dotenv
            load_dotenv()
            
            from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
            server = FMPMarketDataServer()
            # Need to connect for HTTP session
            import asyncio
            asyncio.create_task(server.connect())
            return server
        except Exception as e:
            logger.info(f"FMP not available: {e}, using YFinance")
            from core.mcp_servers.YFinanceServer import YFinanceServer
            return YFinanceServer()


class DefaultResolver(ChartDataResolver):
    """Final fallback - charts are optional"""
    
    async def resolve(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return None gracefully - charts are optional"""
        
        chart_type = spec.get('type', 'unknown')
        logger.info(f"DefaultResolver: No data available for {chart_type} chart - returning None (charts are optional)")
        
        # Charts are OPTIONAL - return None gracefully
        return None


def create_resolver_chain() -> ChartDataResolver:
    """
    Create the standard resolver chain.
    
    Simple order - check context first, then fetch if needed:
    1. ArrayDataResolver - Already have arrays
    2. RiskResultResolver - From risk analysis
    3. PortfolioResolver - From portfolio
    4. MarketDataResolver - Fetch via MCP
    5. DefaultResolver - Return None (charts optional)
    """
    array_resolver = ArrayDataResolver()
    risk_resolver = RiskResultResolver()
    portfolio_resolver = PortfolioResolver()
    market_resolver = MarketDataResolver()
    default_resolver = DefaultResolver()
    
    # Chain them
    array_resolver.set_next(risk_resolver)
    risk_resolver.set_next(portfolio_resolver)
    portfolio_resolver.set_next(market_resolver)
    market_resolver.set_next(default_resolver)
    
    return array_resolver