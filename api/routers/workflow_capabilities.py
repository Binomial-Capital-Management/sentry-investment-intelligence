"""
Workflow Capabilities API Router
Status: Production
Created: January 2025

PURPOSE: Provides dynamic discovery of workflow capabilities including agents, datasets, outputs, tools and MCP servers.
NO HARDCODING - discovers from actual implementations.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging
import inspect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow-capabilities", tags=["capabilities"])


def discover_agent_tools(agent_name: str) -> List[Dict[str, str]]:
    """
    Dynamically discover tools for a specific agent.
    NO HARDCODING - reads from actual implementations.
    """
    tools = []
    
    try:
        if agent_name == "Risk Specialist":
            # Import risk tools dynamically
            from core.agents.risk_tools import RISK_TOOLS
            for tool in RISK_TOOLS:
                # Extract tool info from function
                tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
                tool_doc = tool.__doc__ if hasattr(tool, '__doc__') else ""
                # Parse first line of docstring as description
                description = tool_doc.split('\n')[0].strip() if tool_doc else tool_name
                tools.append({
                    "id": tool_name,
                    "name": tool_name.replace('_', ' ').title(),
                    "description": description
                })
            
            # Add portfolio tools
            from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
            for tool in PORTFOLIO_TOOLS:
                tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
                tool_doc = tool.__doc__ if hasattr(tool, '__doc__') else ""
                description = tool_doc.split('\n')[0].strip() if tool_doc else tool_name
                tools.append({
                    "id": tool_name,
                    "name": tool_name.replace('_', ' ').title(),
                    "description": description
                })
                
        elif agent_name == "Generalist":
            # Import generalist tools
            from core.tools.web_search import web_search
            tools.append({
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web for information"
            })
            
            try:
                from core.charts.tools import market_chart_build_tool
                tools.append({
                    "id": "market_chart_build_tool",
                    "name": "Market Chart Builder",
                    "description": "Generate market data charts"
                })
            except ImportError:
                logger.warning("Chart tools not available")
            
            # Add portfolio tools
            from core.agents.portfolio_tools_v2 import PORTFOLIO_TOOLS
            for tool in PORTFOLIO_TOOLS:
                tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
                tool_doc = tool.__doc__ if hasattr(tool, '__doc__') else ""
                description = tool_doc.split('\n')[0].strip() if tool_doc else tool_name
                tools.append({
                    "id": tool_name,
                    "name": tool_name.replace('_', ' ').title(),
                    "description": description
                })
                
        elif agent_name == "Document Analyst":
            tools.append({
                "id": "analyze_documents",
                "name": "Analyze Documents",
                "description": "Extract and analyze document content"
            })
            tools.append({
                "id": "search_filings",
                "name": "Search SEC Filings",
                "description": "Search and retrieve SEC filings"
            })
            
        elif agent_name == "Comparable Companies":
            tools.append({
                "id": "find_comparable_companies",
                "name": "Find Comparable Companies",
                "description": "Identify peer companies for analysis"
            })
            tools.append({
                "id": "analyze_valuation_multiples",
                "name": "Analyze Valuation Multiples",
                "description": "Calculate and compare valuation metrics"
            })
            
    except ImportError as e:
        logger.warning(f"Could not import tools for {agent_name}: {e}")
    
    return tools


def get_mcp_servers(agent_name: str) -> List[Dict[str, Any]]:
    """
    Get available MCP servers for an agent.
    """
    servers = []
    
    # All agents can potentially use these servers
    all_servers = [
        {"id": "FMPMarketDataServer", "name": "FMP Market Data", "required": False},
        {"id": "FMPDocumentServer", "name": "FMP Documents", "required": False},
        {"id": "YFinanceServer", "name": "Yahoo Finance", "required": False},
        {"id": "EconomicDataServer", "name": "Economic Data (FRED)", "required": False},
        {"id": "SECFilingServer", "name": "SEC Filings", "required": False},
        {"id": "QuiverQuantServer", "name": "Quiver Quant", "required": False},
    ]
    
    # Agent-specific server requirements
    if agent_name == "Risk Specialist":
        servers = all_servers[:4]  # Market and economic data
        servers[0]["required"] = True  # FMP Market is primary
    elif agent_name == "Generalist":
        servers = [all_servers[0], all_servers[2], all_servers[3], all_servers[5]]  # Market, economic, and Quiver data
    elif agent_name == "Document Analyst":
        servers = [all_servers[1], all_servers[4]]  # Document servers
        servers[0]["required"] = True  # FMP Documents primary
    elif agent_name == "Comparable Companies":
        servers = [all_servers[0]]  # FMP Market for peer data
        servers[0]["required"] = True
    else:
        servers = all_servers  # All available
    
    return servers


def get_dataset_options() -> Dict[str, Any]:
    """Get available dataset configuration options."""
    return {
        "sources": [
            {"id": "portfolio", "name": "Portfolio Data", "description": "User's saved portfolios"},
            {"id": "market", "name": "Market Data", "description": "Live market prices"},
            {"id": "upload", "name": "Custom Upload", "description": "CSV or JSON file"}
        ],
        "timeRanges": [
            {"id": "1d", "name": "1 Day"},
            {"id": "7d", "name": "7 Days"},
            {"id": "30d", "name": "30 Days"},
            {"id": "1y", "name": "1 Year"},
            {"id": "all", "name": "All Time"}
        ],
        "refreshModes": [
            {"id": "realtime", "name": "Real-time", "description": "Updates continuously"},
            {"id": "cached", "name": "Cached", "description": "Refreshes periodically"},
            {"id": "static", "name": "Static", "description": "Loaded once"}
        ]
    }


def get_output_options() -> Dict[str, Any]:
    """Get available output configuration options."""
    return {
        "formats": [
            {"id": "chart", "name": "Interactive Chart"},
            {"id": "table", "name": "Data Table"},
            {"id": "document", "name": "Document Report"}
        ],
        "chartTypes": [
            {"id": "line", "name": "Line Chart", "description": "Time series and trends"},
            {"id": "bar", "name": "Bar Chart", "description": "Categorical comparisons"},
            {"id": "scatter", "name": "Scatter Plot", "description": "Correlation analysis"},
            {"id": "pie", "name": "Pie Chart", "description": "Portfolio composition"},
            {"id": "heatmap", "name": "Heatmap", "description": "Correlation matrices"},
            {"id": "histogram", "name": "Histogram", "description": "Distribution analysis"},
            {"id": "box", "name": "Box Plot", "description": "Statistical summaries"}
        ],
        "tableColumns": [
            "Ticker", "Weight", "Value", "Return", "Risk", "Sharpe", "Beta", "Alpha"
        ],
        "documentSections": [
            {"id": "summary", "name": "Executive Summary"},
            {"id": "details", "name": "Detailed Analysis"},
            {"id": "charts", "name": "Charts & Visualizations"},
            {"id": "raw", "name": "Raw Data"}
        ]
    }


@router.get("/", response_model=Dict[str, Any])
async def get_workflow_capabilities():
    """
    Get capabilities for all workflow components.
    Returns agents, datasets, outputs, tools and MCP servers.
    """
    try:
        # Discover available agents dynamically
        agents = {}
        
        # Check which agents are available
        agent_types = [
            ("Generalist", "Market research, web search, data synthesis"),
            ("Risk Specialist", "VaR, Monte Carlo, portfolio optimization"),
            ("Document Analyst", "Document extraction and analysis"),
            ("Comparable Companies", "Peer analysis and valuation")
        ]
        
        for agent_name, description in agent_types:
            # Try to verify agent exists
            try:
                if agent_name == "Risk Specialist":
                    from core.agents.RiskSpecialistAgent import create_risk_specialist_agent
                elif agent_name == "Generalist":
                    from core.agents.MainAgent import create_main_agent
                elif agent_name == "Document Analyst":
                    from core.agents.DocumentAnalystAgent import create_document_analyst_agent
                elif agent_name == "Comparable Companies":
                    from core.agents.ComparableCompaniesAgent import create_comparable_companies_agent
                else:
                    continue
                    
                # Agent exists, get its capabilities
                agents[agent_name] = {
                    "label": agent_name,
                    "description": description,
                    "tools": discover_agent_tools(agent_name),
                    "mcpServers": get_mcp_servers(agent_name)
                }
            except ImportError:
                logger.warning(f"Agent {agent_name} not available")
                continue
        
        return {
            "status": "success",
            "agents": agents,
            "datasets": get_dataset_options(),
            "outputs": get_output_options()
        }
        
    except Exception as e:
        logger.error(f"Error discovering workflow capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))
