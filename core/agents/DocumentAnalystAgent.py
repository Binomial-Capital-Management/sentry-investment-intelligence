"""
Document Analyst Agent Factory - Creates the document analysis agent
Status: Production
Created: December 2025

PURPOSE: Factory function for creating the Document Analyst agent
that handles SEC filings, earnings transcripts, and insider trading analysis.

This agent:
- Fetches and analyzes documents via FMPDocumentServer
- Processes earnings call transcripts
- Analyzes insider and senate trading patterns
- Provides citations and sources
"""

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning
from typing import Any
import logging

logger = logging.getLogger(__name__)


def create_document_analyst_agent(
    document_server: Any = None,
    sec_filing_server: Any = None,
    quiver_server: Any = None,
    model: str = None,
) -> Agent:
    """
    Create the document analyst agent with document servers.
    
    Args:
        document_server: FMPDocumentServer instance for document access (optional)
        sec_filing_server: SECFilingServer instance for SEC filings (optional)
        quiver_server: QuiverQuantServer instance for insider, congressional, lobbying,
            and alternative-signal context around filings (optional)
        model: Optional model override (defaults to config.agent_model)
        
    Returns:
        Configured Agent instance with document servers
    """
    
    # Import the enhanced prompt from the prompts module
    from core.agents.prompts.document_analyst_prompt import get_document_analyst_prompt
    
    # Use the enhanced GPT-5 optimized prompt
    instructions = get_document_analyst_prompt()
    
    # Import document tools (SEC only - FMP tools come from MCP server directly)
    from core.agents.tools.document_tools import (
        sec_index_filing,
        sec_search_filings,
        sec_get_filing,
        set_document_servers
    )

    # Import file tools for user-uploaded documents
    from core.agents.file_tools import read_file_content
    from core.agents.file_retrieval_tools import search_file_chunks_tool
    from core.agents.drive_tools import drive_list_files, drive_get_file_preview
    
    # Import memory tools for saving important info
    from core.agents.memory_tools import MEMORY_TOOLS

    # Collect available MCP servers
    mcp_servers = []

    if document_server:
        mcp_servers.append(document_server)
        logger.info(f"Document analyst includes FMP Document Server: {document_server}")

    if sec_filing_server:
        mcp_servers.append(sec_filing_server)
        logger.info(f"Document analyst includes SEC Filing Server: {sec_filing_server}")

    if quiver_server:
        mcp_servers.append(quiver_server)
        logger.info(f"Document analyst includes Quiver Server: {quiver_server}")

    if not mcp_servers:
        logger.warning("Document analyst created without any document servers")
    else:
        logger.info(f"Document analyst will be created with {len(mcp_servers)} MCP server(s)")

    # Set document servers for the tools to use
    set_document_servers(sec_server=sec_filing_server, fmp_server=document_server)

    # Collect document tools (public APIs + user uploads)
    # Note: FMP document tools (list_document_types, discover_documents, get_raw_document)
    # come from FMPDocumentServer MCP directly - no wrappers needed
    tools = [
        # SEC document tools (wrappers add timeout/session handling)
        sec_index_filing,
        sec_search_filings,
        sec_get_filing,
        # User-uploaded document tools
        read_file_content,       # Read full uploaded files
        search_file_chunks_tool,  # Semantic search over uploaded docs
        # Google Drive tools
        drive_list_files,
        drive_get_file_preview,
    ]

    # Add web search tool for emergency fallback
    from core.tools.web_search import web_search
    tools.append(web_search)
    
    # Add memory tools for saving important info
    tools.extend(MEMORY_TOOLS)

    from core.agents.bh_tools import BINOMIAL_HASH_CHAT_TOOLS
    tools.extend(BINOMIAL_HASH_CHAT_TOOLS)

    # Use provided model or default from config (no hardcoding)
    if not model:
        from core.config import get_config
        model = get_config().agent_model
    
    agent = Agent(
        name="DocumentAnalyst",
        instructions=instructions,
        model=model,  # Dynamic model selection, not hardcoded
        mcp_servers=mcp_servers,  # MCP servers automatically provide tools
        tools=tools,  # Explicit document tools
        model_settings=ModelSettings(
            tool_choice="required",  # Force tool usage to prevent looping
            parallel_tool_calls=True,
            max_tokens=15000,  # Increased output limit for comprehensive responses
            reasoning=Reasoning(effort="medium", summary="detailed")  # Maintain consistent extraction diligence
        )
    )
    
    logger.info(f"Document analyst agent created with {len(mcp_servers)} server(s)")
    
    # NEW Lines 90-95: Verify tool registration
    if hasattr(agent, 'tools'):
        logger.info(f"Document Analyst has {len(agent.tools)} tools registered")
        for tool in agent.tools[:10]:  # Log first 10 to avoid spam
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            logger.info(f"  - Registered tool: {tool_name}")
    else:
        logger.warning("Document Analyst agent has no 'tools' attribute")
    
    return agent
