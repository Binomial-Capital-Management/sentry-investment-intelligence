"""
Response processor to extract structured data from agent responses.

Handles extraction of sources, charts, and other metadata from tool responses.
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def extract_structured_response(raw_response: str) -> Tuple[str, List[Dict], List[Dict]]:
    """
    Extract structured data (sources, charts) from a raw agent response.
    
    Args:
        raw_response: Raw text response from agent
        
    Returns:
        Tuple of (cleaned_content, sources, charts)
    """
    sources = []
    charts = []
    content = raw_response
    
    try:
        # Check if response contains JSON-like structured data
        # Pattern: Look for embedded JSON blocks marked with special tags
        json_pattern = r'<json_data>(.*?)</json_data>'
        json_matches = re.findall(json_pattern, raw_response, re.DOTALL)
        
        for match in json_matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    # Extract sources if present
                    if "sources" in data and isinstance(data["sources"], list):
                        sources.extend(data["sources"])
                    # Extract charts if present
                    if "charts" in data and isinstance(data["charts"], list):
                        charts.extend(data["charts"])
                    # Remove the JSON block from content
                    content = content.replace(f'<json_data>{match}</json_data>', '')
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse embedded JSON: {match[:100]}...")
        
        # Alternative: Check for citation patterns like [1], [2], etc.
        # and extract URLs from markdown links
        if not sources:
            sources = extract_markdown_sources(content)
        
    except Exception as e:
        logger.error(f"Error extracting structured response: {e}")
    
    return content.strip(), sources, charts


def extract_markdown_sources(content: str) -> List[Dict[str, Any]]:
    """
    Extract sources from markdown-formatted content.
    
    Looks for patterns like:
    - [Title](URL)
    - **[1]** [Title](URL)
    - ### Sources Referenced
    """
    sources = []
    
    try:
        # Pattern for markdown links with optional index
        # Matches: [1] [Title](URL) or just [Title](URL)
        link_pattern = r'(?:\*?\*?\[(\d+)\]\*?\*?\s*)?\[([^\]]+)\]\(([^)]+)\)'
        matches = re.findall(link_pattern, content)
        
        for idx, (num, title, url) in enumerate(matches, 1):
            # Skip internal links (starting with #)
            if url.startswith('#'):
                continue
                
            source = {
                "id": f"source_{num or idx}",
                "title": title.strip(),
                "url": url.strip(),
                "index": int(num) if num else idx
            }
            sources.append(source)
        
        # Also look for snippet patterns (quotes after links)
        snippet_pattern = r'\[([^\]]+)\]\(([^)]+)\)(?:\s*\n\s*>([^\n]+))?'
        snippet_matches = re.findall(snippet_pattern, content)
        
        for match in snippet_matches:
            title, url, snippet = match
            # Find corresponding source and add snippet
            for source in sources:
                if source["url"] == url.strip():
                    if snippet:
                        source["snippet"] = snippet.strip().lstrip('> ')
                    break
        
    except Exception as e:
        logger.error(f"Error extracting markdown sources: {e}")
    
    return sources


def format_response_with_sources(content: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Format a response with properly structured sources for the frontend.
    
    Args:
        content: Main response content
        sources: List of source dictionaries
        
    Returns:
        Formatted response dictionary
    """
    # Ensure each source has required fields
    formatted_sources = []
    for idx, source in enumerate(sources, 1):
        formatted_source = {
            "id": source.get("id", f"source_{idx}"),
            "title": source.get("title", f"Source {idx}"),
            "url": source.get("url", ""),
            "snippet": source.get("snippet", ""),
            "score": source.get("score", 0.9),
            "domain": source.get("domain", ""),
            "index": source.get("index", idx)
        }
        formatted_sources.append(formatted_source)
    
    return {
        "content": content,
        "sources": formatted_sources,
        "has_sources": len(formatted_sources) > 0
    }


def merge_tool_responses(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple tool responses into a single structured response.

    Useful when multiple tools are called in parallel.
    """
    merged_content = []
    all_sources = []
    all_charts = []

    for response in responses:
        if isinstance(response, dict):
            # Extract content
            content = response.get("content", response.get("response", ""))
            if content:
                merged_content.append(content)

            # Extract sources
            sources = response.get("sources", [])
            if sources:
                all_sources.extend(sources)

            # Extract charts
            charts = response.get("charts", [])
            if charts:
                all_charts.extend(charts)
        elif isinstance(response, str):
            merged_content.append(response)

    # Deduplicate sources by URL
    unique_sources = {}
    for source in all_sources:
        url = source.get("url", "")
        if url and url not in unique_sources:
            unique_sources[url] = source

    return {
        "content": "\n\n".join(merged_content),
        "sources": list(unique_sources.values()),
        "charts": all_charts
    }


def extract_charts_from_tool_output(output_obj: Dict[str, Any]) -> tuple[List[Dict], List[Dict]]:
    """
    Extract charts from tool output, separating lightweight references from full chart data.

    Args:
        output_obj: Tool output dictionary

    Returns:
        Tuple of (chart_references, full_charts)
        - chart_references: Lightweight chart metadata for agent context
        - full_charts: Complete chart data with Plotly dictionaries for storage
    """
    chart_refs = []
    full_charts = []

    # Check for _full_charts (new pattern for large charts)
    if isinstance(output_obj.get('_full_charts'), list):
        full_charts = output_obj['_full_charts']
        logger.info(f"[CHART EXTRACT] Found {len(full_charts)} full charts in _full_charts")

    # Check for charts (could be references or full charts)
    if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
        charts = output_obj['charts']

        for chart in charts:
            if isinstance(chart, dict):
                # Check if it's a full chart (has plotly field) or a reference
                if 'plotly' in chart:
                    # Full chart - add to both lists
                    full_charts.append(chart)
                    chart_refs.append({
                        'id': chart.get('id'),
                        'title': chart.get('title'),
                        'type': chart.get('type', 'unknown')
                    })
                else:
                    # Already a reference - just use it
                    chart_refs.append(chart)

        logger.info(f"[CHART EXTRACT] Extracted {len(chart_refs)} chart references, {len(full_charts)} full charts")

    # If single chart object (not in array)
    elif all(k in output_obj for k in ("id", "plotly")):
        full_charts.append(output_obj)
        chart_refs.append({
            'id': output_obj.get('id'),
            'title': output_obj.get('title'),
            'type': output_obj.get('type', 'unknown')
        })
        logger.info("[CHART EXTRACT] Extracted single chart object")

    return chart_refs, full_charts