"""
LangGraph Orchestrator - Minimal Implementation for Handback Fix
Status: In Development
Created: August 2025

PURPOSE: Solve the handback problem where Risk Specialist cannot return control to Generalist.
Uses LangGraph's supervisor pattern for orchestration while preserving all OpenAI SDK functionality.

ARCHITECTURE:
- LangGraph: Orchestration layer (routing decisions)
- OpenAI SDK: Agent execution (all existing functionality preserved)
- 3 nodes: supervisor, generalist, risk_specialist
- Supervisor makes routing decisions based on agent responses

This is a MINIMAL implementation that only fixes handback. All existing features preserved.
"""

from typing import Dict, List, Any, Optional, Literal, Tuple
import logging
import os
import asyncio
from datetime import datetime
import sqlite3
import aiosqlite

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Context utils import
from core.utils.context_utils import (
    user_context,
    set_token_sink,
    reset_token_sink,
    set_drive_context,
    reset_drive_context,
    set_cancel_event,
    reset_cancel_event,
)

# OpenAI Agents SDK imports
from agents import Runner, SQLiteSession

# Import cache manager for performance optimization
from core.ai.utils.cache_manager import cache_manager
from core.ai.utils.message_compactor import get_provider_from_model, message_to_dict
from core.config import config as app_config

# Import separated node and utility functions
from core.ai.langgraph_nodes import (
    supervisor_node,
    supervisor_routing,
    generalist_node,
    risk_specialist_node,
    document_analyst_node,
    comparable_companies_node,
    chart_analyst_node,
    quant_coding_node,
    structuring_analyst_node,
    dcf_agent_node,
    prediction_markets_analyst_node,
)
from core.agents.PredictionMarketsAnalyst import create_prediction_markets_analyst
from core.ai.langgraph_utils import execute_with_retry
from core.charts.storage import get_chart

# Pydantic and LangChain imports for dynamic routing
from pydantic import BaseModel, Field, ConfigDict
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class RouterDecision(BaseModel):
    """Structured output for supervisor routing decisions"""
    next_agent: Literal[
        "generalist",
        "risk_specialist",
        "document_analyst",
        "comparable_companies",
        "chart_analyst",
        "quant_coding",
        "options_coding",
        "alternatives_coding",
        "institutional_activity",
        "dcf_agent",
        "funds_products_analyst",
        "prediction_markets_analyst",
        "private_markets",
        "portfolio_semantic_agent",
        "structuring_analyst",
        "end",
    ] = Field(
        description="Which agent to route to next, or 'end' if conversation is complete"
    )
    reasoning: str = Field(
        description="Brief explanation of the routing decision"
    )
    is_complete: bool = Field(
        default=False,
        description="True if the conversation is complete or agent is handing back"
    )
    status_message: str = Field(
        description="Brief user-facing message (5-7 words) describing what analysis will happen. Include any tickers/companies/entities mentioned in the user query. Examples: 'Analyzing AAPL risk exposure...', 'Comparing MSFT vs GOOGL...', 'Calculating portfolio VaR...', 'Extracting NVDA trend components...'. Be specific and contextual."
    )


class ConversationState(TypedDict):
    """State that flows through the LangGraph nodes with enhanced portfolio management"""
    messages: Annotated[list, add_messages]
    current_user_query: str
    last_agent_response: str
    session_id: str
    user_id: Optional[str]
    should_continue: bool
    next_agent: Optional[str]
    status_message: Optional[str]  # User-facing status message for loading UI
    calculation_results: Optional[str]  # Store raw calculation data
    handback_pending: bool  # Track handback intent
    routing_history: Optional[List[Dict[str, str]]]  # Track routing decisions
    agent_mode: Optional[str]  # User-selected agent mode: 'auto', 'risk', 'web', 'market', 'filings'
    deep_analysis_mode: Optional[bool]  # Deep analysis flag to bypass terminal agents
    force_web_search: Optional[bool]  # Force web search when /search command is used
    selected_model: Optional[str]  # User-selected model from frontend dropdown
    prioritized_tools: Optional[List[str]]  # Tools the user wants prioritized/forced

    # Enhanced portfolio state management
    portfolio_state: Optional[Dict[str, Any]]  # Track portfolio composition
    risk_results: Optional[Dict[str, Any]]  # Aggregate risk calculation results
    optimization_suggestions: Optional[Dict[str, Any]]  # Track optimization recommendations
    workflow_context: Optional[Dict[str, Any]]  # Context for multi-tool workflows
    file_ids: Optional[List[str]]  # Attached file IDs for file tools
    drive_context: Optional[Dict[str, Any]]  # Google Drive credential/context
    drive_file_ids: Optional[List[str]]  # Google Drive file IDs supplied by user
    multi_agent_hops: Optional[int]  # Number of times supervisor dispatched an agent this session
    deep_analysis_hop_limit: Optional[int]  # Safety cap for deep analysis loops

    # Visualization and sources (ensure LangGraph preserves these keys)
    charts: Optional[List[Dict[str, Any]]]  # Charts generated by tools
    search_sources: Optional[List[Dict[str, Any]]]  # Sources from web search

    # Code execution data from QuantCoding agent
    code_execution_data: Optional[Dict[str, Any]]  # Contains generated_files, container_id, code_blocks
    last_provider: Optional[str]
    _provider_messages: Optional[List[Dict[str, Any]]]
    errors: Optional[List[Dict[str, Any]]]  # Structured error envelopes

    # Memory Notebook: pre-loaded notes for context injection (see context_manager.py)
    _memory_notes: Optional[List[Dict[str, Any]]]  # Memory notes loaded at start
    _memory_chunks: Optional[List[Dict[str, Any]]]  # Retrieved memory chunks

    # NOTE: token_sink and cancel_event are NOT in state - they use context variables
    # to avoid msgpack serialization errors (Queue objects cannot be serialized)
    # See core/utils/context_utils.py: get_token_sink(), set_token_sink(), get_cancel_event(), set_cancel_event()


