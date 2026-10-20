"""
SEC Filings module - On-demand filing browser and preview.

Uses FMP for metadata and SEC EDGAR for content.
Zero permanent storage - everything fetched on-demand with caching.
"""

from .cache import FilingsCache, get_cache
from .sec_edgar import SECEdgarClient, extract_accession_from_url, build_sec_url
from .sanitizer import HTMLSanitizer
from .form_types import get_form_description
from .fmp_client import FMPClient, FMPError, get_fmp_client
from .thirteenf_parser import (
    ThirteenFHolding,
    ThirteenFParserError,
    fetch_and_parse_13f,
    holdings_to_html,
)

__all__ = [
    # Cache
    "FilingsCache",
    "get_cache",
    # SEC EDGAR
    "SECEdgarClient",
    "extract_accession_from_url",
    "build_sec_url",
    # HTML
    "HTMLSanitizer",
    # Form types
    "get_form_description",
    # FMP client
    "FMPClient",
    "FMPError",
    "get_fmp_client",
    # 13F parser
    "ThirteenFHolding",
    "ThirteenFParserError",
    "fetch_and_parse_13f",
    "holdings_to_html",
]
