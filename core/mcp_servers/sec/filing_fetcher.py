"""
SEC Filing fetcher and parser
Handles EDGAR API interactions and filing text processing
"""

import asyncio
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FilingFetcher:
    """Fetches and parses SEC filings from EDGAR"""
    
    def __init__(self, user_agent: str):
        """
        Initialize filing fetcher
        
        Args:
            user_agent: SEC-required user agent string with email
        """
        self.user_agent = user_agent
    
    async def fetch_filing(self, ticker: str, filing_type: str):
        """Fetch filing from EDGAR (async wrapper) with robust identifier handling"""
        def sync_fetch():
            try:
                from edgar import Company, set_identity
                
                # Set User-Agent as required by SEC
                set_identity(self.user_agent)
                
                # Accept ticker, CIK, or company name. If name, resolve to ticker when possible.
                company = Company(ticker)
                
                # Handle different filing type requests
                if filing_type == "latest":
                    # Get latest FINANCIAL filing (not ownership reports)
                    financial_forms = ['10-K', '10-Q', '20-F', '6-K', '8-K', '10-K/A', '10-Q/A', '20-F/A']
                    all_financial_filings = []
                    
                    for form in financial_forms:
                        form_filings = company.get_filings(form=form)
                        if form_filings:
                            all_financial_filings.extend(form_filings)
                    
                    # Sort by filing date to get most recent
                    if all_financial_filings:
                        filings = sorted(all_financial_filings, 
                                       key=lambda x: x.filing_date, 
                                       reverse=True)
                    else:
                        # Fallback to any filing if no financial filings found
                        filings = company.get_filings()
                else:
                    filings = company.get_filings(form=filing_type)  # Get specific form type
                
                if not filings or len(filings) == 0:
                    # Fallback: if constructed by name and tickers are available, retry with first ticker
                    try:
                        tickers = getattr(company, 'tickers', []) or []
                        if tickers:
                            company = Company(tickers[0])
                            filings = company.get_filings(form=filing_type if filing_type != "latest" else None)
                    except Exception:
                        pass
                if not filings or len(filings) == 0:
                    raise ValueError(f"No {filing_type} filings found for {ticker}")
                
                # Get the most recent filing
                return filings[0]
                
            except ImportError:
                raise ImportError("edgartools not installed. Run: pip install edgartools")
            except Exception as e:
                raise ValueError(f"Failed to fetch filing: {str(e)}")
        
        # Run sync code in thread pool
        return await asyncio.to_thread(sync_fetch)
    
    async def resolve_filing_meta(self, company: str, filing_type: str = "latest") -> Dict:
        """Resolve company identifier (ticker/CIK/name) to filing metadata with comprehensive fallbacks"""
        def sync_resolve():
            try:
                from edgar import Company, set_identity, find
                set_identity(self.user_agent)

                company_obj = None
                search_attempts = []

                # Attempt 1: Direct lookup (ticker/CIK/name)
                try:
                    company_obj = Company(company)
                    search_attempts.append(f"direct:{company}")
                    logger.debug(f"✓ Direct lookup succeeded for '{company}'")
                except Exception as e:
                    logger.debug(f"✗ Direct lookup failed for '{company}': {e}")

                # Attempt 2: Search by name/ticker using edgar.find() if direct failed
                if not company_obj or not hasattr(company_obj, 'get_filings'):
                    try:
                        logger.debug(f"Attempting search lookup for '{company}'...")
                        search_results = find(company)
                        if search_results:
                            # Try first result
                            first_result = search_results[0] if isinstance(search_results, list) else search_results
                            cik = getattr(first_result, 'cik', None)
                            if cik:
                                company_obj = Company(str(cik).lstrip('0'))
                                search_attempts.append(f"search:{cik}")
                                logger.debug(f"✓ Search lookup succeeded with CIK {cik}")
                    except Exception as e:
                        logger.debug(f"✗ Search lookup failed for '{company}': {e}")

                # Attempt 3: Try with leading zeros stripped (common CIK issue)
                if not company_obj and company.isdigit():
                    try:
                        stripped_cik = str(int(company))
                        logger.debug(f"Attempting CIK (stripped) lookup: {stripped_cik}...")
                        company_obj = Company(stripped_cik)
                        search_attempts.append(f"cik_stripped:{stripped_cik}")
                        logger.debug(f"✓ CIK (stripped) lookup succeeded")
                    except Exception as e:
                        logger.debug(f"✗ CIK (stripped) lookup failed: {e}")

                # Attempt 4: Try with leading zeros added (SEC CIK format)
                if not company_obj and company.isdigit() and len(company) < 10:
                    try:
                        padded_cik = company.zfill(10)
                        logger.debug(f"Attempting CIK (padded) lookup: {padded_cik}...")
                        company_obj = Company(padded_cik)
                        search_attempts.append(f"cik_padded:{padded_cik}")
                        logger.debug(f"✓ CIK (padded) lookup succeeded")
                    except Exception as e:
                        logger.debug(f"✗ CIK (padded) lookup failed: {e}")

                if not company_obj:
                    error_msg = f"Could not resolve company identifier '{company}'. Tried: {', '.join(search_attempts)}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Get the appropriate filings
                if filing_type == "latest":
                    # Get latest FINANCIAL filing (not ownership reports)
                    financial_forms = ['10-K', '10-Q', '20-F', '6-K', '8-K', '10-K/A', '10-Q/A', '20-F/A']
                    all_financial_filings = []

                    for form in financial_forms:
                        form_filings = company_obj.get_filings(form=form)
                        if form_filings:
                            all_financial_filings.extend(form_filings)

                    # Sort by filing date to get most recent
                    if all_financial_filings:
                        filings = sorted(all_financial_filings,
                                       key=lambda x: x.filing_date,
                                       reverse=True)
                    else:
                        # Fallback to any filing if no financial filings found
                        filings = company_obj.get_filings()
                else:
                    # Get specific filing type
                    filings = company_obj.get_filings(form=filing_type)

                if not filings or len(filings) == 0:
                    # Fallback: if initialized by name, try first discovered ticker
                    try:
                        tickers = getattr(company_obj, 'tickers', []) or []
                        if tickers:
                            logger.debug(f"No filings found, trying ticker fallback: {tickers[0]}")
                            company_obj = Company(tickers[0])
                            if filing_type == "latest":
                                financial_forms = ['10-K', '10-Q', '20-F', '6-K', '8-K', '10-K/A', '10-Q/A', '20-F/A']
                                all_financial_filings = []
                                for form in financial_forms:
                                    form_filings = company_obj.get_filings(form=form)
                                    if form_filings:
                                        all_financial_filings.extend(form_filings)
                                filings = (sorted(all_financial_filings, key=lambda x: x.filing_date, reverse=True)
                                           if all_financial_filings else company_obj.get_filings())
                            else:
                                filings = company_obj.get_filings(form=filing_type)
                    except Exception as e:
                        logger.debug(f"Ticker fallback failed: {e}")

                if not filings or len(filings) == 0:
                    error_msg = f"No {filing_type} filings found for {company}. Company resolved successfully but no filings available."
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                filing = filings[0]
                logger.info(f"Successfully resolved {company} → {filing.form} filed on {filing.filing_date}")

                return {
                    'accession_number': filing.accession_number,
                    'filing_date': filing.filing_date,
                    'filing_url': filing.url,
                    'filing_type': filing.form,
                    'company_name': company_obj.name,
                    'ticker': (company_obj.tickers[0] if getattr(company_obj, 'tickers', None) else company),
                    'cik': getattr(company_obj, 'cik', None)
                }
            except Exception as e:
                logger.error(f"Failed to resolve filing for '{company}': {str(e)}")
                raise ValueError(f"Failed to resolve filing: {str(e)}")

        return await asyncio.to_thread(sync_resolve)
    
    def parse_sections(self, text: str, max_preview: int = 500) -> List[Dict]:
        """Parse filing text into sections with previews"""
        sections = []
        
        # Common SEC filing section patterns
        section_patterns = [
            r'(Item|ITEM|Part|PART)\s+\d+[A-Z]?\.?\s*[^\n]{0,100}',
            r'(RISK FACTORS|BUSINESS|MANAGEMENT|FINANCIAL|LEGAL)\s*[^\n]{0,50}'
        ]
        
        for pattern in section_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = match.start()
                # Get preview text after section header
                preview_start = match.end()
                preview_end = min(preview_start + max_preview, len(text))
                preview = text[preview_start:preview_end].strip()
                
                if preview:  # Only add if there's content
                    sections.append({
                        'section_name': match.group().strip(),
                        'preview': preview,
                        'position': start
                    })
        
        # If no sections found, create a default one
        if not sections:
            sections.append({
                'section_name': 'DOCUMENT',
                'preview': text[:max_preview].strip(),
                'position': 0
            })
        
        return sections[:12]  # Limit to first 12 sections