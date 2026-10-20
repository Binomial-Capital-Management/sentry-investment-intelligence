"""
Native OpenAI WebSearchTool implementation for GPT-5 models.

This module provides the correct implementation for web search using
the OpenAI Agents SDK's built-in WebSearchTool.

Status: Production
Created: January 2025
"""

import logging
from typing import Optional
from agents import WebSearchTool

logger = logging.getLogger(__name__)


def get_web_search_tool():
    """
    Get the native OpenAI WebSearchTool for use with GPT-5 models.

    This is the correct way to enable web search for GPT-5 models
    using the OpenAI Agents SDK.

    Returns:
        WebSearchTool instance configured for web search
    """
    try:
        # Create and return the native WebSearchTool
        # No configuration needed - it works out of the box with GPT-5
        tool = WebSearchTool()
        logger.info("Native WebSearchTool created successfully for GPT-5")
        return tool
    except Exception as e:
        logger.error(f"Failed to create WebSearchTool: {e}")
        # Fallback to None if WebSearchTool is not available
        return None


def create_fallback_search_tool():
    """
    Create a fallback search tool using Perplexity when WebSearchTool is unavailable.

    This maintains backward compatibility with existing Perplexity implementation.
    """
    try:
        # Import existing Perplexity implementation as fallback
        from core.tools.web_search import web_search as perplexity_search
        logger.info("Using Perplexity fallback for web search")
        return perplexity_search
    except ImportError:
        logger.error("No fallback search tool available")
        return None