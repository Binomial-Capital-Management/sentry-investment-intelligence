# Lines 1-20: Imports and setup
from agents import function_tool
from typing import Optional, Dict, Any
import logging
import json
import asyncio
from core.config import config

logger = logging.getLogger(__name__)

# Global references (set by DocumentAnalystAgent)
_sec_server = None
_fmp_doc_server = None

def set_document_servers(sec_server=None, fmp_server=None):
    """Set global server references"""
    global _sec_server, _fmp_doc_server
    _sec_server = sec_server
    _fmp_doc_server = fmp_server

# Lines 25-55: SEC index_filing wrapper
@function_tool
async def sec_index_filing(
    ticker: str,
    filing_type: str = "10-K",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    """Index a company's SEC filing for semantic search."""
    try:
        if not _sec_server:
            return json.dumps({"status": "error", "error_type": "server_unavailable",
                   "hint": "SEC server not initialized"})
        
        ctx = getattr(_sec_server, '_session_context', {}) or {}
        effective_user_id = user_id or ctx.get('user_id')
        effective_session_id = session_id or ctx.get('session_id')
        
        if hasattr(_sec_server, 'set_session_context') and (effective_session_id or effective_user_id):
            _sec_server.set_session_context(effective_session_id, effective_user_id)
        
        result = await asyncio.wait_for(
            _sec_server.index_filing(ticker, filing_type, effective_user_id),
            timeout=config.sec_operation_timeout
        )
        return json.dumps({"status": "success", "data": result})
        
    except asyncio.TimeoutError:
        return json.dumps({"status": "error", "error_type": "timeout",
               "hint": f"Operation timed out after {config.sec_operation_timeout}s"})
    except Exception as e:
        logger.error(f"Error in sec_index_filing: {e}")
        return json.dumps({"status": "error", "error_type": "execution_error",
               "hint": str(e)})

# Lines 60-90: SEC search_filings wrapper
@function_tool
async def sec_search_filings(
    query: str,
    top_k: int = 10,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    """Search indexed SEC filings using semantic and keyword search."""
    try:
        if not _sec_server:
            return json.dumps({"status": "error", "error_type": "server_unavailable",
                   "hint": "SEC server not initialized"})
        
        ctx = getattr(_sec_server, '_session_context', {}) or {}
        effective_user_id = user_id or ctx.get('user_id')
        effective_session_id = session_id or ctx.get('session_id')
        
        if hasattr(_sec_server, 'set_session_context') and (effective_session_id or effective_user_id):
            _sec_server.set_session_context(effective_session_id, effective_user_id)
        
        result = await asyncio.wait_for(
            _sec_server.search_filings(query, top_k, effective_user_id, effective_session_id),
            timeout=config.sec_operation_timeout
        )
        return json.dumps({"status": "success", "data": result})
        
    except asyncio.TimeoutError:
        return json.dumps({"status": "error", "error_type": "timeout",
               "hint": f"Search timed out after {config.sec_operation_timeout}s"})
    except Exception as e:
        logger.error(f"Error in sec_search_filings: {e}")
        return json.dumps({"status": "error", "error_type": "execution_error",
               "hint": str(e)})

# Lines 95-130: SEC get_filing wrapper
@function_tool
async def sec_get_filing(
    company: str,
    filing_type: str = "latest",
    query: Optional[str] = None,
    top_k: int = 10,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    stream: bool = False
) -> str:
    """Get and search a specific SEC filing."""
    try:
        if not _sec_server:
            return json.dumps({"status": "error", "error_type": "server_unavailable",
                   "hint": "SEC server not initialized"})
        
        ctx = getattr(_sec_server, '_session_context', {}) or {}
        effective_user_id = user_id or ctx.get('user_id')
        effective_session_id = session_id or ctx.get('session_id')
        
        if hasattr(_sec_server, 'set_session_context') and (effective_session_id or effective_user_id):
            _sec_server.set_session_context(effective_session_id, effective_user_id)
        
        result = await asyncio.wait_for(
            _sec_server.get_filing(company, filing_type, query, top_k,
                                  stream, effective_user_id, effective_session_id),
            timeout=config.sec_operation_timeout
        )
        return json.dumps({"status": "success", "data": result})
        
    except asyncio.TimeoutError:
        return json.dumps({"status": "error", "error_type": "timeout",
               "hint": f"Filing retrieval timed out after {config.sec_operation_timeout}s"})
    except Exception as e:
        logger.error(f"Error in sec_get_filing: {e}")
        return json.dumps({"status": "error", "error_type": "execution_error",
               "hint": str(e)})

# Lines 135-155: FMP list_document_types wrapper - REMOVED (use MCP server directly)
# @function_tool
# async def fmp_list_document_types() -> Dict[str, Any]:
#     """Agent should use list_document_types from FMPDocumentServer MCP directly"""
#     pass


# Lines 160-185: FMP discover_documents wrapper - REMOVED (use MCP server directly)
# @function_tool
# async def fmp_discover_documents(symbol: str, depth: str = "quick") -> Dict[str, Any]:
#     """Agent should use discover_documents from FMPDocumentServer MCP directly"""
#     pass


# Lines 190-215: FMP get_document wrapper - REMOVED (use MCP server directly)
# Agent should use get_raw_document from FMPDocumentServer MCP directly
# This avoids params confusion and lets the MCP inputSchema handle validation