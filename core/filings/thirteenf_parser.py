"""
13F SEC Filing XML Parser.

Handles parsing of 13F-HR filings from SEC EDGAR, including:
- Finding infotable.xml in filing index pages
- Parsing XML holdings data
- Generating formatted HTML output
"""

import re
import logging
import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple
from dataclasses import dataclass, asdict
import aiohttp

logger = logging.getLogger(__name__)

SEC_USER_AGENT = "Sentry Investment Intelligence (hello@bcmassets.com)"


@dataclass
class ThirteenFHolding:
    """Single holding from 13F filing."""
    name: str
    title: str
    cusip: str
    value: str
    shares: str
    share_type: str


class ThirteenFParserError(Exception):
    """Error parsing 13F filing."""
    pass


async def find_infotable_url(index_url: str, session: aiohttp.ClientSession) -> str:
    """
    Find the infotable.xml URL from a 13F filing index page.
    
    SEC 13F filings have two versions of infotable.xml:
    1. Raw XML at base path (e.g., /000110465925112514/infotable.xml)
    2. XSL-transformed HTML at xslForm13F_X02 path (not parseable as XML)
    
    We need to find the RAW XML version.
    
    Args:
        index_url: SEC filing index page URL
        session: aiohttp client session
        
    Returns:
        Full URL to infotable.xml (raw XML version)
        
    Raises:
        ThirteenFParserError: If infotable.xml cannot be found
    """
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }
    
    # Extract CIK and accession from URL first to construct direct path
    # This is the most reliable method - avoids XSL-transformed versions
    accession_match = re.search(r'/(\d{10}-\d{2}-\d{6})/', index_url)
    cik_match = re.search(r'/data/(\d+)/', index_url)
    
    if accession_match and cik_match:
        accession = accession_match.group(1).replace("-", "")
        cik = cik_match.group(1)
        # Construct direct URL to raw XML (no XSL transform)
        direct_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/infotable.xml"
        
        # Verify it exists and is actual XML
        try:
            async with session.head(direct_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Using direct infotable.xml URL: {direct_url}")
                    return direct_url
        except Exception as e:
            logger.debug(f"Direct URL check failed: {e}")
    
    # Fallback: Parse the index page
    async with session.get(index_url, headers=headers, timeout=30) as response:
        if response.status != 200:
            raise ThirteenFParserError(f"Failed to fetch SEC filing index: {response.status}")
        index_html = await response.text()
    
    # Extract base URL (without the index filename)
    base_url = "/".join(index_url.rstrip("/").split("/")[:-1])
    if not base_url.endswith("/"):
        base_url += "/"
    
    # Find infotable.xml links, but EXCLUDE xslForm paths (those are XSL-transformed HTML)
    # We want the raw XML, not the transformed version
    xml_pattern = re.compile(r'href="([^"]*infotable\.xml)"', re.IGNORECASE)
    matches = xml_pattern.findall(index_html)
    
    for xml_file in matches:
        # Skip XSL-transformed versions - they return HTML, not XML
        if 'xslForm' in xml_file or 'xsl' in xml_file.lower():
            logger.debug(f"Skipping XSL-transformed URL: {xml_file}")
            continue
        
        if xml_file.startswith("http"):
            return xml_file
        elif xml_file.startswith("/"):
            return f"https://www.sec.gov{xml_file}"
        else:
            return base_url + xml_file
    
    # If we found only XSL versions, try constructing the direct URL
    if accession_match and cik_match:
        accession = accession_match.group(1).replace("-", "")
        cik = cik_match.group(1)
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/infotable.xml"
    
    raise ThirteenFParserError("Could not find raw infotable.xml in 13F filing")


def parse_infotable_xml(xml_content: str) -> List[ThirteenFHolding]:
    """
    Parse infotable.xml content into structured holdings.
    
    Args:
        xml_content: Raw XML string
        
    Returns:
        List of ThirteenFHolding objects
    """
    root = ET.fromstring(xml_content)
    
    # Handle namespace
    ns = {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}
    
    holdings = []
    
    # Try with namespace first, then without
    info_tables = root.findall(".//ns:infoTable", ns)
    if not info_tables:
        info_tables = root.findall(".//infoTable")
    if not info_tables:
        # Try finding any element with infoTable in its name
        for elem in root.iter():
            if "infoTable" in elem.tag.lower():
                info_tables.append(elem)
    
    def get_text(elem: ET.Element, path: str) -> str:
        """Helper to get text from element with namespace fallback."""
        result = elem.find(f"ns:{path}", ns)
        if result is None:
            result = elem.find(path)
        if result is None:
            # Case-insensitive search
            for child in elem:
                if path.lower() in child.tag.lower():
                    return child.text or ""
        return result.text if result is not None else ""
    
    for info in info_tables:
        name = get_text(info, "nameOfIssuer")
        title = get_text(info, "titleOfClass")
        cusip = get_text(info, "cusip")
        value = get_text(info, "value")
        
        # Get shares info - nested structure
        shrs_elem = info.find("ns:shrsOrPrnAmt", ns) or info.find("shrsOrPrnAmt")
        shares = ""
        share_type = ""
        if shrs_elem is not None:
            shares = get_text(shrs_elem, "sshPrnamt") or get_text(shrs_elem, "sshPrnAmt")
            share_type = get_text(shrs_elem, "sshPrnamtType") or get_text(shrs_elem, "sshPrnAmtType")
        
        holdings.append(ThirteenFHolding(
            name=name,
            title=title,
            cusip=cusip,
            value=value,
            shares=shares,
            share_type=share_type,
        ))
    
    return holdings


def holdings_to_html(holdings: List[ThirteenFHolding]) -> str:
    """
    Generate formatted HTML table from holdings.
    
    Args:
        holdings: List of ThirteenFHolding objects
        
    Returns:
        Complete HTML document string
    """
    total_value = sum(int(h.value) * 1000 for h in holdings if h.value.isdigit())
    
    rows_html = ""
    for i, h in enumerate(holdings, 1):
        shares_formatted = f"{int(h.shares):,}" if h.shares.isdigit() else h.shares
        value_formatted = f"{int(h.value):,}" if h.value.isdigit() else h.value
        rows_html += f"""
            <tr>
                <td>{i}</td>
                <td>{h.name}</td>
                <td>{h.title}</td>
                <td class="cusip">{h.cusip}</td>
                <td class="number">{shares_formatted}</td>
                <td class="number">{value_formatted}</td>
            </tr>"""
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 24px;
            background: #fff;
            color: #333;
        }}
        h1 {{
            font-size: 20px;
            font-weight: 600;
            margin: 0 0 8px 0;
        }}
        .summary {{
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #f5f5f5;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e0e0e0;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 8px 12px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .number {{
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}
        .cusip {{
            font-family: monospace;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>13F-HR Information Table</h1>
    <div class="summary">{len(holdings)} holdings | Total Value: ${total_value:,.0f}</div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Name of Issuer</th>
                <th>Title of Class</th>
                <th>CUSIP</th>
                <th class="number">Shares</th>
                <th class="number">Value ($000s)</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>
</body>
</html>"""


async def fetch_and_parse_13f(index_url: str) -> Tuple[List[ThirteenFHolding], str]:
    """
    Fetch and parse a 13F filing from SEC EDGAR.
    
    Args:
        index_url: SEC filing index page URL
        
    Returns:
        Tuple of (holdings list, HTML string)
    """
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }
    
    async with aiohttp.ClientSession() as session:
        # Find the infotable URL
        infotable_url = await find_infotable_url(index_url, session)
        logger.info(f"Fetching 13F infotable from: {infotable_url}")
        
        # Fetch the XML
        async with session.get(infotable_url, headers=headers, timeout=60) as response:
            if response.status != 200:
                raise ThirteenFParserError(f"Failed to fetch infotable.xml: {response.status}")
            xml_content = await response.text()
        
        # Verify it's actually XML, not HTML (XSL-transformed)
        if xml_content.strip().startswith('<!DOCTYPE html') or '<html' in xml_content[:500].lower():
            logger.error(f"Received HTML instead of XML from: {infotable_url}")
            raise ThirteenFParserError("Received XSL-transformed HTML instead of raw XML. URL may be incorrect.")
        
        # Parse holdings
        try:
            holdings = parse_infotable_xml(xml_content)
        except ET.ParseError as e:
            logger.error(f"XML parsing failed for {infotable_url}: {e}")
            logger.debug(f"First 500 chars of content: {xml_content[:500]}")
            raise ThirteenFParserError(f"Failed to parse XML: {e}")
        
        # Generate HTML
        html = holdings_to_html(holdings)
        
        return holdings, html
