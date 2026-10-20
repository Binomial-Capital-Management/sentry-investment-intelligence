"""
SEC Filings API - On-demand filing browser and preview.

Uses FMP for metadata (CIK, accession, dates) and SEC EDGAR for content.
Zero permanent storage - everything fetched on-demand with short-term caching.

Integrations:
- edgartools: Clean filing text/HTML extraction
- weasyprint: HTML to PDF conversion
- sec2md: Markdown conversion
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from typing import Optional, Dict, Any
import aiohttp
import asyncio
import logging
import os
import io
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# Setup logger early for optional import warnings
logger = logging.getLogger(__name__)

# Import refactored modules
from core.filings.cache import get_cache, FilingsCache
from core.filings.sec_edgar import (
    SECEdgarClient, 
    extract_accession_from_url, 
    build_sec_url
)
from core.filings.sanitizer import HTMLSanitizer
from core.filings.form_types import get_form_description
from core.filings.thirteenf_parser import (
    fetch_and_parse_13f,
    ThirteenFParserError,
)

# edgartools for clean filing access
EDGARTOOLS_AVAILABLE = False
try:
    from edgar import Company, set_identity
    set_identity("Sentry Investment Intelligence (hello@bcmassets.com)")
    EDGARTOOLS_AVAILABLE = True
except (ImportError, Exception) as e:
    logger.warning(f"edgartools not available: {e}")

# weasyprint for PDF generation (requires pango system library)
# Install on macOS: brew install pango
WEASYPRINT_AVAILABLE = False
HTML = None
CSS = None
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"weasyprint not available (install pango: brew install pango): {e}")

# sec2md for clean Markdown conversion
SEC2MD_AVAILABLE = False
try:
    import sec2md
    SEC2MD_AVAILABLE = True
except ImportError:
    pass

# Thread pool for CPU-bound PDF generation
_pdf_executor = ThreadPoolExecutor(max_workers=2)

router = APIRouter(prefix="/api/filings", tags=["filings"])

# Configuration
FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com"

# Shared instances
_cache = get_cache()
_sanitizer = HTMLSanitizer()
_sec_client = SECEdgarClient()


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/list")
async def list_filings(
    symbol: str = Query(..., description="Stock ticker symbol (e.g., AAPL)"),
    form_type: Optional[str] = Query(None, description="Filter by form type: 10-K, 10-Q, 8-K"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
) -> Dict[str, Any]:
    """List SEC filings for a symbol using FMP API."""
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    symbol = symbol.upper().strip()
    
    # Check cache
    cache_key = f"filings:list:{symbol}:{form_type}:{from_date}:{to_date}:{limit}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for filings list: {symbol}")
        return cached
    
    # Default date range (3 years)
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if not from_date:
        from_date = (datetime.now() - timedelta(days=3*365)).strftime("%Y-%m-%d")
    
    # Fetch from FMP
    filings = await _fetch_fmp_filings(symbol, from_date, to_date, limit, form_type)
    
    result = {
        "symbol": symbol,
        "count": len(filings),
        "from_date": from_date,
        "to_date": to_date,
        "filings": filings[:limit],
    }
    
    _cache.set(cache_key, result, FilingsCache.METADATA_TTL)
    return result


@router.delete("/cache")
async def clear_cache():
    """Clear all filings cache."""
    size_before = _cache.size()
    _cache.clear()
    return {"cleared": size_before, "message": f"Cleared {size_before} cached items"}


@router.get("/preview")
async def preview_filing(
    cik: str = Query("", description="SEC CIK number"),
    accession: str = Query("", description="Accession number"),
    filename: Optional[str] = Query(None, description="Specific filename"),
    link: Optional[str] = Query(None, description="Direct link (preferred)"),
) -> HTMLResponse:
    """Proxy SEC EDGAR filing content for preview."""
    cache_key = f"filings:preview:{link or f'{cik}:{accession}'}:{filename or 'auto'}"
    
    if cached := _cache.get(cache_key):
        logger.info("Cache hit for filing preview")
        return HTMLResponse(content=cached, media_type="text/html")
    
    # Resolve filing URL
    filing_url, base_url = await _resolve_filing_url(link, cik, accession, filename)
    
    if not filing_url:
        raise HTTPException(status_code=400, detail="Need 'link' or valid 'cik' and 'accession'")
    
    # Fetch and sanitize
    try:
        content = await _sec_client.fetch_filing(filing_url)
        safe_html = _sanitizer.sanitize(content, base_url or "/".join(filing_url.split("/")[:-1]))
    except Exception as e:
        logger.error(f"SEC EDGAR fetch failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch from SEC EDGAR")
    
    _cache.set(cache_key, safe_html, FilingsCache.CONTENT_TTL)
    
    return HTMLResponse(
        content=safe_html,
        media_type="text/html",
        headers={"Cache-Control": f"public, max-age={FilingsCache.CONTENT_TTL}"}
    )


@router.get("/preview-markdown")
async def preview_filing_markdown(
    link: Optional[str] = Query(None, description="Direct link to the filing"),
    cik: str = Query("", description="SEC CIK number"),
    accession: str = Query("", description="Accession number"),
) -> JSONResponse:
    """Convert SEC filing to clean Markdown using sec2md."""
    if not SEC2MD_AVAILABLE:
        raise HTTPException(status_code=501, detail="sec2md not installed")
    
    cache_key = f"filings:markdown:{link or f'{cik}:{accession}'}"
    
    if cached := _cache.get(cache_key):
        logger.info("Cache hit for Markdown preview")
        return JSONResponse(content=cached)
    
    # Resolve filing URL
    filing_url, _ = await _resolve_filing_url(link, cik, accession)
    
    if not filing_url:
        raise HTTPException(status_code=400, detail="Need 'link' or 'cik' and 'accession'")
    
    try:
        logger.info(f"Converting to Markdown: {filing_url}")
        user_agent = "Sentry Investment Intelligence (hello@bcmassets.com)"
        
        # Get pages and full markdown
        pages = sec2md.convert_to_markdown(filing_url, user_agent=user_agent, return_pages=True)
        full_markdown = sec2md.convert_to_markdown(filing_url, user_agent=user_agent, return_pages=False)
        
        result = {
            "markdown": full_markdown,
            "pages": [
                {"page": getattr(p, 'page', i + 1), "content": getattr(p, 'content', str(p))}
                for i, p in enumerate(pages or [])
            ],
            "total_pages": len(pages) if pages else 1,
            "source_url": filing_url,
        }
        
        _cache.set(cache_key, result, FilingsCache.CONTENT_TTL)
        return JSONResponse(content=result, headers={"Cache-Control": f"public, max-age={FilingsCache.CONTENT_TTL}"})
        
    except Exception as e:
        logger.error(f"sec2md conversion failed: {e}")
        raise HTTPException(status_code=502, detail=f"Markdown conversion failed: {str(e)}")


@router.get("/index")
async def get_filing_index(
    cik: str = Query(..., description="SEC CIK number"),
    accession: str = Query(..., description="Accession number"),
) -> Dict[str, Any]:
    """Get the file index for a specific filing."""
    cik_clean = cik.lstrip("0")
    accession_clean = accession.replace("-", "")
    
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/index.json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                index_url, 
                headers={"User-Agent": "Sentry Investment Intelligence (hello@bcmassets.com)"}, 
                timeout=30
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Could not fetch filing index")
                data = await response.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch filing index: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch filing index")
    
    files = [
        {
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "size": item.get("size", ""),
            "lastModified": item.get("last-modified", ""),
        }
        for item in data.get("directory", {}).get("item", [])
    ]
    
    return {
        "cik": cik,
        "accession": accession,
        "files": files,
        "base_url": f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}",
    }


# =============================================================================
# Earnings Transcripts Endpoints
# =============================================================================

@router.get("/transcripts")
async def list_transcripts(
    symbol: str = Query(..., description="Stock ticker symbol (e.g., AAPL)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
) -> Dict[str, Any]:
    """
    List available earnings call transcripts for a symbol.
    
    Returns list of available transcript dates (year/quarter combinations).
    """
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    symbol = symbol.upper().strip()
    
    # Check cache
    cache_key = f"transcripts:list:{symbol}:{limit}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for transcripts list: {symbol}")
        return cached
    
    # Fetch from FMP - correct endpoint is earning-call-transcript-dates
    url = f"{FMP_BASE_URL}/stable/earning-call-transcript-dates"
    params = {
        "symbol": symbol,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP transcripts API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="FMP API timeout")
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    # Log raw response for debugging
    logger.info(f"FMP transcripts raw response for {symbol}: {data[:2] if isinstance(data, list) and data else data}")
    
    # Transform response - FMP may return different field structures
    transcripts = []
    for item in data if isinstance(data, list) else []:
        # FMP response has: symbol, quarter, year, date
        year = item.get("year")
        quarter = item.get("quarter")
        date_str = item.get("date", "")
        
        # If year/quarter missing, try to extract from date
        if (year is None or quarter is None) and date_str:
            try:
                from datetime import datetime as dt
                parsed = dt.strptime(date_str[:10], "%Y-%m-%d")
                if year is None:
                    year = parsed.year
                if quarter is None:
                    # Determine quarter from month
                    quarter = (parsed.month - 1) // 3 + 1
            except Exception:
                pass
        
        # Skip if we still don't have year/quarter
        if year is None or quarter is None:
            logger.warning(f"Skipping transcript with missing year/quarter: {item}")
            continue
            
        transcripts.append({
            "symbol": symbol,
            "year": int(year),
            "quarter": int(quarter),
            "date": date_str,
        })
    
    # Sort by date descending (newest first)
    transcripts.sort(key=lambda x: (x.get("year", 0), x.get("quarter", 0)), reverse=True)
    
    result = {
        "symbol": symbol,
        "count": len(transcripts),
        "transcripts": transcripts[:limit],
    }
    
    _cache.set(cache_key, result, FilingsCache.METADATA_TTL)
    return result


@router.get("/transcript")
async def get_transcript(
    symbol: str = Query(..., description="Stock ticker symbol"),
    year: int = Query(..., description="Fiscal year"),
    quarter: int = Query(..., ge=1, le=4, description="Quarter (1-4)"),
) -> Dict[str, Any]:
    """
    Get full earnings call transcript content.
    
    Returns the complete transcript text for a specific earnings call.
    """
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    symbol = symbol.upper().strip()
    
    # Check cache
    cache_key = f"transcript:{symbol}:{year}:{quarter}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for transcript: {symbol} Q{quarter} {year}")
        return cached
    
    # Fetch from FMP
    url = f"{FMP_BASE_URL}/stable/earning-call-transcript"
    params = {
        "symbol": symbol,
        "year": year,
        "quarter": quarter,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=60) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP transcript API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="FMP API timeout")
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    # FMP returns array with single item
    if isinstance(data, list) and len(data) > 0:
        transcript = data[0]
    elif isinstance(data, dict):
        transcript = data
    else:
        raise HTTPException(status_code=404, detail=f"No transcript found for {symbol} Q{quarter} {year}")
    
    result = {
        "symbol": symbol,
        "year": year,
        "quarter": quarter,
        "date": transcript.get("date", ""),
        "content": transcript.get("content", ""),
    }
    
    _cache.set(cache_key, result, FilingsCache.CONTENT_TTL)
    return result


# =============================================================================
# 13F Institutional Holdings Endpoints
# =============================================================================

@router.get("/institutions/latest")
async def get_latest_13f(
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    limit: int = Query(100, ge=1, le=500, description="Results per page"),
) -> Dict[str, Any]:
    """
    Get latest 13F institutional filings.
    
    Returns recent filings with institution info (cik, investorName, etc.)
    Frontend extracts unique institutions for searchable list.
    """
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    # Check cache
    cache_key = f"institutions:latest:{page}:{limit}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for institutions latest: page {page}")
        return cached
    
    # Fetch from FMP
    url = f"{FMP_BASE_URL}/stable/institutional-ownership/latest"
    params = {
        "page": page,
        "limit": limit,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP institutional API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="FMP API timeout")
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    # Transform response
    filings = []
    for item in data if isinstance(data, list) else []:
        filings.append({
            "cik": item.get("cik", ""),
            "investorName": item.get("investorName", ""),
            "filingDate": item.get("filingDate", ""),
            "totalValue": item.get("totalValue", 0),
            "sharesNumber": item.get("sharesNumber", 0),
        })
    
    result = {
        "page": page,
        "limit": limit,
        "count": len(filings),
        "filings": filings,
    }
    
    _cache.set(cache_key, result, FilingsCache.METADATA_TTL)
    return result


@router.get("/institutions/filings")
async def get_institution_filings(
    cik: str = Query(..., description="Institution CIK number"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> Dict[str, Any]:
    """
    Get 13F filing dates for a specific institution.
    
    Returns list of filing dates for the given institution CIK.
    """
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    cik = cik.strip()
    
    # Check cache
    cache_key = f"institutions:filings:{cik}:{limit}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for institution filings: {cik}")
        return cached
    
    # Fetch from FMP
    url = f"{FMP_BASE_URL}/stable/institutional-ownership/dates"
    params = {
        "cik": cik,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP institutional filings API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="FMP API timeout")
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    # Transform response
    filings = []
    for item in data if isinstance(data, list) else []:
        filings.append({
            "date": item.get("date", ""),
            "filingDate": item.get("filingDate", ""),
        })
    
    # Sort by date descending
    filings.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    result = {
        "cik": cik,
        "count": len(filings),
        "filings": filings[:limit],
    }
    
    _cache.set(cache_key, result, FilingsCache.METADATA_TTL)
    return result


@router.get("/institutions/holdings")
async def get_institution_holdings(
    cik: str = Query(..., description="Institution CIK number"),
    year: int = Query(..., description="Filing year"),
    quarter: int = Query(..., ge=1, le=4, description="Quarter (1-4)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum holdings to return"),
) -> Dict[str, Any]:
    """
    Get 13F holdings for a specific institution, year and quarter.
    
    Returns list of stock holdings with shares and value from actual 13F form.
    """
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    cik = cik.strip()
    
    # Check cache
    cache_key = f"institutions:holdings:{cik}:{year}:{quarter}:{limit}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for institution holdings: {cik} Q{quarter} {year}")
        return cached
    
    # Fetch from FMP stable API - actual 13F form extract
    url = f"{FMP_BASE_URL}/stable/institutional-ownership/extract"
    params = {
        "cik": cik,
        "year": year,
        "quarter": quarter,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP 13F extract API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="FMP API timeout")
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    # Calculate total value for weight calculation
    total_value = sum(item.get("value", 0) for item in (data if isinstance(data, list) else []))
    
    # Transform response - sort by value descending
    holdings = []
    sorted_data = sorted((data if isinstance(data, list) else []), key=lambda x: x.get("value", 0), reverse=True)
    for item in sorted_data[:limit]:
        value = item.get("value", 0)
        holdings.append({
            "symbol": item.get("symbol", ""),
            "securityName": item.get("nameOfIssuer", ""),
            "shares": item.get("shares", 0),
            "value": value,
            "weight": value / total_value if total_value > 0 else 0,
            "titleOfClass": item.get("titleOfClass", ""),
            "cusip": item.get("securityCusip", ""),
        })
    
    # Get SEC filing link from first item
    sec_link = ""
    if data and isinstance(data, list) and len(data) > 0:
        sec_link = data[0].get("link", "")
    
    result = {
        "cik": cik,
        "year": year,
        "quarter": quarter,
        "totalValue": total_value,
        "count": len(holdings),
        "holdings": holdings,
        "secLink": sec_link,
    }
    
    _cache.set(cache_key, result, FilingsCache.CONTENT_TTL)
    return result


@router.get("/13f-document")
async def get_13f_document(
    link: str = Query(..., description="SEC filing index URL"),
) -> Response:
    """
    Parse and render a 13F filing document from SEC EDGAR.
    
    Takes the SEC index URL, finds the infotable.xml file, parses it,
    and returns a formatted HTML table of holdings.
    """
    # Cache check
    cache_key = f"13f:document:{link}"
    if cached := _cache.get(cache_key):
        logger.info("Cache hit for 13F document")
        return Response(content=cached, media_type="text/html")
    
    try:
        _, html = await fetch_and_parse_13f(link)
        _cache.set(cache_key, html, FilingsCache.CONTENT_TTL)
        return Response(content=html, media_type="text/html")
        
    except ThirteenFParserError as e:
        logger.error(f"13F parsing error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching 13F document: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch 13F document: {str(e)}")


@router.get("/preview-clean")
async def preview_filing_clean(
    symbol: str = Query(..., description="Stock ticker symbol"),
    form_type: str = Query("10-K", description="Form type (10-K, 10-Q, 8-K)"),
    year: Optional[int] = Query(None, description="Filing year (latest if not specified)"),
    output: str = Query("html", description="Output format: html, text"),
) -> Response:
    """
    Get clean filing content using edgartools.
    
    Much cleaner than raw SEC EDGAR HTML - properly parsed and formatted.
    """
    if not EDGARTOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="edgartools not installed")
    
    cache_key = f"filings:clean:{symbol}:{form_type}:{year}:{output}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for clean preview: {symbol}")
        media_type = "text/html" if output == "html" else "text/plain"
        return Response(content=cached, media_type=media_type)
    
    try:
        # Run edgartools in thread pool (it's sync and does network I/O)
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            _pdf_executor,
            _get_filing_with_edgartools,
            symbol, form_type, year, output
        )
        
        if not content:
            raise HTTPException(status_code=404, detail=f"No {form_type} filing found for {symbol}")
        
        _cache.set(cache_key, content, FilingsCache.CONTENT_TTL)
        
        media_type = "text/html" if output == "html" else "text/plain"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Cache-Control": f"public, max-age={FilingsCache.CONTENT_TTL}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"edgartools fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch filing: {str(e)}")


@router.get("/export-pdf")
async def export_filing_pdf(
    symbol: str = Query(..., description="Stock ticker symbol"),
    form_type: str = Query("10-K", description="Form type (10-K, 10-Q, 8-K)"),
    year: Optional[int] = Query(None, description="Filing year (latest if not specified)"),
) -> Response:
    """
    Export SEC filing as PDF using edgartools + weasyprint.
    
    Combines:
    - edgartools: Clean HTML extraction
    - weasyprint: Professional PDF rendering
    """
    if not EDGARTOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="edgartools not installed")
    if not WEASYPRINT_AVAILABLE:
        raise HTTPException(status_code=501, detail="weasyprint not installed")
    
    cache_key = f"filings:pdf:{symbol}:{form_type}:{year}"
    if cached := _cache.get(cache_key):
        logger.info(f"Cache hit for PDF export: {symbol}")
        filename = f"{symbol}_{form_type}_{year or 'latest'}.pdf"
        return Response(
            content=cached,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    
    try:
        # Get clean HTML from edgartools, then convert to PDF
        loop = asyncio.get_event_loop()
        pdf_bytes = await loop.run_in_executor(
            _pdf_executor,
            _generate_pdf_with_weasyprint,
            symbol, form_type, year
        )
        
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail=f"No {form_type} filing found for {symbol}")
        
        _cache.set(cache_key, pdf_bytes, FilingsCache.CONTENT_TTL)
        
        filename = f"{symbol}_{form_type}_{year or 'latest'}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": f"public, max-age={FilingsCache.CONTENT_TTL}",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"PDF generation failed: {str(e)}")


# =============================================================================
# Helper Functions
# =============================================================================

async def _fetch_fmp_filings(
    symbol: str, 
    from_date: str, 
    to_date: str, 
    limit: int,
    form_type: Optional[str] = None
) -> list:
    """Fetch filings from FMP API."""
    url = f"{FMP_BASE_URL}/stable/sec-filings-search/symbol"
    params = {
        "symbol": symbol,
        "from": from_date,
        "to": to_date,
        "page": 0,
        "limit": limit,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="FMP API timeout")
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    filings = []
    for item in data if isinstance(data, list) else []:
        cik = item.get("cik", "")
        if not cik:
            continue
        
        # Get accession number
        accession = item.get("accessionNumber", "")
        link = item.get("link", "")
        final_link = item.get("finalLink", "")
        
        if final_link and final_link.lower().endswith(('.htm', '.html')) and 'index' not in final_link.lower():
            link = final_link
        
        if not accession and link:
            accession = extract_accession_from_url(link)
        
        filing_type = item.get("type", item.get("formType", ""))
        
        # Apply form type filter
        if form_type and form_type.upper() not in filing_type.upper():
            continue
        
        filings.append({
            "cik": cik,
            "accessionNumber": accession,
            "type": filing_type,
            "filingDate": item.get("fillingDate", item.get("filingDate", "")),
            "acceptedDate": item.get("acceptedDate", ""),
            "link": link,
            "description": get_form_description(filing_type),
        })
    
    # Sort by date descending
    filings.sort(key=lambda x: x.get("filingDate", ""), reverse=True)
    return filings


async def _resolve_filing_url(
    link: Optional[str], 
    cik: str, 
    accession: str, 
    filename: Optional[str] = None
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the filing URL from provided parameters."""
    filing_url = None
    base_url = None
    
    if link:
        # Check if index page or direct document
        is_index = '-index.htm' in link.lower() or 'browse-edgar' in link or not link.lower().endswith(('.htm', '.html'))
        
        if is_index:
            base_url = "/".join(link.rstrip('/').split("/")[:-1]) if link.lower().endswith('.htm') else link.rstrip('/')
            try:
                doc_filename = await _sec_client.find_primary_document(base_url)
                filing_url = f"{base_url}/{doc_filename}" if doc_filename else link
            except Exception as e:
                filing_url = link
        else:
            filing_url = link
            base_url = "/".join(link.split("/")[:-1])
    
    elif cik and accession:
        cik_clean = cik.lstrip("0")
        if not cik_clean:
            raise HTTPException(status_code=400, detail="Invalid CIK")
        
        accession_clean = accession.replace("-", "")
        if len(accession_clean) < 10:
            raise HTTPException(status_code=400, detail="Invalid accession number")
        
        base_url = build_sec_url(cik, accession)
        
        try:
            if not filename:
                filename = await _sec_client.find_primary_document(base_url)
            if filename:
                filing_url = f"{base_url}/{filename}"
        except Exception as e:
            logger.warning(f"Error finding primary document: {e}")
    
    return filing_url, base_url


