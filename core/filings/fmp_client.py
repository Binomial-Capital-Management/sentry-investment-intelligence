"""
FMP (Financial Modeling Prep) API client for filings data.

Handles all FMP API interactions for SEC filings, transcripts, and institutional holdings.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp

from .form_types import get_form_description
from .sec_edgar import extract_accession_from_url

logger = logging.getLogger(__name__)

FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com"


class FMPError(Exception):
    """FMP API error."""
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"FMP API error ({status}): {message}")


@dataclass
class FMPFiling:
    """Structured SEC filing from FMP."""
    cik: str
    accession_number: str
    form_type: str
    filing_date: str
    accepted_date: str
    link: str
    description: str


@dataclass
class FMPTranscript:
    """Structured earnings transcript from FMP."""
    symbol: str
    year: int
    quarter: int
    date: str


@dataclass
class FMPHolding:
    """Structured 13F holding from FMP."""
    symbol: str
    security_name: str
    shares: int
    value: int
    weight: float
    title_of_class: str
    cusip: str


class FMPClient:
    """Async client for FMP API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FMP_API_KEY
        if not self.api_key:
            raise ValueError("FMP_API_KEY not configured")
    
    async def _request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Any:
        """Make authenticated request to FMP API."""
        url = f"{FMP_BASE_URL}/{endpoint}"
        params = params or {}
        params["apikey"] = self.api_key
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"FMP API error: {response.status} - {error_text[:200]}")
                        raise FMPError(response.status, error_text[:200])
                    return await response.json()
        except asyncio.TimeoutError:
            raise FMPError(504, "FMP API timeout")
        except aiohttp.ClientError as e:
            logger.error(f"FMP connection error: {e}")
            raise FMPError(502, f"Failed to connect to FMP API: {str(e)}")
    
    # =========================================================================
    # SEC Filings
    # =========================================================================
    
    async def list_filings(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        limit: int = 50,
        form_type: Optional[str] = None
    ) -> List[FMPFiling]:
        """List SEC filings for a symbol."""
        data = await self._request(
            "stable/sec-filings-search/symbol",
            {
                "symbol": symbol.upper().strip(),
                "from": from_date,
                "to": to_date,
                "page": 0,
                "limit": limit,
            }
        )
        
        filings = []
        for item in (data if isinstance(data, list) else []):
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
            
            filings.append(FMPFiling(
                cik=cik,
                accession_number=accession,
                form_type=filing_type,
                filing_date=item.get("fillingDate", item.get("filingDate", "")),
                accepted_date=item.get("acceptedDate", ""),
                link=link,
                description=get_form_description(filing_type),
            ))
        
        # Sort by date descending
        filings.sort(key=lambda x: x.filing_date, reverse=True)
        return filings
    
    # =========================================================================
    # Earnings Transcripts
    # =========================================================================
    
    async def list_transcripts(
        self,
        symbol: str,
        limit: int = 20
    ) -> List[FMPTranscript]:
        """List available earnings call transcripts for a symbol."""
        data = await self._request(
            "stable/earning-call-transcript-dates",
            {"symbol": symbol.upper().strip()}
        )
        
        transcripts = []
        for item in (data if isinstance(data, list) else []):
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
                        quarter = (parsed.month - 1) // 3 + 1
                except Exception:
                    pass
            
            if year is None or quarter is None:
                logger.warning(f"Skipping transcript with missing year/quarter: {item}")
                continue
            
            transcripts.append(FMPTranscript(
                symbol=symbol.upper(),
                year=int(year),
                quarter=int(quarter),
                date=date_str,
            ))
        
        # Sort by date descending
        transcripts.sort(key=lambda x: (x.year, x.quarter), reverse=True)
        return transcripts[:limit]
    
    async def get_transcript(
        self,
        symbol: str,
        year: int,
        quarter: int
    ) -> Dict[str, Any]:
        """Get full earnings call transcript content."""
        data = await self._request(
            "stable/earning-call-transcript",
            {
                "symbol": symbol.upper().strip(),
                "year": year,
                "quarter": quarter,
            },
            timeout=60
        )
        
        if isinstance(data, list) and len(data) > 0:
            transcript = data[0]
        elif isinstance(data, dict):
            transcript = data
        else:
            raise FMPError(404, f"No transcript found for {symbol} Q{quarter} {year}")
        
        return {
            "symbol": symbol.upper(),
            "year": year,
            "quarter": quarter,
            "date": transcript.get("date", ""),
            "content": transcript.get("content", ""),
        }
    
    # =========================================================================
    # 13F Institutional Holdings
    # =========================================================================
    
    async def get_latest_institutions(
        self,
        page: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get latest 13F institutional filings."""
        data = await self._request(
            "stable/institutional-ownership/latest",
            {"page": page, "limit": limit}
        )
        
        filings = []
        for item in (data if isinstance(data, list) else []):
            filings.append({
                "cik": item.get("cik", ""),
                "investorName": item.get("investorName", ""),
                "filingDate": item.get("filingDate", ""),
                "totalValue": item.get("totalValue", 0),
                "sharesNumber": item.get("sharesNumber", 0),
            })
        
        return filings
    
    async def get_institution_filing_dates(
        self,
        cik: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """Get 13F filing dates for a specific institution."""
        data = await self._request(
            "stable/institutional-ownership/dates",
            {"cik": cik.strip()}
        )
        
        filings = []
        for item in (data if isinstance(data, list) else []):
            filings.append({
                "date": item.get("date", ""),
                "filingDate": item.get("filingDate", ""),
            })
        
        # Sort by date descending
        filings.sort(key=lambda x: x.get("date", ""), reverse=True)
        return filings[:limit]
    
    async def get_institution_holdings(
        self,
        cik: str,
        year: int,
        quarter: int,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get 13F holdings for a specific institution, year and quarter."""
        data = await self._request(
            "stable/institutional-ownership/extract",
            {"cik": cik.strip(), "year": year, "quarter": quarter}
        )
        
        # Calculate total value for weight calculation
        total_value = sum(item.get("value", 0) for item in (data if isinstance(data, list) else []))
        
        # Transform and sort by value descending
        holdings = []
        sorted_data = sorted((data if isinstance(data, list) else []), key=lambda x: x.get("value", 0), reverse=True)
        
        for item in sorted_data[:limit]:
            value = item.get("value", 0)
            holdings.append(FMPHolding(
                symbol=item.get("symbol", ""),
                security_name=item.get("nameOfIssuer", ""),
                shares=item.get("shares", 0),
                value=value,
                weight=value / total_value if total_value > 0 else 0,
                title_of_class=item.get("titleOfClass", ""),
                cusip=item.get("securityCusip", ""),
            ))
        
        # Get SEC filing link from first item
        sec_link = ""
        if data and isinstance(data, list) and len(data) > 0:
            sec_link = data[0].get("link", "")
        
        return {
            "cik": cik,
            "year": year,
            "quarter": quarter,
            "total_value": total_value,
            "count": len(holdings),
            "holdings": holdings,
            "sec_link": sec_link,
        }


# Singleton instance
_client: Optional[FMPClient] = None


def get_fmp_client() -> FMPClient:
    """Get or create FMP client singleton."""
    global _client
    if _client is None:
        _client = FMPClient()
    return _client