class LangGraphOrchestrator:
    """
    Minimal LangGraph wrapper around existing OpenAI agents to fix handback problem.

    Uses supervisor pattern:
    1. User query → Supervisor (routing decision)
    2. Supervisor → Generalist or Risk Specialist
    3. Agent response → Supervisor (handback decision)
    4. Loop until conversation complete
    """

    def __init__(self, agent_model: str = None):
        """Initialize with existing agents and minimal LangGraph wrapper"""
        # Import components directly to avoid circular imports
        from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
        from core.mcp_servers.fmp.FMPDocumentServer import FMPDocumentServer
        from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
        from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
        from core.mcp_servers.fmp.FMPTradeFlowServer import FMPTradeFlowServer
        from core.mcp_servers.YFinanceServer import YFinanceServer  # YFinance fallback
        from core.mcp_servers.EconomicDataServer import EconomicDataServer
        from core.mcp_servers.SECFilingServer import SECFilingServer  # NEW: SEC filings
        from core.agents.MainAgent import create_main_agent
        from core.agents.RiskSpecialistAgent import create_risk_specialist_agent
        from core.agents.DocumentAnalystAgent import create_document_analyst_agent
        from core.agents.ComparableCompaniesAgent import create_comparable_companies_agent
        from core.agents.ChartAnalystAgent import create_chart_analyst_agent
        from core.agents.QuantCodingAgent import create_quant_coding_agent
        from core.agents.StructuringAgent import create_structuring_agent
        from core.agents.AlternativesCodingAgent import create_alternatives_coding_agent
        from core.agents.OptionsCodingAgent import create_options_coding_agent
        from core.agents.InstitutionalActivityAgent import create_institutional_activity_agent
        from core.agents.DCFAgent import create_dcf_agent
        from core.agents.FundsProductsAnalyst import create_funds_products_analyst
        from core.agents.PrivateMarketsAgent import create_private_markets_agent
        from core.agents.DataSemanticAgent import create_data_semantic_agent
        from core.mcp_servers.polygon import (
            PolygonOptionsFuturesServer,
            PolygonCryptoFXServer,
        )
        from core.mcp_servers.polymarket import PolymarketServer
        from core.mcp_servers.quiver import QuiverQuantServer
        from core.mcp_servers.unusualwhales import (
            UWOptionsServer,
            UWInstitutionalServer,
            UWMarketServer,
        )

        # Initialize the router based on configuration
        router_model = os.getenv("LANGGRAPH_ROUTER_MODEL", "gpt-5-nano")  # Default to nano for speed/cost

        # Create router based on model choice - NO HARDCODING
        self.structured_router = self._create_router(router_model)
        self.o4_mini_router = None
        self.deep_analysis_max_hops = getattr(app_config, "deep_analysis_max_hops", 6)
        self.startup_warnings: List[str] = []

        # Track active streaming runs for cooperative cancellation
        self._active_runs: Dict[str, asyncio.Task] = {}
        self._runs_lock = asyncio.Lock()

        # Hard cap for streaming runs to prevent infinite loops during failures
        self.langgraph_stream_timeout_seconds = getattr(
            app_config,
            "langgraph_stream_timeout_seconds",
            1200,  # 20 minutes default to allow long-running agents
        )

        # Initialize MCP servers - FMP as primary, YFinance as fallback
        try:
            self.fmp_market_server = FMPMarketDataServer()
            self.fmp_document_server = FMPDocumentServer()
            self.fmp_valuation_server = FMPAdvancedValuationServer()
            self.fmp_alternatives_server = FMPAlternativesServer()
            self.fmp_tradeflow_server = FMPTradeFlowServer()
            self.use_fmp = True
            logger.info("Using FMP as primary market data source")
            logger.info("FMPAlternativesServer and FMPTradeFlowServer initialized successfully")
        except Exception as e:
            logger.warning(f"FMP initialization failed: {e}, using YFinance")
            self.use_fmp = False
            self.startup_warnings.append("FMP unavailable; using YFinance fallback (degraded market/alternatives coverage).")

        # Always keep YFinance as fallback
        self.yfinance_server = YFinanceServer()
        self.economic_server = EconomicDataServer()

        # Initialize Polygon servers for options and crypto/FX
        self.polygon_options_server = None
        self.polygon_crypto_server = None
        self.options_coding = None
        self.polymarket_server = None
        try:
            self.polymarket_server = PolymarketServer()
            logger.info(
                "Polymarket server initialized: %s",
                self.polymarket_server.__class__.__name__,
            )
        except Exception as e:
            logger.warning("Polymarket MCP server initialization failed: %s", e)
            self.polymarket_server = None
            self.startup_warnings.append("Prediction markets MCP server unavailable; analysis will run degraded.")
        self.quiver_server = None
        try:
            self.quiver_server = QuiverQuantServer()
            logger.info(
                "Quiver server initialized: %s",
                self.quiver_server.__class__.__name__,
            )
        except Exception as e:
            logger.warning("Quiver MCP server initialization failed: %s", e)
            self.quiver_server = None
            self.startup_warnings.append("Quiver server unavailable; political/alternative data coverage will run degraded.")
        self.prediction_markets_analyst = None
        try:
            self.polygon_options_server = PolygonOptionsFuturesServer()
            self.polygon_crypto_server = PolygonCryptoFXServer()
            logger.info(
                "Polygon MCP servers initialized: %s",
                [
                    server.__class__.__name__
                    for server in (self.polygon_options_server, self.polygon_crypto_server)
                    if server is not None
                ],
            )
        except Exception as e:
            logger.warning("Polygon MCP server initialization failed: %s", e)
            self.polygon_options_server = None
            self.polygon_crypto_server = None
            self.startup_warnings.append("Polygon options/crypto servers unavailable; options/alternatives data will be limited.")
        if self.polymarket_server is None:
            logger.warning("Prediction markets MCP server unavailable; agent will run degraded.")

        # Initialize SEC Filing Server (always available)
        try:
            self.sec_filing_server = SECFilingServer()
            logger.info(f"SEC Filing Server initialized successfully: {self.sec_filing_server}")
            # Log available tools
            if hasattr(self.sec_filing_server, 'get_tools'):
                tools = self.sec_filing_server.get_tools()
                logger.info(f"SEC Filing Server has {len(tools)} tools available:")
                for tool in tools:
                    if 'function' in tool:
                        logger.info(f"  - {tool['function'].get('name', 'unknown')}")
        except Exception as e:
            logger.error(f"SEC Filing Server initialization failed: {e}", exc_info=True)
            self.sec_filing_server = None
            self.startup_warnings.append("SEC filing server unavailable; filing analysis will be limited.")

        # Initialize Unusual Whales servers for options flow, institutional, and market data
        self.uw_options_server = None
        self.uw_institutional_server = None
        self.uw_market_server = None
        try:
            self.uw_options_server = UWOptionsServer()
            self.uw_institutional_server = UWInstitutionalServer()
            self.uw_market_server = UWMarketServer()
            logger.info(
                "Unusual Whales MCP servers initialized: %s",
                [
                    server.__class__.__name__
                    for server in (self.uw_options_server, self.uw_institutional_server, self.uw_market_server)
                ],
            )
        except Exception as e:
            logger.warning("Unusual Whales MCP server initialization failed: %s", e)
            self.uw_options_server = None
            self.uw_institutional_server = None
            self.uw_market_server = None
            self.startup_warnings.append("Unusual Whales servers unavailable; options flow/institutional data limited.")

        # Create agents using factory functions for clean separation
        # Use FMP servers if available, fallback to YFinance
        # Use provided model or default from config
        self.agent_model = agent_model
        
        if self.use_fmp:
            self.risk_specialist = create_risk_specialist_agent(
                self.fmp_market_server,
                self.economic_server,
                uw_options_server=self.uw_options_server,
                uw_market_server=self.uw_market_server,
                model=agent_model
            )
            additional_servers = [
                server
                for server in (
                    self.polygon_options_server,
                    self.polygon_crypto_server,
                    self.quiver_server,
                    self.uw_options_server,
                    self.uw_institutional_server,
                    self.uw_market_server,
                )
                if server is not None
            ]
            self.main_agent = create_main_agent(
                self.fmp_market_server,
                self.economic_server,
                alternatives_server=self.fmp_alternatives_server,
                tradeflow_server=self.fmp_tradeflow_server,
                model=agent_model,
                additional_servers=additional_servers,
            )
            logger.info(
                "Main agent MCP servers (FMP primary): %s",
                [server.__class__.__name__ for server in self.main_agent.mcp_servers],
            )
            self.comparable_companies = create_comparable_companies_agent(self.fmp_market_server, model=agent_model)
            # Document analyst gets BOTH FMP and SEC servers
            self.document_analyst = create_document_analyst_agent(
                document_server=self.fmp_document_server,
                sec_filing_server=self.sec_filing_server,
                quiver_server=self.quiver_server,
                model=agent_model
            )
            # Chart analyst gets FMP market server for technical data, UW for GEX levels and market data
            self.chart_analyst = create_chart_analyst_agent(
                self.fmp_market_server,
                uw_options_server=self.uw_options_server,
                uw_market_server=self.uw_market_server,
                quiver_server=self.quiver_server,
                model=agent_model
            )
            # Quant coding gets market, economic, alternatives, and all UW servers for comprehensive data access
            self.quant_coding = create_quant_coding_agent(
                self.fmp_market_server,
                self.economic_server,
                self.fmp_alternatives_server,
                uw_options_server=self.uw_options_server,
                uw_market_server=self.uw_market_server,
                uw_institutional_server=self.uw_institutional_server,
                quiver_server=self.quiver_server,
                model=agent_model,
            )
            self.options_coding = create_options_coding_agent(
                polygon_options_server=self.polygon_options_server,
                market_data_server=self.fmp_market_server,
                uw_options_server=self.uw_options_server,
                model=agent_model,
            )
            self.alternatives_coding = create_alternatives_coding_agent(
                polygon_server=self.polygon_crypto_server,
                alternatives_server=self.fmp_alternatives_server,
                model=agent_model,
            )
            self.institutional_activity = create_institutional_activity_agent(
                self.fmp_tradeflow_server,
                uw_institutional_server=self.uw_institutional_server,
                quiver_server=self.quiver_server,
                model=agent_model
            )
            self.dcf_agent = create_dcf_agent(self.fmp_market_server, self.economic_server, self.fmp_valuation_server, model=agent_model)
            # Funds products analyst gets FMP market, alternatives, and UW institutional servers for comprehensive fund data
            self.funds_products_analyst = create_funds_products_analyst(
                self.fmp_market_server,
                self.fmp_alternatives_server,
                uw_institutional_server=self.uw_institutional_server,
                model=agent_model
            )
            # Prediction markets analyst gets FMP market and prediction markets servers
            self.prediction_markets_analyst = create_prediction_markets_analyst(self.fmp_market_server, self.polymarket_server, model=agent_model)
            # Private markets agent gets TradeFlow, Economic, and Market servers
            self.private_markets = create_private_markets_agent(
                tradeflow_server=self.fmp_tradeflow_server,
                economic_server=self.economic_server,
                market_server=self.fmp_market_server,
                model=agent_model
            )
            # Portfolio semantic agent for financial knowledge graph discovery
            # TODO: Add Google Drive and OneDrive clients when integrations are set up
            self.portfolio_semantic_agent = create_data_semantic_agent(
                model=agent_model,
                google_drive_client=None,  # TODO: Wire up when Drive integration ready
                onedrive_client=None,  # TODO: Wire up when OneDrive integration ready
                polygon_api_key=os.getenv("POLYGON_API_KEY")  # Use env var for Polygon API key
            )
            # Structuring analyst gets market, economic, tradeflow, polygon options, and UW for derivatives pricing
            self.structuring_analyst = create_structuring_agent(
                market_server=self.fmp_market_server,
                economic_server=self.economic_server,
                tradeflow_server=self.fmp_tradeflow_server,
                polygon_options_server=self.polygon_options_server,
                uw_options_server=self.uw_options_server,
                model=agent_model,
            )
        else:
            self.risk_specialist = create_risk_specialist_agent(
                self.yfinance_server,
                self.economic_server,
                uw_options_server=self.uw_options_server,
                uw_market_server=self.uw_market_server,
                model=agent_model
            )
            additional_servers = [
                server
                for server in (
                    self.polygon_options_server,
                    self.polygon_crypto_server,
                    self.quiver_server,
                    self.uw_options_server,
                    self.uw_institutional_server,
                    self.uw_market_server,
                )
                if server is not None
            ]
            self.main_agent = create_main_agent(
                self.yfinance_server,
                self.economic_server,
                alternatives_server=None,  # FMP alternatives not available in fallback
                tradeflow_server=None,  # FMP tradeflow not available in fallback
                model=agent_model,
                additional_servers=additional_servers,
            )
            logger.info(
                "Main agent MCP servers (YFinance primary): %s",
                [server.__class__.__name__ for server in self.main_agent.mcp_servers],
            )
            # Comparable companies agent only works with FMP (not YFinance)
            self.comparable_companies = None
            # Document analyst with only SEC server (no FMP)
            if self.sec_filing_server:
                self.document_analyst = create_document_analyst_agent(
                    document_server=None,
                    sec_filing_server=self.sec_filing_server,
                    quiver_server=self.quiver_server,
                    model=agent_model
                )
            else:
                self.document_analyst = None
            # Chart analyst with YFinance fallback, UW for GEX levels and market data
            self.chart_analyst = create_chart_analyst_agent(
                self.yfinance_server,
                uw_options_server=self.uw_options_server,
                uw_market_server=self.uw_market_server,
                quiver_server=self.quiver_server,
                model=agent_model
            )
            # Quant coding with YFinance fallback and all UW servers
            self.quant_coding = create_quant_coding_agent(
                self.yfinance_server,
                self.economic_server,
                None,
                uw_options_server=self.uw_options_server,
                uw_market_server=self.uw_market_server,
                uw_institutional_server=self.uw_institutional_server,
                quiver_server=self.quiver_server,
                model=agent_model
            )
            self.options_coding = create_options_coding_agent(
                polygon_options_server=self.polygon_options_server,
                market_data_server=self.yfinance_server,
                uw_options_server=self.uw_options_server,
                model=agent_model,
            )
            # Alternatives agent still available via Polygon even without FMP
            self.alternatives_coding = create_alternatives_coding_agent(
                polygon_server=self.polygon_crypto_server,
                model=agent_model,
            )
            self.institutional_activity = create_institutional_activity_agent(
                tradeflow_server=None,
                uw_institutional_server=self.uw_institutional_server,
                quiver_server=self.quiver_server,
                model=agent_model,
            )
            # Private markets agent requires TradeFlow server (not available without FMP)
            self.private_markets = None
            # Funds products analyst with YFinance fallback (no alternatives server without FMP), UW institutional
            self.funds_products_analyst = create_funds_products_analyst(
                self.yfinance_server,
                None,
                uw_institutional_server=self.uw_institutional_server,
                model=agent_model
            )
            # DCF agent with YFinance fallback (no valuation server without FMP)
            self.dcf_agent = create_dcf_agent(self.yfinance_server, self.economic_server, None, model=agent_model)
            # Prediction markets analyst with YFinance fallback
            self.prediction_markets_analyst = create_prediction_markets_analyst(self.yfinance_server, self.polymarket_server, model=agent_model)
            # Portfolio semantic agent for financial knowledge graph discovery (same in both paths)
            self.portfolio_semantic_agent = create_data_semantic_agent(
                model=agent_model,
                google_drive_client=None,  # TODO: Wire up when Drive integration ready
                onedrive_client=None,  # TODO: Wire up when OneDrive integration ready
                polygon_api_key=os.getenv("POLYGON_API_KEY")
            )
            # Structuring analyst with YFinance fallback (no tradeflow server)
            self.structuring_analyst = create_structuring_agent(
                market_server=self.yfinance_server,
                economic_server=self.economic_server,
                tradeflow_server=None,  # Not available without FMP
                polygon_options_server=self.polygon_options_server,
                model=agent_model,
            )

        # Provider continuity caches (per session)
        self._session_provider_cache: Dict[str, str] = {}
        self._session_compaction_cache: Dict[str, Dict[str, Any]] = {}
        self._session_provider_messages: Dict[str, List[Dict[str, Any]]] = {}

        # Note: Handoffs are handled by the supervisor pattern in LangGraph,
        # not by the agents themselves. The agents don't need handoff configuration.

        # NOTE: Removed bidirectional handoff - it was causing Risk Specialist to hand back
        # too early before displaying calculation results. The supervisor pattern handles
        # routing back to generalist automatically after Risk Specialist completes.

        # Create the LangGraph with supervisor pattern
        # Use separate database for LangGraph state (async) vs OpenAI sessions (sync)
        try:
            from pathlib import Path
            Path(app_config.langgraph_db_path).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Failed to ensure LangGraph DB directory: %s", e)

        from os.path import abspath
        self.db_path = abspath(app_config.langgraph_db_path)

        # Initialize without compiling the graph; compile once and reuse
        self._compiled_graph = None
        self._checkpointer: Optional[AsyncSqliteSaver] = None
        self._checkpointer_cm = None
        self._compile_lock = asyncio.Lock()

        # Debug: log MCP servers attached to agents
        try:
            def _count_mcp(agent_obj):
                return len(getattr(agent_obj, 'mcp_servers', []) or [])
            logger.info(
                f"LangGraph orchestrator initialized with {router_model} router; "
                f"agents MCP counts - main={_count_mcp(self.main_agent)}, "
                f"risk={_count_mcp(self.risk_specialist)}, doc={_count_mcp(self.document_analyst)}"
            )
        except Exception:
            logger.info(f"LangGraph orchestrator initialized with {router_model} router")

    def get_last_provider(self, session_id: str) -> Optional[str]:
        """Return the provider used on the most recent completed run for a session."""
        return self._session_provider_cache.get(session_id)

    def pop_last_compaction_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve and clear compaction metadata for the most recent run."""
        return self._session_compaction_cache.pop(session_id, None)

    def _record_run_metadata(
        self,
        session_id: str,
        final_state: Dict[str, Any],
        fallback_model: Optional[str],
    ) -> None:
        """Persist provider continuity and compaction metadata for a session."""
        provider = final_state.get("last_provider")
        if not provider and fallback_model:
            provider = get_provider_from_model(fallback_model)
        if provider:
            self._session_provider_cache[session_id] = provider

        if final_state.get("_compaction_applied"):
            self._session_compaction_cache[session_id] = {
                "tokens": int(final_state.get("_compaction_tokens", 0)),
                "from_provider": final_state.get("_compaction_from_provider"),
                "to_provider": final_state.get("_compaction_to_provider"),
                "original_tokens": int(final_state.get("_compaction_original_tokens", 0)),
                "summary_tokens": int(final_state.get("_compaction_summary_tokens", 0)),
                "summary_model": final_state.get("_compaction_summary_model"),
                "summary_used": bool(final_state.get("_compaction_summary_used", False)),
            }

        summary_text = final_state.get("_cross_provider_summary")
        if summary_text and session_id in self._session_compaction_cache:
            self._session_compaction_cache[session_id]["summary_preview"] = summary_text[:1000]

        raw_messages = final_state.get("messages") or []
        messages_tail: List[Dict[str, Any]] = []
        for msg in raw_messages:
            normalized = message_to_dict(msg)
            if normalized:
                messages_tail.append(normalized)
        if messages_tail:
            self._session_provider_messages[session_id] = messages_tail[-200:]
            logger.info(
                "[COMPACTION CACHE] session=%s provider=%s cached_messages=%s",
                session_id,
                provider,
                len(self._session_provider_messages[session_id]),
            )
        else:
            self._session_provider_messages.pop(session_id, None)
    
    async def connect_mcp_servers(self):
        """Connect all MCP servers to initialize their HTTP sessions."""
        try:
            if self.use_fmp:
                await self.fmp_market_server.connect()
                await self.fmp_document_server.connect()
                await self.fmp_valuation_server.connect()
                await self.fmp_alternatives_server.connect()
                await self.fmp_tradeflow_server.connect()
                logger.info("Connected FMP MCP servers")
            
            # Connect SEC Filing Server if available and enabled
            if self.sec_filing_server and hasattr(self.sec_filing_server, 'connect'):
                try:
                    await self.sec_filing_server.connect()
                    logger.info("Connected SEC Filing Server")
                except RuntimeError as e:
                    # Expected error when SEC vectors disabled or PostgreSQL unavailable
                    logger.info(f"SEC Filing Server not available: {e}")
                    # Remove the server from Document Analyst to prevent tool registration
                    if self.document_analyst and hasattr(self.document_analyst, 'mcp_servers'):
                        self.document_analyst.mcp_servers = [
                            s for s in self.document_analyst.mcp_servers 
                            if not isinstance(s, type(self.sec_filing_server))
                        ]
                        logger.info("Removed SEC Filing Server from Document Analyst")
                except Exception as e:
                    # Unexpected error - log but don't crash
                    logger.warning(f"Unexpected error connecting SEC Filing Server: {e}")
                    # Remove the server to prevent issues
                    if self.document_analyst and hasattr(self.document_analyst, 'mcp_servers'):
                        self.document_analyst.mcp_servers = [
                            s for s in self.document_analyst.mcp_servers 
                            if not isinstance(s, type(self.sec_filing_server))
                        ]
            
            # YFinance and Economic servers don't need connection
            # but we can call connect() anyway for consistency
            if hasattr(self.yfinance_server, 'connect'):
                await self.yfinance_server.connect()
            if hasattr(self.economic_server, 'connect'):
                await self.economic_server.connect()

            if self.polygon_options_server and hasattr(self.polygon_options_server, 'connect'):
                await self.polygon_options_server.connect()
            if self.polygon_crypto_server and hasattr(self.polygon_crypto_server, 'connect'):
                await self.polygon_crypto_server.connect()
            if self.polymarket_server and hasattr(self.polymarket_server, 'connect'):
                await self.polymarket_server.connect()
            
            # Connect Unusual Whales servers
            if self.uw_options_server and hasattr(self.uw_options_server, 'connect'):
                await self.uw_options_server.connect()
            if self.uw_institutional_server and hasattr(self.uw_institutional_server, 'connect'):
                await self.uw_institutional_server.connect()
            if self.uw_market_server and hasattr(self.uw_market_server, 'connect'):
                await self.uw_market_server.connect()
                
            logger.info("All MCP servers connected")
        except Exception as e:
            logger.warning(f"MCP server connection warning: {e}")
            # Don't fail startup if connection fails - servers can lazy-init

    def _create_router(self, router_model: str):
        """Create router based on model configuration"""

        # Ensure router_model is not None and has a default
        if not router_model:
            router_model = "gpt-5-nano"
            logger.warning("Router model was None/empty, defaulting to gpt-5-nano")

        # Configure router based on model type
        if "gpt-5" in router_model.lower():
            # GPT-5 models use reasoning parameter with Responses API
            router_llm = ChatOpenAI(
                model=router_model,
                output_version="responses/v1",  # Use Responses API for GPT-5
                reasoning={"effort": "minimal"}  # Fast routing without extensive reasoning
            )
            logger.info(f"Using {router_model} for routing with minimal reasoning effort")
        elif "gpt-4.1" in router_model.lower():
            # GPT-4.1 models - standard ChatOpenAI, low temperature for consistency
            router_llm = ChatOpenAI(
                model=router_model, 
                temperature=0.1  # Lower temperature for more consistent routing
            )
            logger.info(f"Using {router_model} for routing with temperature=0.1")
        else:
            # Other models (gpt-4o, gpt-3.5, etc)
            router_llm = ChatOpenAI(model=router_model, temperature=0.3)
            logger.info(f"Using {router_model} for routing with temperature=0.3")

        return router_llm.with_structured_output(RouterDecision)

    def _create_graph(self) -> StateGraph:
        """Create the 8-node LangGraph with all specialized agents"""

        # Define the graph
        workflow = StateGraph(ConversationState)

        # Add nodes using wrapper methods that call imported functions
        workflow.add_node("supervisor", self._supervisor_node_wrapper)
        workflow.add_node("generalist", self._generalist_node_wrapper)
        workflow.add_node("risk_specialist", self._risk_specialist_node_wrapper)
        workflow.add_node("document_analyst", self._document_analyst_node_wrapper)
        workflow.add_node("comparable_companies", self._comparable_companies_node_wrapper)
        workflow.add_node("quant_coding", self._quant_coding_node_wrapper)
        workflow.add_node("structuring_analyst", self._structuring_analyst_node_wrapper)
        workflow.add_node("options_coding", self._options_coding_node_wrapper)
        workflow.add_node("alternatives_coding", self._alternatives_coding_node_wrapper)
        workflow.add_node("institutional_activity", self._institutional_activity_node_wrapper)
        workflow.add_node("chart_analyst", self._chart_analyst_node_wrapper)
        workflow.add_node("dcf_agent", self._dcf_agent_node_wrapper)
        workflow.add_node("funds_products_analyst", self._funds_products_analyst_node_wrapper)
        workflow.add_node("prediction_markets_analyst", self._prediction_markets_analyst_node_wrapper)
        workflow.add_node("private_markets", self._private_markets_node_wrapper)
        workflow.add_node("portfolio_semantic_agent", self._portfolio_semantic_agent_node_wrapper)

        # Set entry point
        workflow.set_entry_point("supervisor")

        # Supervisor routes to agents or ends
        workflow.add_conditional_edges(
            "supervisor",
            self._supervisor_routing,
            {
                "generalist": "generalist",
                "risk_specialist": "risk_specialist",
                "document_analyst": "document_analyst",
                "comparable_companies": "comparable_companies",
                "quant_coding": "quant_coding",
                "structuring_analyst": "structuring_analyst",
                "options_coding": "options_coding",
                "alternatives_coding": "alternatives_coding",
                "institutional_activity": "institutional_activity",
                "chart_analyst": "chart_analyst",
                "dcf_agent": "dcf_agent",
                "funds_products_analyst": "funds_products_analyst",
                "prediction_markets_analyst": "prediction_markets_analyst",
                "private_markets": "private_markets",
                "portfolio_semantic_agent": "portfolio_semantic_agent",
                "end": END
            }
        )

        # Define routing function for agent completion
        def create_agent_router(agent_name: str):
            """Create a routing function for a specific agent"""
            def agent_should_continue(state: ConversationState) -> str:
                """Determine if we should continue to supervisor or end after agent response"""
                # ✅ CHECK CANCELLATION: Stop multi-agent loop if cancelled
                from core.utils.context_utils import get_cancel_event
                cancel_event = get_cancel_event()
                if cancel_event and cancel_event.is_set():
                    logger.info("[CANCEL] %s routing cancelled - stopping multi-agent loop", agent_name)
                    return "end"

                # Terminal agents that complete the conversation
                terminal_agents = {
                    "generalist",
                    "document_analyst",
                    "comparable_companies",
                    "quant_coding",
                    "structuring_analyst",
                    "options_coding",
                    "alternatives_coding",
                    "institutional_activity",
                    "chart_analyst",
                    "dcf_agent",
                    "funds_products_analyst",
                    "prediction_markets_analyst",
                    "private_markets",
                    "portfolio_semantic_agent",
                }

                # If deep analysis mode is enabled, never terminate early - always go back to supervisor
                if state.get("deep_analysis_mode"):
                    hop_limit = state.get("deep_analysis_hop_limit") or self.deep_analysis_max_hops
                    hop_count = int(state.get("multi_agent_hops", 0) or 0)
                    if hop_count >= hop_limit:
                        logger.info(
                            "[MULTI-AGENT] %s reached hop limit (%s/%s); disabling deep_analysis_mode",
                            agent_name,
                            hop_count,
                            hop_limit,
                        )
                        state["deep_analysis_mode"] = False
                    else:
                        logger.info(
                            "[MULTI-AGENT] %s continuing collaborative loop (%s/%s)",
                            agent_name,
                            hop_count,
                            hop_limit,
                        )
                        return "supervisor"  # Continue collaborative loop until cap

                # If this is a terminal agent and it has responded without requesting handoff
                if agent_name in terminal_agents and state.get("last_agent_response") and not state.get("next_agent"):
                    logger.info(f"[MULTI-AGENT] {agent_name} ending conversation (terminal agent, deep_analysis_mode=False)")
                    return "end"  # Terminal agents end directly

                # Non-terminal agents (like risk_specialist) or agents requesting handoff continue to supervisor
                return "supervisor"
            return agent_should_continue

        # Use conditional edges instead of hardcoded edges
        workflow.add_conditional_edges(
            "generalist",
            create_agent_router("generalist"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "risk_specialist", 
            create_agent_router("risk_specialist"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "document_analyst",
            create_agent_router("document_analyst"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "comparable_companies",
            create_agent_router("comparable_companies"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "quant_coding",
            create_agent_router("quant_coding"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "structuring_analyst",
            create_agent_router("structuring_analyst"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "options_coding",
            create_agent_router("options_coding"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "alternatives_coding",
            create_agent_router("alternatives_coding"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "institutional_activity",
            create_agent_router("institutional_activity"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "chart_analyst",
            create_agent_router("chart_analyst"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "dcf_agent",
            create_agent_router("dcf_agent"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "funds_products_analyst",
            create_agent_router("funds_products_analyst"),
            {
                "supervisor": "supervisor",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "prediction_markets_analyst",
            create_agent_router("prediction_markets_analyst"),
            {
                "supervisor": "supervisor",
                "end": END,
            },
        )
        workflow.add_conditional_edges(
            "private_markets",
            create_agent_router("private_markets"),
            {
                "supervisor": "supervisor",
                "end": END,
            },
        )
        workflow.add_conditional_edges(
            "portfolio_semantic_agent",
            create_agent_router("portfolio_semantic_agent"),
            {
                "supervisor": "supervisor",
                "end": END,
            },
        )

        # Return uncompiled workflow; compile later with optional checkpointer
        return workflow

    async def _supervisor_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported supervisor_node function"""
        return await supervisor_node(state, self.structured_router)

    def _supervisor_routing(self, state: ConversationState) -> Literal["generalist", "risk_specialist", "document_analyst", "comparable_companies", "quant_coding", "structuring_analyst", "options_coding", "alternatives_coding", "institutional_activity", "chart_analyst", "dcf_agent", "funds_products_analyst", "prediction_markets_analyst", "private_markets", "portfolio_semantic_agent", "end"]:
        """Wrapper to call imported supervisor_routing function"""
        return supervisor_routing(state)

    async def _generalist_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported generalist_node function"""
        return await generalist_node(state, self.main_agent, execute_with_retry)

    async def _risk_specialist_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported risk_specialist_node function"""
        return await risk_specialist_node(state, self.risk_specialist, execute_with_retry)
    
    async def _document_analyst_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported document_analyst_node function"""
        from core.ai.langgraph_nodes import document_analyst_node
        
        # Set session context on SEC Filing Server before agent execution
        # ALWAYS set context if we have EITHER session_id OR user_id (was AND before - that was wrong)
        if self.sec_filing_server and hasattr(self.sec_filing_server, 'set_session_context'):
            session_id = state.get("session_id")
            user_id = state.get("user_id")
            try:
                if session_id or user_id:
                    self.sec_filing_server.set_session_context(session_id, user_id)
                    logger.info(
                        f"[SEC] Context set: session={str(session_id)[:8] if session_id else 'None'}..., "
                        f"user={str(user_id)[:8] if user_id else 'None'}..."
                    )
                else:
                    logger.warning("[SEC] No session context available (both session_id and user_id are None)")
            except Exception as e:
                logger.warning(f"[SEC] Failed to set session context: {e}")
        
        return await document_analyst_node(state, self.document_analyst, execute_with_retry)
    
    async def _comparable_companies_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported comparable_companies_node function"""
        from core.ai.langgraph_nodes import comparable_companies_node
        return await comparable_companies_node(state, self.comparable_companies, execute_with_retry)

    async def _quant_coding_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported quant_coding_node function"""
        from core.ai.langgraph_nodes import quant_coding_node
        return await quant_coding_node(state, self.quant_coding, execute_with_retry)

    async def _structuring_analyst_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported structuring_analyst_node function"""
        from core.ai.langgraph_nodes import structuring_analyst_node
        return await structuring_analyst_node(state, self.structuring_analyst, execute_with_retry)

    async def _options_coding_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported options_coding_node function"""
        from core.ai.langgraph_nodes import options_coding_node
        return await options_coding_node(state, self.options_coding, execute_with_retry)

    async def _alternatives_coding_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported alternatives_coding_node function"""
        from core.ai.langgraph_nodes import alternatives_coding_node
        return await alternatives_coding_node(state, self.alternatives_coding, execute_with_retry)

    async def _institutional_activity_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported institutional_activity_node function"""
        from core.ai.langgraph_nodes import institutional_activity_node
        return await institutional_activity_node(state, self.institutional_activity, execute_with_retry)

    async def _chart_analyst_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported chart_analyst_node function"""
        return await chart_analyst_node(state, self.chart_analyst, execute_with_retry)

    async def _dcf_agent_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported dcf_agent_node function"""
        from core.ai.langgraph_nodes import dcf_agent_node
        return await dcf_agent_node(state, self.dcf_agent, execute_with_retry)

    async def _funds_products_analyst_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported funds_products_analyst_node function"""
        from core.ai.langgraph_nodes import funds_products_analyst_node
        return await funds_products_analyst_node(state, self.funds_products_analyst, execute_with_retry)

    async def _prediction_markets_analyst_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported prediction_markets_analyst_node function"""
        if not self.prediction_markets_analyst:
            logger.warning("Prediction markets analyst unavailable, falling back to generalist")
            state["next_agent"] = "generalist"
            state["should_continue"] = True
            state["last_agent_response"] = (
                "Prediction markets analysis is not currently available. "
                "Handing the request back to the supervisor."
            )
            state["messages"].append(
                {
                    "role": "assistant",
                    "content": state["last_agent_response"],
                    "agent": "prediction_markets_analyst",
                    "provider": state.get("last_provider"),
                    "model": state.get("selected_model"),
                }
            )
            return state

        return await prediction_markets_analyst_node(
            state,
            self.prediction_markets_analyst,
            execute_with_retry,
        )

    async def _prediction_markets_analyst_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported prediction_markets_analyst_node function"""
        return await prediction_markets_analyst_node(state, self.prediction_markets_analyst, execute_with_retry)

    async def _portfolio_semantic_agent_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported portfolio_semantic_agent_node function"""
        from core.ai.langgraph_nodes import generic_agent_node
        return await generic_agent_node(state, self.portfolio_semantic_agent, execute_with_retry, "portfolio_semantic_agent")

    async def _private_markets_node_wrapper(self, state: ConversationState) -> ConversationState:
        """Wrapper to call imported private_markets_node function"""
        if not self.private_markets:
            logger.warning("Private markets agent unavailable (requires FMP TradeFlow), falling back to generalist")
            state["next_agent"] = "generalist"
            state["should_continue"] = True
            state["last_agent_response"] = (
                "Private markets research requires premium data access. "
                "Handing the request back to the supervisor."
            )
            state["messages"].append(
                {
                    "role": "assistant",
                    "content": state["last_agent_response"],
                    "agent": "private_markets",
                    "provider": state.get("last_provider"),
                    "model": state.get("selected_model"),
                }
            )
            return state

        from core.ai.langgraph_nodes import private_markets_node
        return await private_markets_node(
            state,
            self.private_markets,
            execute_with_retry,
        )

    async def ensure_compiled(self) -> None:
        """Compile the LangGraph once with a long-lived checkpointer (reuse per request)."""
        if self._compiled_graph is not None and self._checkpointer is not None:
            return
        async with self._compile_lock:
            if self._compiled_graph is not None and self._checkpointer is not None:
                return
            # Open a long-lived async checkpointer via context manager and keep the CM for shutdown
            if self._checkpointer_cm is None:
                self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(self.db_path)
                self._checkpointer = await self._checkpointer_cm.__aenter__()
            # Compile once
            workflow = self._create_graph()
            self._compiled_graph = workflow.compile(checkpointer=self._checkpointer)
            logger.info("LangGraph compiled with persistent AsyncSqliteSaver")

    async def close(self) -> None:
        """Close long-lived checkpointer and cleanup MCP servers on shutdown."""
        # Close checkpointer
        if self._checkpointer_cm is not None:
            try:
                await self._checkpointer_cm.__aexit__(None, None, None)
            finally:
                self._checkpointer_cm = None
                self._checkpointer = None
                self._compiled_graph = None

        # Cleanup MCP servers (close aiohttp sessions)
        mcp_servers = [
            ('fmp_market_server', self.fmp_market_server),
            ('fmp_document_server', self.fmp_document_server),
            ('fmp_valuation_server', self.fmp_valuation_server),
            ('fmp_alternatives_server', self.fmp_alternatives_server),
            ('fmp_tradeflow_server', self.fmp_tradeflow_server),
            ('yfinance_server', self.yfinance_server),
            ('economic_server', self.economic_server),
            ('sec_filing_server', self.sec_filing_server),
            ('polygon_options_server', self.polygon_options_server),
            ('polygon_crypto_server', self.polygon_crypto_server),
            ('polymarket_server', self.polymarket_server),
            ('quiver_server', self.quiver_server),
        ]

        for name, server in mcp_servers:
            if server and hasattr(server, 'cleanup'):
                try:
                    await server.cleanup()
                    logger.info(f"Cleaned up {name}")
                except Exception as e:
                    logger.warning(f"Error cleaning up {name}: {e}")

    # Removed _recompile_graph(): recompile during runtime caused threading conflicts.

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        agent_mode: Optional[str] = None,  # 'auto', 'risk', 'web', 'market', 'filings'
        workflow_context: Optional[Dict[str, Any]] = None,  # File attachments and other context
        selected_model: Optional[str] = None,  # Model selection from UI (gpt-5.4, gpt-5.1)
        deep_analysis_mode: Optional[bool] = None,  # Deep analysis mode flag
        prioritized_tools: Optional[List[str]] = None,  # Tools to prioritize/force usage
        cancel_event: Optional[asyncio.Event] = None,  # Cooperative cancellation (simulated stream)
    ) -> str:
        """
        Process a query using LangGraph orchestration with OpenAI agents.

        Args:
            query: The user's query
            session_id: Optional session ID for state management
            portfolio_context: Optional portfolio data from frontend (tickers, weights, value)

        This replaces the direct agent execution to fix handback issues.
        """

        if not session_id:
            # Generate UUID-based session ID instead of timestamp (no hardcoding)
            import uuid
            session_id = str(uuid.uuid4())

        # ✅ CHECK CANCELLATION: Stop immediately if already cancelled (prevents fallback re-invocation)
        if cancel_event and cancel_event.is_set():
            logger.info("[CANCEL] process_query skipped - request already cancelled for session %s", session_id)
            raise asyncio.CancelledError("Request cancelled before processing started")

        # Initialize messages with merged history (frontend-provided + backend store), then append current query
        normalized_messages: List[Dict[str, str]] = []

        async def _merge_histories(frontend_hist: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
            merged: List[Dict[str, str]] = []
            # 1) Load recent backend history for this session_id
            try:
                from core.config import config as app_config
                db_path = app_config.conversation_db_path
                async with aiosqlite.connect(db_path) as db:
                    async with db.execute(
                        """
                        SELECT role, content
                        FROM messages
                        WHERE session_id = ?
                        ORDER BY datetime(created_at) ASC
                        LIMIT 200
                        """,
                        (session_id,),
                    ) as cursor:
                        rows = await cursor.fetchall()
                        for role, content in rows:
                            if role in ("user", "assistant") and content:
                                merged.append({"role": role, "content": str(content)})
            except Exception as e:
                logger.warning(f"[ORCH] Failed to load backend history: {e}")

            # 2) Append any frontend-provided short history that isn't already present (by content)
            if frontend_hist and isinstance(frontend_hist, list):
                seen = set((m.get("role"), m.get("content")) for m in merged if isinstance(m, dict))
                for item in frontend_hist:
                    # Skip None or non-dict items to prevent crashes
                    if not isinstance(item, dict):
                        logger.warning(f"Skipping non-dict history item: {type(item)}")
                        continue
                    r = str(item.get("role", "user"))
                    c = str(item.get("content", ""))
                    if c and (r, c) not in seen:
                        merged.append({"role": r, "content": c})
            return merged

        normalized_messages = await _merge_histories(history)
        
        # Implement sliding window to prevent token explosion
        MAX_MESSAGES = 20  # Keep last 20 messages
        if len(normalized_messages) > MAX_MESSAGES:
            # Summarize older messages if needed (for now, just keep recent ones)
            logger.info(f"Trimming history from {len(normalized_messages)} to {MAX_MESSAGES} messages")
            normalized_messages = normalized_messages[-MAX_MESSAGES:]
        
        logger.info(f"[DEBUG ORCHESTRATOR] Using merged history of {len(normalized_messages)} messages for session {session_id}")

        # Process commands (e.g., /search from frontend Perplexity flag)
        processed_query = query
        force_web_search = False
        if query.startswith("/search "):
            # Extract the actual query and set web search flag
            processed_query = query[8:]  # Remove "/search " prefix
            force_web_search = True
            logger.info(f"[COMMAND] Detected /search command, forcing web search for: {processed_query}")

        # Only append current query if it's not already in history
        current_msg = {"role": "user", "content": processed_query}
        if not normalized_messages or normalized_messages[-1].get("content") != processed_query:
            normalized_messages.append(current_msg)

        # Initialize state with enhanced portfolio management
        logger.info(f"[DEBUG ORCHESTRATOR] Creating initial state with {len(normalized_messages)} messages")

        # Extract file_ids from workflow_context if present
        file_ids = None
        drive_context_payload: Optional[Dict[str, Any]] = None
        drive_file_ids = None
        if workflow_context and isinstance(workflow_context, dict):
            file_ids = workflow_context.get("file_ids")
            if file_ids:
                logger.info(f"Found {len(file_ids)} file attachments in workflow context")
            drive_context_payload = workflow_context.get("drive")
            if isinstance(drive_context_payload, dict):
                drive_file_ids = drive_context_payload.get("file_ids")
                if drive_file_ids:
                    logger.info(f"Found {len(drive_file_ids)} Google Drive files in context")

        # Set search provider selection (separate from agent model)
        logger.info(f"[DEBUG MODEL] selected_model parameter: {selected_model} (type: {type(selected_model)})")
        if selected_model:
            import os
            logger.info(f"[DEBUG MODEL] Checking if '{selected_model}' is in ['perplexity-sonar', 'perplexity-sonar-pro']")
            model_str = str(selected_model)
            model_lower = model_str.lower()
            if selected_model in ['perplexity-sonar', 'perplexity-sonar-pro']:
                logger.info(f"[DEBUG MODEL] MATCH! Setting SEARCH_PROVIDER to 'perplexity'")
                # Set search provider for web_search tool
                os.environ["SEARCH_PROVIDER"] = "perplexity"
                # Set the specific Perplexity model variant
                if selected_model == 'perplexity-sonar':
                    os.environ["PERPLEXITY_MODEL"] = "sonar"
                    logger.info("Perplexity Sonar selected - forcing web search mode with Perplexity Sonar")
                else:  # perplexity-sonar-pro
                    os.environ["PERPLEXITY_MODEL"] = "sonar-pro"
                    logger.info("Perplexity Sonar Pro selected - forcing web search mode with Perplexity Sonar Pro")
                # Agents always use gpt-5.1 (Perplexity is only for search)
                # Don't set AGENT_MODEL - keep it as default gpt-5.1
                # Also force web search mode
                force_web_search = True
            elif (
                isinstance(selected_model, str)
                and (
                    selected_model.startswith('claude')
                    or 'anthropic/' in selected_model
                    or 'litellm/anthropic/' in selected_model
                )
            ):
                os.environ["SEARCH_PROVIDER"] = selected_model
                logger.info("[DEBUG MODEL] Anthropic/Claude selected — configured SEARCH_PROVIDER for web search")
            elif isinstance(selected_model, str) and ('gemini' in model_lower or 'google' in model_lower):
                os.environ["SEARCH_PROVIDER"] = selected_model
                logger.info("[DEBUG MODEL] Gemini model selected — configured SEARCH_PROVIDER for web search")
            elif isinstance(selected_model, str) and 'deepseek' in model_lower:
                os.environ.pop("SEARCH_PROVIDER", None)
                logger.info("[DEBUG MODEL] DeepSeek model selected — web search disabled (no native support)")
            elif isinstance(selected_model, str) and ('bedrock' in model_lower or 'llama4' in model_lower):
                os.environ.pop("SEARCH_PROVIDER", None)
                logger.info("[DEBUG MODEL] Bedrock model selected — web search fallback to Perplexity")
            elif isinstance(selected_model, str) and ('/xai/' in selected_model or 'grok' in model_lower):
                os.environ["SEARCH_PROVIDER"] = selected_model
                logger.info("[DEBUG MODEL] xAI/Grok model selected — configured SEARCH_PROVIDER for web search")
            elif isinstance(selected_model, str) and ('moonshot' in model_lower or 'kimi' in model_lower):
                os.environ.pop("SEARCH_PROVIDER", None)
                logger.info("[DEBUG MODEL] Moonshot/Kimi model selected — web search fallback to Perplexity")
            elif isinstance(selected_model, str) and ('dashscope' in model_lower or 'qwen' in model_lower):
                os.environ.pop("SEARCH_PROVIDER", None)
                logger.info("[DEBUG MODEL] Qwen/DashScope model selected — web search fallback to Perplexity")
            elif isinstance(selected_model, str) and ('/zai/' in selected_model or 'zai/' in model_lower or 'glm' in model_lower):
                os.environ.pop("SEARCH_PROVIDER", None)
                logger.info("[DEBUG MODEL] Z.AI/GLM model selected — web search fallback to Perplexity")
            else:
                logger.info(f"[DEBUG MODEL] NO MATCH - falling to else branch for model: {selected_model}")
                os.environ["SEARCH_PROVIDER"] = selected_model
                os.environ["AGENT_MODEL"] = selected_model
                logger.info(f"Set SEARCH_PROVIDER and AGENT_MODEL to {selected_model}")
        else:
            logger.info(f"[DEBUG MODEL] selected_model is None/empty - using default")

        # Default deep_analysis_mode first, then log the actual value
        deep_analysis_mode = deep_analysis_mode if deep_analysis_mode is not None else False
        logger.info(f"[MULTI-AGENT] Deep analysis mode: {deep_analysis_mode}")

        # Load memory notes for context injection (Memory Notebook feature)
        memory_notes: List[Dict[str, Any]] = []
        memory_chunks: List[Dict[str, Any]] = []
        if user_id and session_id:
            try:
                from core.ai.utils.context_manager import _load_memory_notes, _retrieve_relevant_chunks
                memory_notes = await _load_memory_notes(session_id, user_id)
                if memory_notes:
                    logger.info(f"[MEMORY] Loaded {len(memory_notes)} memory notes for session {session_id}")
                    # Filter out chunked notes (they'll be retrieved via semantic search)
                    non_chunked = [n for n in memory_notes if not n.get("is_chunked", False)]
                    memory_notes = non_chunked
                    # Retrieve relevant chunks using the current query
                    memory_chunks = await _retrieve_relevant_chunks(
                        session_id=session_id,
                        user_id=user_id,
                        query=processed_query,
                        top_k=5
                    )
                    if memory_chunks:
                        logger.info(f"[MEMORY] Retrieved {len(memory_chunks)} relevant chunks for query")
            except Exception as e:
                logger.warning(f"[MEMORY] Failed to load memory notes: {e}")

        from core.agents.binomial_hash import init_binomial_hash
        init_binomial_hash()

        initial_state = ConversationState(
            messages=normalized_messages,
            current_user_query=processed_query,
            last_agent_response="",
            session_id=session_id,
            user_id=user_id,
            should_continue=True,
            next_agent=None,
            calculation_results=None,
            handback_pending=False,
            agent_mode=agent_mode or 'auto',  # Default to 'auto' if not specified
            deep_analysis_mode=deep_analysis_mode,  # Already defaulted above
            force_web_search=force_web_search,  # Pass the /search command flag
            selected_model=selected_model,  # Pass selected model for agent nodes
            prioritized_tools=prioritized_tools,  # Tools to prioritize/force usage
            portfolio_state=portfolio_context,  # Set portfolio context from parameter
            risk_results=None,
            optimization_suggestions=None,
            workflow_context=workflow_context,  # Set workflow context with file attachments
            file_ids=file_ids,  # Uploaded file IDs
            drive_context=drive_context_payload,
            drive_file_ids=drive_file_ids,
            last_provider=self._session_provider_cache.get(session_id),
            _provider_messages=self._session_provider_messages.get(session_id),
            multi_agent_hops=0,
            deep_analysis_hop_limit=self.deep_analysis_max_hops,
            errors=[],
            _memory_notes=memory_notes,  # Memory Notebook notes
            _memory_chunks=memory_chunks,  # Retrieved memory chunks
        )
        
        logger.info(
            "[PROVIDER CONTINUITY] session=%s last_provider=%s current_model=%s",
            session_id,
            self._session_provider_cache.get(session_id),
            selected_model,
        )

        # Use portfolio context from frontend if provided
        # Otherwise let the agents extract context naturally from the query
        if portfolio_context:
            initial_state["portfolio_state"] = portfolio_context
            logger.info(f"Initialized with portfolio context from frontend: {portfolio_context}")
        else:
            # Let agents handle context extraction through natural language understanding
            # No hardcoded regex patterns - agents are better at NLU
            logger.info("No portfolio context provided, agents will extract from query")

        try:
            # Ensure compiled graph is ready (no per-request compilation)
            await self.ensure_compiled()
            logger.info("Starting LangGraph execution with compiled graph")

            # Set user context ONCE before retry loop (fixes "No user context available")
            user_token = None
            drive_token = None
            cancel_token = None
            if user_id:
                user_token = user_context.set(user_id)
                logger.debug(f"Set user context for user_id: {user_id}")
            if drive_context_payload:
                drive_token = set_drive_context(drive_context_payload)
                logger.debug("Drive context set for current request")
            if cancel_event:
                cancel_token = set_cancel_event(cancel_event)
                logger.debug(f"Set cancel event for session: {session_id}")

            try:
                # Use a unique thread_id per request to avoid LangGraph checkpoint collisions
                import uuid
                final_state = None
                last_error: Optional[Exception] = None
                run_task: Optional[asyncio.Task] = None
                # Retry a small, bounded number of times on transient errors without recompiling
                for attempt in range(2):
                    thread_id = f"{session_id}_{uuid.uuid4().hex}"
                    # Use configured recursion limit instead of hardcoded 10
                    from core.config import get_config
                    max_recursion = get_config().max_graph_recursion
                    graph_config = {
                        "recursion_limit": max_recursion,
                        "configurable": {"thread_id": thread_id},
                    }

                    try:
                        run_task = asyncio.create_task(
                            self._compiled_graph.ainvoke(initial_state, config=graph_config)
                        )
                        if session_id:
                            async with self._runs_lock:
                                existing_task = self._active_runs.get(session_id)
                                if existing_task and not existing_task.done():
                                    logger.warning(
                                        "Cancelling existing run for session %s before starting new one",
                                        session_id,
                                    )
                                    existing_task.cancel()
                                self._active_runs[session_id] = run_task

                        final_state = await run_task
                        last_error = None
                        break
                    except asyncio.CancelledError:
                        logger.info("LangGraph execution cancelled for session %s", session_id)
                        raise
                    except Exception as e:
                        last_error = e
                        msg = str(e).lower()
                        transient = (
                            "threads can only be started once" in msg
                            or ("thread" in msg and "started" in msg)
                            or "connection closed" in msg
                            or "temporarily unavailable" in msg
                            or "timeout" in msg
                        )
                        if transient:
                            logger.warning(f"LangGraph transient error on attempt {attempt + 1}: {e}")
                            # Backoff before retrying with a fresh thread id
                            try:
                                await asyncio.sleep(0.5 * (attempt + 1))
                            except Exception:
                                pass
                            continue
                        else:
                            # Non-retryable error
                            raise
                    finally:
                        if session_id and run_task:
                            async with self._runs_lock:
                                stored = self._active_runs.get(session_id)
                                if stored is run_task:
                                    self._active_runs.pop(session_id, None)
                        run_task = None
            finally:
                # ALWAYS clean up user context token, even on exception
                if user_token is not None:
                    user_context.reset(user_token)
                    logger.debug(f"Reset user context for user_id: {user_id}")
                if drive_token is not None:
                    reset_drive_context(drive_token)
                if cancel_token is not None:
                    reset_cancel_event(cancel_token)

            if final_state is None and last_error is not None:
                # Exhausted retries; raise last error to trigger fallback path
                raise last_error

            # Extract final response - prioritize calculation results

            # Check if final_state is None (graph execution failed)
            if final_state is None:
                logger.error("Final state is None after graph execution")
                raise Exception("Graph execution failed - final state is None")

            self._record_run_metadata(session_id, final_state, selected_model)

            # First check if we have calculation results
            if final_state.get("calculation_results"):
                # Try to include charts/sources if they exist
                messages = final_state.get("messages", [])
                assistant_charts = []
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        if isinstance(msg.get("charts"), list) and msg["charts"]:
                            assistant_charts.extend(msg["charts"])
                
                # Deduplicate charts by ID to prevent duplicates
                charts_out = final_state.get("charts") or assistant_charts
                if charts_out:
                    seen_ids = set()
                    unique_charts = []
                    for chart in charts_out:
                        if isinstance(chart, dict) and chart.get("id"):
                            if chart["id"] not in seen_ids:
                                seen_ids.add(chart["id"])
                            unique_charts.append(chart)
                        else:
                            # Keep charts without IDs (shouldn't happen but defensive)
                            unique_charts.append(chart)
                    charts_out = unique_charts
                    charts_out, hydrated_full = self._hydrate_chart_handles(charts_out)
                
                sources_out = final_state.get("search_sources") or []

                # Extract code execution data if available (from quant_coding_node)
                code_execution_data = final_state.get("code_execution_data")
                errors = final_state.get("errors") or []
                full_charts = final_state.get("_full_charts") or []
                if charts_out and hydrated_full:
                    full_charts.extend(hydrated_full)

                logger.info(f"Returning calculation results with {len(charts_out)} unique charts")
                result = {"content": final_state["calculation_results"], "sources": sources_out, "charts": charts_out or []}
                if full_charts:
                    result["_full_charts"] = full_charts

                # Add code execution data if present
                if code_execution_data:
                    result["code_execution_data"] = code_execution_data
                    logger.info(f"[ORCHESTRATOR] Including code execution data: {len(code_execution_data.get('generated_files', []))} files, {len(code_execution_data.get('code_blocks', []))} code blocks")
                if errors:
                    result["errors"] = errors
                if self.startup_warnings:
                    result["warnings"] = self.startup_warnings

                return result

            # Otherwise extract from messages and include structured sources/charts if present
            messages = final_state.get("messages", [])

            # Handle both dict and LangChain message formats
            assistant_messages = []
            assistant_charts = []
            for msg in messages:
                if hasattr(msg, 'type') and msg.type == 'ai':
                    # LangChain AIMessage
                    assistant_messages.append(msg.content)
                elif isinstance(msg, dict) and msg.get("role") == "assistant":
                    # Dict format
                    assistant_messages.append(msg["content"])
                    if isinstance(msg.get("charts"), list) and msg["charts"]:
                        assistant_charts.extend(msg["charts"])
                elif hasattr(msg, 'content') and hasattr(msg, '__class__'):
                    # Check if it's an AI message by class name
                    if 'AI' in msg.__class__.__name__ or 'Assistant' in msg.__class__.__name__:
                        assistant_messages.append(msg.content)

            # Determine content string
            if assistant_messages:
                content_out = assistant_messages[-1]
            else:
                content_out = final_state.get("last_agent_response", "I couldn't process your request. Please try again.")

            # If generalist captured sources from a tool (e.g., web_search), return a dict including them
            sources_out = final_state.get("search_sources") or []
            charts_out = final_state.get("charts") or assistant_charts or []

            # Deduplicate charts by ID to prevent duplicates
            if charts_out:
                seen_ids = set()
                unique_charts = []
                for chart in charts_out:
                    if isinstance(chart, dict) and chart.get("id"):
                        if chart["id"] not in seen_ids:
                            seen_ids.add(chart["id"])
                            unique_charts.append(chart)
                    else:
                        # Keep charts without IDs (shouldn't happen but defensive)
                        unique_charts.append(chart)
                charts_out = unique_charts
                charts_out, hydrated_full = self._hydrate_chart_handles(charts_out)

            logger.info(f"[CHART DEBUG ORCH] Returning {len(charts_out)} unique chart references (deduped from {len(final_state.get('charts', []))} in state)")

            # Extract full charts for metadata storage (prevents context overflow)
            full_charts = final_state.get("_full_charts") or []
            if charts_out and hydrated_full:
                full_charts.extend(hydrated_full)
            if full_charts:
                logger.info(f"[ORCHESTRATOR] Found {len(full_charts)} full charts in _full_charts for metadata storage")

            # Extract code execution data if available (from quant_coding_node)
            code_execution_data = final_state.get("code_execution_data")
            errors = final_state.get("errors") or []

            # Debug: Check what's in final_state
            logger.info(f"[ORCHESTRATOR DEBUG] Final state keys: {list(final_state.keys())}")
            logger.info(f"[ORCHESTRATOR DEBUG] code_execution_data in state: {code_execution_data is not None}")

            # Always return a dict to preserve charts/sources shape
            result = {"content": content_out, "sources": sources_out, "charts": charts_out}

            # Add full charts to metadata (for database storage, separate from agent context)
            if full_charts:
                result["_full_charts"] = full_charts
                logger.info(f"[ORCHESTRATOR] Including {len(full_charts)} full charts in result metadata")

            # Add code execution data if present
            if code_execution_data:
                result["code_execution_data"] = code_execution_data
                logger.info(f"[ORCHESTRATOR] Including code execution data: {len(code_execution_data.get('generated_files', []))} files, {len(code_execution_data.get('code_blocks', []))} code blocks")
            if errors:
                result["errors"] = errors
            if self.startup_warnings:
                result["warnings"] = self.startup_warnings

            return result

        except asyncio.CancelledError:
            logger.info("[ORCHESTRATOR] process_query cancelled before completion")
            raise
        except Exception as e:
            logger.error(f"LangGraph execution error: {e}")

            # Check if this is a rate limit error and provide friendly message
            error_msg = str(e)
            is_rate_limit = (
                "quota" in error_msg.lower() and "exceeded" in error_msg.lower()
            ) or "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg

            if is_rate_limit:
                # Extract model name if available
                model_name = selected_model or "AI model"
                if "gemini" in error_msg.lower():
                    model_name = "Gemini"
                elif "claude" in error_msg.lower() or "anthropic" in error_msg.lower():
                    model_name = "Claude"
                elif "grok" in error_msg.lower() or "xai" in error_msg.lower():
                    model_name = "Grok"
                elif "bedrock" in error_msg.lower() or "llama" in error_msg.lower():
                    model_name = "Llama"
                elif "gpt" in error_msg.lower():
                    model_name = "GPT"

                # Parse retry time if available
                import re
                retry_match = re.search(r'retry in ([\d.]+)s', error_msg)
                retry_time = int(float(retry_match.group(1))) if retry_match else 10

                friendly_message = (
                    f"I've temporarily hit my usage limit for {model_name}. "
                    f"Please try again in about {retry_time} seconds, or select a different model "
                    f"from the model dropdown to continue immediately."
                )
                logger.warning(f"Rate limit hit, returning friendly message to user")
                return friendly_message

            # For non-rate-limit errors, try fallback
            try:
                # IMPORTANT: Use SQLiteSession in fallback to preserve context with provider-scoped IDs!
                from core.config import config as app_config
                provider = (
                    get_provider_from_model(selected_model)
                    if selected_model
                    else "openai"
                )
                if provider not in {"anthropic", "gemini", "bedrock", "xai"}:
                    provider = "openai"
                sdk_session_id = f"{session_id}::{provider}"
                fallback_session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)
                logger.info(f"Fallback: Using SQLiteSession with sdk_session_id: {sdk_session_id} (provider: {provider})")

                result = await execute_with_retry(
                    self.main_agent,
                    query,
                    fallback_session,
                    agent_name="orchestrator_fallback",
                    selected_model=selected_model,
                )
                return result.final_output if hasattr(result, "final_output") else str(result)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                # Check if fallback also hit rate limit
                fallback_msg = str(fallback_error)
                if "quota" in fallback_msg.lower() or "429" in fallback_msg or "RESOURCE_EXHAUSTED" in fallback_msg:
                    return (
                        "I'm experiencing high demand right now. "
                        "Please wait a moment and try again, or select a different model."
                    )
                return f"I encountered an error processing your request. Please try again in a moment."

    def _extract_portfolio_context(self, query: str) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: This method uses hardcoded regex patterns which violates our NO HARDCODING principle.

        Portfolio context should come from:
        1. Frontend UI (preferred) - user sets portfolio via UI controls
        2. Agent NLU (fallback) - agents extract context using natural language understanding

        This method is kept for backward compatibility but returns None to force proper context handling.
        """
        # Return None - let frontend or agents handle context properly
        return None

    def _hydrate_chart_handles(
        self, charts: Optional[List[Any]]
    ) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        Resolve lightweight chart handles into full Plotly payloads for UI delivery.

        Returns both hydrated chart objects (for streaming) and the full charts
        for metadata storage.
        """
        hydrated: List[Any] = []
        full: List[Dict[str, Any]] = []

        if not charts:
            return hydrated, full

        hits = 0
        misses = 0
        for chart in charts:
            if not isinstance(chart, dict):
                hydrated.append(chart)
                continue

            chart_copy = dict(chart)
            chart_id = chart_copy.get("chart_id") or chart_copy.get("id")
            stored = get_chart(str(chart_id)) if chart_id else None

            if stored and isinstance(stored, dict):
                full.append(stored)
                chart_copy.setdefault("id", stored.get("id"))
                chart_copy.setdefault("title", stored.get("title"))
                chart_copy.setdefault("alt_text", stored.get("alt_text"))
                chart_copy.setdefault("type", stored.get("type"))
                chart_copy.setdefault("metadata", stored.get("metadata"))
                chart_copy.setdefault("plotly", stored.get("plotly"))
                hits += 1
            else:
                misses += 1

            hydrated.append(chart_copy)

        if hits or misses:
            logger.info(
                "[CHART HYDRATE] Handles=%s hits=%s misses=%s",
                len(charts),
                hits,
                misses,
            )

        return hydrated, full

    async def process_query_stream(
        self,
        query: str,
        session_id: str,
        user_id: Optional[str] = None,
        portfolio_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        agent_mode: Optional[str] = None,
        workflow_context: Optional[Dict[str, Any]] = None,
        selected_model: Optional[str] = None,
        deep_analysis_mode: Optional[bool] = None,
        prioritized_tools: Optional[List[str]] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Any:
        """Stream responses using LangGraph orchestrator with native token streaming."""

        import uuid as _uuid

        if not session_id:
            session_id = str(_uuid.uuid4())

        # ✅ CHECK CANCELLATION: Stop immediately if already cancelled
        if cancel_event and cancel_event.is_set():
            logger.info("[CANCEL] process_query_stream skipped - request already cancelled for session %s", session_id)
            yield {"type": "cancelled"}
            return

        async def _merge_histories(frontend_hist: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
            merged: List[Dict[str, str]] = []
            try:
                from core.config import config as app_config
                db_path = app_config.conversation_db_path
                async with aiosqlite.connect(db_path) as db:
                    async with db.execute(
                        """
                        SELECT role, content
                        FROM messages
                        WHERE session_id = ?
                        ORDER BY datetime(created_at) ASC
                        LIMIT 200
                        """,
                        (session_id,),
                    ) as cursor:
                        rows = await cursor.fetchall()
                        for role, content in rows:
                            if role in ("user", "assistant") and content:
                                merged.append({"role": role, "content": str(content)})
            except Exception as e:
                logger.warning(f"[ORCH] Failed to load backend history: {e}")

            if frontend_hist and isinstance(frontend_hist, list):
                seen = set((m.get("role"), m.get("content")) for m in merged if isinstance(m, dict))
                for item in frontend_hist:
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role", "user"))
                    content = str(item.get("content", ""))
                    if content and (role, content) not in seen:
                        merged.append({"role": role, "content": content})
            return merged

        normalized_messages = await _merge_histories(history)
        MAX_MESSAGES = 20
        if len(normalized_messages) > MAX_MESSAGES:
            normalized_messages = normalized_messages[-MAX_MESSAGES:]

        processed_query = query
        force_web_search = False
        if query.startswith("/search "):
            processed_query = query[8:]
            force_web_search = True

        current_msg = {"role": "user", "content": processed_query}
        if not normalized_messages or normalized_messages[-1].get("content") != processed_query:
            normalized_messages.append(current_msg)

        file_ids = None
        drive_context_payload: Optional[Dict[str, Any]] = None
        drive_file_ids = None
        if workflow_context and isinstance(workflow_context, dict):
            file_ids = workflow_context.get("file_ids")
            drive_context_payload = workflow_context.get("drive")
            if isinstance(drive_context_payload, dict):
                drive_file_ids = drive_context_payload.get("file_ids")
        workflow_ctx = workflow_context if isinstance(workflow_context, dict) else None

        if selected_model:
            import os
            model_lower = str(selected_model).lower()
            if selected_model in ['perplexity-sonar', 'perplexity-sonar-pro']:
                os.environ["SEARCH_PROVIDER"] = "perplexity"
                os.environ["PERPLEXITY_MODEL"] = 'sonar' if selected_model == 'perplexity-sonar' else 'sonar-pro'
                force_web_search = True
            elif (
                selected_model.startswith('claude')
                or 'anthropic/' in selected_model
                or 'litellm/anthropic/' in selected_model
            ):
                os.environ["SEARCH_PROVIDER"] = selected_model
            elif '/xai/' in selected_model or 'grok' in model_lower:
                os.environ["SEARCH_PROVIDER"] = selected_model
            elif 'gemini' in model_lower or 'google' in model_lower:
                os.environ["SEARCH_PROVIDER"] = selected_model
            elif 'deepseek' in model_lower:
                os.environ.pop("SEARCH_PROVIDER", None)
            elif 'bedrock' in model_lower or 'llama4' in model_lower:
                os.environ.pop("SEARCH_PROVIDER", None)
            elif 'moonshot' in model_lower or 'kimi' in model_lower:
                os.environ.pop("SEARCH_PROVIDER", None)
            elif 'dashscope' in model_lower or 'qwen' in model_lower:
                os.environ.pop("SEARCH_PROVIDER", None)
            elif '/zai/' in selected_model or 'zai/' in model_lower or 'glm' in model_lower:
                os.environ.pop("SEARCH_PROVIDER", None)
            else:
                os.environ["SEARCH_PROVIDER"] = selected_model
                os.environ["AGENT_MODEL"] = selected_model

        deep_analysis_mode = deep_analysis_mode if deep_analysis_mode is not None else False

        from core.agents.binomial_hash import init_binomial_hash
        init_binomial_hash()

        initial_state = ConversationState(
            messages=normalized_messages,
            current_user_query=processed_query,
            last_agent_response="",
            session_id=session_id,
            user_id=user_id,
            should_continue=True,
            next_agent=None,
            calculation_results=None,
            handback_pending=False,
            agent_mode=agent_mode or 'auto',
            deep_analysis_mode=deep_analysis_mode,
            force_web_search=force_web_search,
            selected_model=selected_model,
            prioritized_tools=prioritized_tools,
            portfolio_state=portfolio_context,
            risk_results=None,
            optimization_suggestions=None,
            workflow_context=workflow_ctx,
            file_ids=file_ids,
            drive_context=drive_context_payload,
            drive_file_ids=drive_file_ids,
            last_provider=self._session_provider_cache.get(session_id),
            _provider_messages=self._session_provider_messages.get(session_id),
            errors=[],
        )

        logger.info(
            "[PROVIDER CONTINUITY] session=%s last_provider=%s current_model=%s",
            session_id,
            self._session_provider_cache.get(session_id),
            selected_model,
        )

        if portfolio_context:
            initial_state["portfolio_state"] = portfolio_context
            logger.info(f"[PORTFOLIO DEBUG ORCHESTRATOR] Set portfolio_state in initial_state: {portfolio_context}")
        else:
            logger.warning(f"[PORTFOLIO DEBUG ORCHESTRATOR] No portfolio_context provided to process_query_stream")

        token_queue: asyncio.Queue[Any] = asyncio.Queue()
        # NOTE: token_queue is NOT added to state to avoid msgpack serialization errors
        # Instead, it's set via context variables below (line 1627)

        sink_token = None
        user_token = None
        drive_token = None
        cancel_token = None
        final_state: Optional[Dict[str, Any]] = None
        streaming_error: Optional[Exception] = None

        if self.startup_warnings:
            for warn in self.startup_warnings:
                yield {"type": "status", "message": warn}

        try:
            await self.ensure_compiled()
            from core.config import get_config as _get_config
            cfg = _get_config()
            thread_id = f"{session_id}_{_uuid.uuid4().hex}"
            config_dict = {"recursion_limit": cfg.max_graph_recursion, "configurable": {"thread_id": thread_id}}

            # Set context variables (non-serializable objects that can't go in LangGraph state)
            sink_token = set_token_sink(token_queue)
            if cancel_event:
                cancel_token = set_cancel_event(cancel_event)
            if user_id:
                user_token = user_context.set(user_id)
            if drive_context_payload:
                drive_token = set_drive_context(drive_context_payload)

            run_task = asyncio.create_task(
                asyncio.wait_for(
                    self._compiled_graph.ainvoke(initial_state, config=config_dict),
                    timeout=self.langgraph_stream_timeout_seconds,
                )
            )
            heartbeat = cfg.stream_heartbeat_seconds

            if session_id:
                async with self._runs_lock:
                    # Cancel any existing run for this session before starting a new one
                    existing_task = self._active_runs.get(session_id)
                    if existing_task and not existing_task.done():
                        logger.warning(f"Cancelling existing run for session {session_id} before starting new one")
                        existing_task.cancel()
                        # Don't await here to avoid blocking, just fire and forget
                    self._active_runs[session_id] = run_task

            while not run_task.done():
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError
                try:
                    token_delta = await asyncio.wait_for(token_queue.get(), timeout=heartbeat)
                    if isinstance(token_delta, dict):
                        if token_delta.get("type") == "stream_event":
                            yield {"type": "stream_event", "event": token_delta.get("event")}
                        elif token_delta.get("type") == "status":
                            yield {"type": "status", "message": token_delta.get("message")}
                        else:
                            # Pass through other dict events
                            yield token_delta
                    elif isinstance(token_delta, str) and token_delta:
                        yield {"type": "content", "content": token_delta}
                except asyncio.TimeoutError:
                    # Only emit heartbeat if no explicit status message exists
                    if not final_state or not final_state.get("status_message"):
                        yield {"type": "status", "message": "working..."}

            try:
                while True:
                    if cancel_event and cancel_event.is_set():
                        raise asyncio.CancelledError
                    token_delta = token_queue.get_nowait()
                    if isinstance(token_delta, dict):
                        if token_delta.get("type") == "stream_event":
                            yield {"type": "stream_event", "event": token_delta.get("event")}
                        elif token_delta.get("type") == "status":
                            yield {"type": "status", "message": token_delta.get("message")}
                        else:
                            # Pass through other dict events
                            yield token_delta
                    elif isinstance(token_delta, str) and token_delta:
                        yield {"type": "content", "content": token_delta}
            except asyncio.QueueEmpty:
                pass

            final_state = await run_task
        except asyncio.CancelledError:
            run_task.cancel()
            try:
                await run_task
            except asyncio.CancelledError:
                pass
            yield {"type": "cancelled"}
            return
        except asyncio.TimeoutError as exc:
            streaming_error = exc
            logger.error(
                "[STREAM] LangGraph run timed out after %.1fs",
                self.langgraph_stream_timeout_seconds,
            )
            yield {
                "type": "content",
                "content": "Processing timed out. Please try again or simplify the request.",
            }
        except Exception as exc:
            streaming_error = exc
        finally:
            if user_token is not None:
                try:
                    user_context.reset(user_token)
                except Exception:
                    pass
            if drive_token is not None:
                try:
                    reset_drive_context(drive_token)
                except Exception:
                    pass
            reset_token_sink(sink_token)
            if cancel_token is not None:
                reset_cancel_event(cancel_token)
            if session_id:
                async with self._runs_lock:
                    stored = self._active_runs.get(session_id)
                    if stored is run_task:
                        self._active_runs.pop(session_id, None)

        if isinstance(final_state, dict):
            self._record_run_metadata(session_id, final_state, selected_model)

        if streaming_error or not isinstance(final_state, dict):
            error_payload = {
                "message": "Streaming failed. Please retry or pick a smaller request.",
                "detail": str(streaming_error) if streaming_error else "final_state missing",
                "category": "streaming",
                "retryable": False,
            }
            logger.error(f"[STREAM] Fatal error: {error_payload['detail']}")
            yield {"type": "error", "errors": [error_payload]}
            yield {"type": "done"}
            return

        messages = final_state.get("messages", []) or []
        assistant_charts: List[Any] = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                charts = msg.get("charts")
                if isinstance(charts, list) and charts:
                    assistant_charts.extend(charts)

        sources_out = final_state.get("search_sources") or []
        charts_out = final_state.get("charts") or []
        if not charts_out and assistant_charts:
            charts_out = assistant_charts

        if charts_out:
            seen_ids = set()
            unique_charts: List[Any] = []
            for chart in charts_out:
                if isinstance(chart, dict) and chart.get("id"):
                    cid = chart["id"]
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    unique_charts.append(chart)
                else:
                    unique_charts.append(chart)
            charts_out = unique_charts
            charts_out, _ = self._hydrate_chart_handles(charts_out)

        if sources_out:
            yield {"type": "sources", "sources": sources_out}
        if charts_out:
            yield {"type": "charts", "charts": charts_out}

        code_execution_data = final_state.get("code_execution_data")
        if isinstance(code_execution_data, dict) and (
            code_execution_data.get("generated_files")
            or code_execution_data.get("container_id")
            or code_execution_data.get("code_blocks")
        ):
            yield {"type": "extras", "extras": code_execution_data}

        errors = final_state.get("errors") or []
        if errors:
            yield {"type": "error", "errors": errors}

        yield {"type": "done"}
        return

    async def cancel_active_run(self, session_id: str) -> bool:
        """Request cooperative cancellation for an active streaming run."""
        async with self._runs_lock:
            task = self._active_runs.get(session_id)

        if not task or task.done():
            return False

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics including multi-tool workflow stats"""

        return {
            "langgraph_enabled": True,
            "orchestration_type": "supervisor_pattern_enhanced",
            "node_count": 8,
            "features": {
                "multi_tool_workflows": True,
                "portfolio_state_management": True,
                "result_aggregation": True,
                "parallel_tool_calls": True
            },
            "mcp_servers": {
                "market_server": "operational" if hasattr(self, 'market_server') else "not initialized",
                "economic_server": "operational" if hasattr(self, 'economic_server') else "not initialized"
            },
            "agents": {
                "main_agent": "operational" if hasattr(self, 'main_agent') else "not initialized",
                "risk_specialist": "operational" if hasattr(self, 'risk_specialist') else "not initialized"
            }
        }


# Feature flag integration
def create_orchestrator(enable_langgraph: bool = True) -> Any:
    """
    Factory function to create orchestrator.

    Since AgentOrchestrator has been archived, this always returns LangGraphOrchestrator.
    The parameter is kept for backward compatibility but ignored.

    Args:
        enable_langgraph: Kept for backward compatibility (ignored)

    Returns:
        LangGraphOrchestrator instance
    """

    logger.info("Creating LangGraph orchestrator (unified architecture)")
    return LangGraphOrchestrator()
