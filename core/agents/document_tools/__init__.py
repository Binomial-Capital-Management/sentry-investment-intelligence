"""
Document Analysis Tools for Document Analyst Agent
Following the same modular pattern as risk_tools
"""

from .discover_documents import discover_documents_tool
from .get_document_content import get_document_content_tool
from .analyze_insider_trading import analyze_insider_trading_tool
from .compare_filings import compare_filings_tool

# Export all tools and the combined list
__all__ = [
    'discover_documents_tool',
    'get_document_content_tool', 
    'analyze_insider_trading_tool',
    'compare_filings_tool',
    'DOCUMENT_TOOLS'
]

# Combined list of all document tools for the agent
DOCUMENT_TOOLS = [
    discover_documents_tool,
    get_document_content_tool,
    analyze_insider_trading_tool,
    compare_filings_tool
]

# Convenience functions that match tool names
discover_documents = discover_documents_tool
get_document_content = get_document_content_tool
analyze_insider_trading = analyze_insider_trading_tool
compare_filings = compare_filings_tool