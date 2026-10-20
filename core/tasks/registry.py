"""
Declarative registry for the Tasks backend.
Maps frontend node types and agent modes to backend execution metadata so the parser
and executor can make decisions without embedding switch statements everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from .types import (
    TaskAgentMode,
    TaskDeliveryChannel,
    TaskNodeType,
)

NodeCategory = Literal["entrance", "input", "agent", "output", "delivery", "utility"]


@dataclass(frozen=True)
class AgentSpec:
    """Metadata for mapping an agent mode to an orchestrator implementation."""

    mode: TaskAgentMode
    orchestrator_attr: str
    default_model: str
    default_tools: List[str] = field(default_factory=list)
    default_mcp_servers: List[str] = field(default_factory=list)
    supports_reasoning_control: bool = True
    notes: Optional[str] = None


@dataclass(frozen=True)
class NodeSpec:
    """Describes a canvas node type."""

    type: TaskNodeType
    category: NodeCategory
    description: str
    config_keys: List[str] = field(default_factory=list)
    produces_assets: bool = False
    consumes_assets: bool = False


@dataclass(frozen=True)
class DeliverySpec:
    """Adapter metadata for delivery nodes."""

    channel: TaskDeliveryChannel
    adapter_name: str
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)


# ===== Agent Registry =====

AGENT_REGISTRY: Dict[TaskAgentMode, AgentSpec] = {
    TaskAgentMode.AUTO: AgentSpec(
        mode=TaskAgentMode.AUTO,
        orchestrator_attr="main_agent",
        default_model="gpt-5.4",
        default_tools=[
            "web_search",
            "read_file_content",
            "search_file_chunks_tool",
            "drive_list_files",
            "drive_get_file_preview",
            "CodeInterpreterTool",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
            "EconomicDataServer",
            "SECFilingServer",
            "YFinanceServer",
        ],
        notes="Auto-mode lets the orchestrator supervisor pick downstream specialists.",
    ),
    TaskAgentMode.GENERALIST: AgentSpec(
        mode=TaskAgentMode.GENERALIST,
        orchestrator_attr="main_agent",
        default_model="gpt-5.4",
        default_tools=[
            "web_search",
            "read_file_content",
            "search_file_chunks_tool",
            "drive_list_files",
            "drive_get_file_preview",
            "CodeInterpreterTool",
            "market_chart_build_tool",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
            "EconomicDataServer",
            "SECFilingServer",
        ],
    ),
    TaskAgentMode.RISK: AgentSpec(
        mode=TaskAgentMode.RISK,
        orchestrator_attr="risk_specialist",
        default_model="gpt-5.4",
        default_tools=[
            "calculate_var",
            "run_monte_carlo",
            "optimize_portfolio",
            "analyze_barra_factors",
            "create_hedge_portfolio",
            "list_user_portfolios",
            "get_portfolio",
            "set_active_portfolio",
            "get_active_portfolio",
            "CodeInterpreterTool",
        ],
        default_mcp_servers=[
            "YFinanceServer",
            "EconomicDataServer",
        ],
    ),
    TaskAgentMode.FILINGS: AgentSpec(
        mode=TaskAgentMode.FILINGS,
        orchestrator_attr="document_analyst",
        default_model="gpt-5.4",
        default_tools=[
            "sec_index_filing",
            "sec_search_filings",
            "sec_get_filing",
            "read_file_content",
            "search_file_chunks_tool",
            "drive_list_files",
            "drive_get_file_preview",
            "CodeInterpreterTool",
            "web_search",
        ],
        default_mcp_servers=[
            "FMPDocumentServer",
            "SECFilingServer",
        ],
    ),
    TaskAgentMode.MULTIPLES: AgentSpec(
        mode=TaskAgentMode.MULTIPLES,
        orchestrator_attr="comparable_companies",
        default_model="gpt-5.4",
        default_tools=[
            "analyze_comparable_companies",
            "CodeInterpreterTool",
            "web_search",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
        ],
    ),
    TaskAgentMode.CHARTS: AgentSpec(
        mode=TaskAgentMode.CHARTS,
        orchestrator_attr="chart_analyst",
        default_model="gpt-5.4",
        default_tools=[
            "market_chart_build_tool",
            "CodeInterpreterTool",
            "web_search",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
        ],
    ),
    TaskAgentMode.QUANT: AgentSpec(
        mode=TaskAgentMode.QUANT,
        orchestrator_attr="quant_coding",
        default_model="gpt-5.4",
        default_tools=[
            "CodeInterpreterTool",
            "read_file_content",
            "search_file_chunks_tool",
            "web_search",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
            "EconomicDataServer",
            "FMPAlternativesServer",
        ],
    ),
    TaskAgentMode.DCF: AgentSpec(
        mode=TaskAgentMode.DCF,
        orchestrator_attr="dcf_agent",
        default_model="gpt-5.4",
        default_tools=[
            "gather_dcf_data_sources",
            "analyze_three_stage_dcf",
            "analyze_two_stage_dcf",
            "analyze_stable_stage_dcf",
            "dcf_sensitivity_analysis",
            "CodeInterpreterTool",
            "web_search",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
            "EconomicDataServer",
            "FMPAdvancedValuationServer",
        ],
    ),
    TaskAgentMode.ALTERNATIVES: AgentSpec(
        mode=TaskAgentMode.ALTERNATIVES,
        orchestrator_attr="alternatives_coding",
        default_model="gpt-5.4",
        default_tools=[
            "CodeInterpreterTool",
            "web_search",
            "read_file_content",
            "search_file_chunks_tool",
        ],
        default_mcp_servers=[
            "FMPAlternativesServer",
            "PolygonCryptoFXServer",
        ],
    ),
    TaskAgentMode.INSTITUTIONAL: AgentSpec(
        mode=TaskAgentMode.INSTITUTIONAL,
        orchestrator_attr="institutional_activity",
        default_model="gpt-5.4",
        default_tools=[
            "CodeInterpreterTool",
            "web_search",
            "read_file_content",
        ],
        default_mcp_servers=[
            "FMPTradeFlowServer",
        ],
    ),
    TaskAgentMode.PREDICTION_MARKETS: AgentSpec(
        mode=TaskAgentMode.PREDICTION_MARKETS,
        orchestrator_attr="prediction_markets_analyst",
        default_model="gpt-5.4",
        default_tools=[
            "web_search",
            "CodeInterpreterTool",
            "read_file_content",
            "search_file_chunks_tool",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
            "PolymarketServer",
        ],
    ),
    TaskAgentMode.FUNDS_PRODUCTS: AgentSpec(
        mode=TaskAgentMode.FUNDS_PRODUCTS,
        orchestrator_attr="funds_products_analyst",
        default_model="gpt-5.4",
        default_tools=[
            "web_search",
            "CodeInterpreterTool",
            "read_file_content",
        ],
        default_mcp_servers=[
            "FMPMarketDataServer",
            "FMPAlternativesServer",
        ],
    ),
}


AVAILABLE_AGENT_MODES = set(AGENT_REGISTRY.keys())


# ===== Node Registry =====

NODE_REGISTRY: Dict[TaskNodeType, NodeSpec] = {
    TaskNodeType.START: NodeSpec(
        type=TaskNodeType.START,
        category="entrance",
        description="Fixed start node, single source handle.",
    ),
    TaskNodeType.END: NodeSpec(
        type=TaskNodeType.END,
        category="entrance",
        description="Fixed end node, terminal sink.",
    ),
    TaskNodeType.PORTFOLIO: NodeSpec(
        type=TaskNodeType.PORTFOLIO,
        category="input",
        description="Loads a saved portfolio under RLS.",
        config_keys=["portfolioId", "name", "description"],
        produces_assets=True,
    ),
    TaskNodeType.FILE_UPLOAD: NodeSpec(
        type=TaskNodeType.FILE_UPLOAD,
        category="input",
        description="User-uploaded file attachment.",
        config_keys=["fileName", "fileId", "fileSize", "fileType", "name", "description"],
        produces_assets=True,
    ),
    TaskNodeType.ONEDRIVE: NodeSpec(
        type=TaskNodeType.ONEDRIVE,
        category="input",
        description="OneDrive file connector.",
        config_keys=["accountType", "connectedFile", "fileId", "fileSize", "fileType", "name", "description"],
        produces_assets=True,
    ),
    TaskNodeType.GOOGLE_DRIVE: NodeSpec(
        type=TaskNodeType.GOOGLE_DRIVE,
        category="input",
        description="Google Drive file connector.",
        config_keys=["accountType", "connectedFile", "fileId", "fileSize", "fileType", "name", "description"],
        produces_assets=True,
    ),
    TaskNodeType.GRAPH: NodeSpec(
        type=TaskNodeType.GRAPH,
        category="input",
        description="Graph data source (coming soon).",
        config_keys=["graphId", "name", "description"],
        produces_assets=True,
    ),
    TaskNodeType.MERGE: NodeSpec(
        type=TaskNodeType.MERGE,
        category="utility",
        description="Merge node that combines multiple data sources into one output.",
        config_keys=["aggregationMode", "label"],
        consumes_assets=False,
        produces_assets=False,
    ),
    TaskNodeType.DISTRIBUTE: NodeSpec(
        type=TaskNodeType.DISTRIBUTE,
        category="utility",
        description="Distribute node that sends output to multiple delivery channels.",
        config_keys=["label"],
        consumes_assets=False,
        produces_assets=False,
    ),
    TaskNodeType.AGENT: NodeSpec(
        type=TaskNodeType.AGENT,
        category="agent",
        description="Specialist agent node.",
        config_keys=[
            "agent",
            "model",
            "instructions",
            "tools",
            "mcpServers",
            "reasoning",
            "responseLength",
            "temperature",
            "maxTokens",
        ],
        consumes_assets=True,
        produces_assets=True,
    ),
    TaskNodeType.PDF_REPORT: NodeSpec(
        type=TaskNodeType.PDF_REPORT,
        category="output",
        description="Structured PDF output node.",
        config_keys=["name", "contentInstructions", "dataIntensity", "verbosity"],
        consumes_assets=True,
    ),
    TaskNodeType.PPT_PRESENTATION: NodeSpec(
        type=TaskNodeType.PPT_PRESENTATION,
        category="output",
        description="Presentation output node.",
        config_keys=["name", "contentInstructions", "dataIntensity", "verbosity", "slideCount"],
        consumes_assets=True,
    ),
    TaskNodeType.WORKBOOK: NodeSpec(
        type=TaskNodeType.WORKBOOK,
        category="output",
        description="Workbook/Excel output node.",
        config_keys=["name", "contentInstructions", "workbookType", "verbosity"],
        consumes_assets=True,
    ),
    TaskNodeType.EMAIL: NodeSpec(
        type=TaskNodeType.EMAIL,
        category="delivery",
        description="Email delivery node.",
        config_keys=["emails", "customMessage", "aiGeneratedMessage"],
        consumes_assets=True,
    ),
    TaskNodeType.SLACK: NodeSpec(
        type=TaskNodeType.SLACK,
        category="delivery",
        description="Slack delivery via connected workspace.",
        config_keys=[
            "workspaceId",
            "workspaceName",
            "channelIds",
            "channelNames",
            "customMessage",
            "aiGeneratedMessage",
            "connected",
        ],
        consumes_assets=True,
    ),
    TaskNodeType.TEAMS: NodeSpec(
        type=TaskNodeType.TEAMS,
        category="delivery",
        description="Teams delivery via Microsoft Graph.",
        config_keys=[
            "tenantId",
            "tenantName",
            "teamId",
            "teamName",
            "channelIds",
            "channelNames",
            "customMessage",
            "aiGeneratedMessage",
            "connected",
        ],
        consumes_assets=True,
    ),
    TaskNodeType.SAVE_TO_SENTRY: NodeSpec(
        type=TaskNodeType.SAVE_TO_SENTRY,
        category="delivery",
        description="Persist output into Sentry workspace.",
        config_keys=["notes"],
        consumes_assets=True,
    ),
}

NODE_CATEGORY_INDEX: Dict[TaskNodeType, NodeCategory] = {
    spec.type: spec.category for spec in NODE_REGISTRY.values()
}


# ===== Delivery Registry =====

DELIVERY_REGISTRY: Dict[TaskDeliveryChannel, DeliverySpec] = {
    TaskDeliveryChannel.EMAIL: DeliverySpec(
        channel=TaskDeliveryChannel.EMAIL,
        adapter_name="email_adapter",
        required_fields=["emails"],
        optional_fields=["customMessage", "aiGeneratedMessage"],
    ),
    TaskDeliveryChannel.SLACK: DeliverySpec(
        channel=TaskDeliveryChannel.SLACK,
        adapter_name="slack_adapter",
        required_fields=["workspaceId", "channelIds"],
        optional_fields=["customMessage", "aiGeneratedMessage", "channelNames"],
    ),
    TaskDeliveryChannel.TEAMS: DeliverySpec(
        channel=TaskDeliveryChannel.TEAMS,
        adapter_name="teams_adapter",
        required_fields=["tenantId", "teamId", "channelIds"],
        optional_fields=["customMessage", "aiGeneratedMessage", "channelNames"],
    ),
    TaskDeliveryChannel.SAVE_TO_SENTRY: DeliverySpec(
        channel=TaskDeliveryChannel.SAVE_TO_SENTRY,
        adapter_name="sentry_storage_adapter",
        required_fields=[],
    ),
}


# ===== Helper Functions =====

def get_agent_spec(mode: TaskAgentMode) -> AgentSpec:
    """Return the metadata for the given agent mode."""
    try:
        return AGENT_REGISTRY[mode]
    except KeyError as exc:
        raise KeyError(f"Unsupported agent mode: {mode}") from exc


def get_node_spec(node_type: TaskNodeType) -> NodeSpec:
    """Return node metadata or raise if unsupported."""
    try:
        return NODE_REGISTRY[node_type]
    except KeyError as exc:
        raise KeyError(f"Unsupported node type: {node_type}") from exc


def get_delivery_spec(channel: TaskDeliveryChannel) -> DeliverySpec:
    """Return delivery adapter metadata."""
    try:
        return DELIVERY_REGISTRY[channel]
    except KeyError as exc:
        raise KeyError(f"Unsupported delivery channel: {channel}") from exc