def _get_filing_with_edgartools(symbol: str, form_type: str, year: Optional[int], output: str) -> Optional[str]:
    """Get filing content using edgartools (sync, runs in thread pool)."""
    try:
        company = Company(symbol)
        filings = company.get_filings(form=form_type)
        
        if not filings or len(filings) == 0:
            return None
        
        # Get specific year or latest
        if year:
            # Filter by year
            for filing in filings:
                if filing.filing_date and filing.filing_date.year == year:
                    target_filing = filing
                    break
            else:
                target_filing = filings[0]  # Fallback to latest
        else:
            target_filing = filings[0]  # Latest
        
        # Get content based on output format
        if output == "text":
            content = target_filing.text()
        else:
            content = target_filing.html()
            if content:
                # Wrap in styled container for better display
                content = _wrap_html_with_styles(content, symbol, form_type, target_filing.filing_date)
        
        return content
        
    except Exception as e:
        logger.error(f"edgartools error for {symbol}: {e}")
        raise


def _generate_pdf_with_weasyprint(symbol: str, form_type: str, year: Optional[int]) -> Optional[bytes]:
    """Generate PDF from filing using edgartools + weasyprint (sync, runs in thread pool)."""
    try:
        # Get clean HTML from edgartools
        html_content = _get_filing_with_edgartools(symbol, form_type, year, "html")
        if not html_content:
            return None
        
        # PDF-specific styling
        pdf_css = CSS(string="""
            @page {
                size: letter;
                margin: 0.75in;
                @top-center {
                    content: string(title);
                    font-size: 9pt;
                    color: #666;
                }
                @bottom-center {
                    content: "Page " counter(page) " of " counter(pages);
                    font-size: 9pt;
                    color: #666;
                }
            }
            body {
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.5;
                color: #1a1a1a;
            }
            h1, h2, h3 {
                page-break-after: avoid;
                color: #111;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                font-size: 9pt;
                page-break-inside: avoid;
            }
            th, td {
                padding: 4px 8px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            th {
                background: #f5f5f5;
                font-weight: 600;
            }
            .header {
                string-set: title content();
            }
        """)
        
        # Generate PDF
        html_doc = HTML(string=html_content)
        pdf_bytes = html_doc.write_pdf(stylesheets=[pdf_css])
        
        return pdf_bytes
        
    except Exception as e:
        logger.error(f"weasyprint error for {symbol}: {e}")
        raise


def _wrap_html_with_styles(html: str, symbol: str, form_type: str, filing_date) -> str:
    """Wrap edgartools HTML with clean styles for display."""
    date_str = filing_date.strftime("%B %d, %Y") if filing_date else ""
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{symbol} {form_type} - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            font-size: 13px;
            line-height: 1.6;
            padding: 24px 32px;
            max-width: 100%;
            color: #1a1a1a;
            background: #fff;
        }}
        h1, h2, h3, h4 {{
            color: #111;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}
        h1 {{ font-size: 1.5em; border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.3em; }}
        h3 {{ font-size: 1.1em; }}
        p {{ margin: 0.75em 0; }}
        table {{
            border-collapse: collapse;
            margin: 1em 0;
            font-size: 12px;
            width: 100%;
        }}
        th, td {{
            padding: 8px 12px;
            border-bottom: 1px solid #eee;
            text-align: left;
        }}
        th {{
            background: #f9f9f9;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }}
        tr:hover td {{ background: #fafafa; }}
        a {{ color: #1976d2; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .filing-header {{
            background: #f5f7fa;
            padding: 16px 20px;
            border-radius: 8px;
            margin-bottom: 24px;
            border-left: 4px solid #1976d2;
        }}
        .filing-header h1 {{
            margin: 0 0 4px 0;
            font-size: 1.3em;
            border: none;
            padding: 0;
        }}
        .filing-header .meta {{
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="filing-header">
        <h1>{symbol} {form_type}</h1>
        <div class="meta">Filed: {date_str}</div>
    </div>
    {html}
</body>
</html>"""
