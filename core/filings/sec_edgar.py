"""SEC EDGAR client for fetching filing content."""

import re
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# User agent for SEC requests (SEC requires declared contact email)
USER_AGENT = "Sentry Investment Intelligence (hello@bcmassets.com)"


class SECEdgarClient:
    """Client for fetching SEC EDGAR filing content."""
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    
    async def fetch_filing(self, url: str) -> str:
        """Fetch filing content from SEC EDGAR. Converts XML to HTML if needed."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                if response.status != 200:
                    raise SECEdgarError(f"SEC EDGAR returned {response.status}")
                content = await response.text()
                
                # Convert 13F XML to HTML table
                if url.lower().endswith('.xml') and 'holding' in url.lower():
                    return self._convert_13f_xml_to_html(content, url)
                
                return content
    
    def _convert_13f_xml_to_html(self, xml_content: str, source_url: str) -> str:
        """Convert 13F holdings XML to readable HTML table."""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml_content)
            ns = {'ns': 'http://www.sec.gov/edgar/document/thirteenf/informationtable'}
            
            rows = []
            total_value = 0
            total_shares = 0
            
            for info in root.findall('.//ns:infoTable', ns):
                issuer = info.findtext('ns:nameOfIssuer', '', ns)
                title = info.findtext('ns:titleOfClass', '', ns)
                cusip = info.findtext('ns:cusip', '', ns)
                value = int(info.findtext('ns:value', '0', ns) or 0)
                shares_elem = info.find('ns:shrsOrPrnAmt', ns)
                shares = int(shares_elem.findtext('ns:sshPrnamt', '0', ns) or 0) if shares_elem is not None else 0
                
                total_value += value
                total_shares += shares
                
                rows.append({
                    'issuer': issuer,
                    'title': title,
                    'cusip': cusip,
                    'shares': shares,
                    'value': value
                })
            
            # Sort by value descending
            rows.sort(key=lambda x: x['value'], reverse=True)
            
            # Build HTML rows
            html_rows = []
            for r in rows:
                weight = (r['value'] / total_value * 100) if total_value > 0 else 0
                html_rows.append(f'''<tr>
                    <td>{r['issuer']}</td>
                    <td>{r['title']}</td>
                    <td class="mono">{r['cusip']}</td>
                    <td class="num">{r['shares']:,}</td>
                    <td class="num">${r['value']:,}</td>
                    <td class="num">{weight:.2f}%</td>
                </tr>''')
            
            # Extract quarter/year from filename
            filename = source_url.split('/')[-1]
            
            html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>13F Holdings - {filename}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; 
            padding: 24px; 
            background: #fff;
            color: #1a1a1a;
        }}
        .header {{
            border-bottom: 1px solid #e5e5e5;
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        h1 {{ 
            font-size: 20px; 
            font-weight: 600;
            color: #111; 
            margin: 0 0 8px 0;
        }}
        .meta {{ 
            font-size: 13px; 
            color: #666; 
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .meta span {{ display: flex; align-items: center; gap: 6px; }}
        .meta strong {{ color: #333; }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 12px;
        }}
        thead {{ position: sticky; top: 0; }}
        th {{ 
            padding: 10px 12px; 
            text-align: left; 
            background: #f8f9fa; 
            border-bottom: 2px solid #dee2e6; 
            font-weight: 600; 
            color: #495057;
            white-space: nowrap;
        }}
        th.num {{ text-align: right; }}
        td {{
            padding: 8px 12px;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: top;
        }}
        td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        td.mono {{ font-family: 'SF Mono', Monaco, monospace; font-size: 11px; color: #666; }}
        tr:hover {{ background: #fafafa; }}
        .source {{ 
            margin-top: 20px; 
            font-size: 11px; 
            color: #888;
            padding-top: 16px;
            border-top: 1px solid #e5e5e5;
        }}
        .source a {{ color: #0066cc; text-decoration: none; }}
        .source a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Form 13F-HR Holdings Report</h1>
        <div class="meta">
            <span><strong>Holdings:</strong> {len(rows):,}</span>
            <span><strong>Total Value:</strong> ${total_value:,}</span>
            <span><strong>Total Shares:</strong> {total_shares:,}</span>
        </div>
    </div>
    <table>
        <thead>
            <tr>
                <th>Issuer</th>
                <th>Class</th>
                <th>CUSIP</th>
                <th class="num">Shares</th>
                <th class="num">Value ($)</th>
                <th class="num">Weight</th>
            </tr>
        </thead>
        <tbody>
            {''.join(html_rows)}
        </tbody>
    </table>
    <p class="source">Source: <a href="{source_url}" target="_blank">{filename}</a></p>
</body>
</html>'''
            return html
        except Exception as e:
            logger.warning(f"Failed to parse 13F XML: {e}")
            # Return raw XML wrapped in pre tag as fallback
            return f'<html><body><pre>{xml_content}</pre></body></html>'
    
    async def find_primary_document(self, base_url: str) -> Optional[str]:
        """Find the primary document filename from the filing index."""
        # Try index.json first
        index_url = f"{base_url}/index.json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(index_url, headers={"User-Agent": USER_AGENT}, timeout=30) as response:
                    if response.status == 200:
                        # SEC sometimes returns index.json with text/html content-type, so try parsing as JSON regardless
                        try:
                            response_text = await response.text()
                            if response_text.strip().startswith('{'):
                                import json
                                data = json.loads(response_text)
                                result = self._extract_primary_from_json(data)
                                if result:
                                    return result
                        except Exception:
                            pass  # Fall through to HTML fallback
        except Exception as e:
            logger.debug(f"index.json not available: {e}")
        
        # Fallback: parse HTML index page
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, headers={"User-Agent": USER_AGENT}, timeout=30) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_primary_from_html(html)
        except Exception as e:
            logger.warning(f"Failed to fetch filing index HTML: {e}")
        
        return None
    
    def _extract_primary_from_json(self, data: dict) -> Optional[str]:
        """Extract primary document filename from index.json."""
        directory = data.get("directory", {})
        items = directory.get("item", [])
        
        # Priority patterns for primary documents (HTML)
        primary_patterns = [
            r".*-\d{8}\.htm[l]?$",  # ticker-YYYYMMDD.htm
            r".*10-?k.*\.htm[l]?$",
            r".*10-?q.*\.htm[l]?$",
            r".*8-?k.*\.htm[l]?$",
            r".*def.*14a.*\.htm[l]?$",
            r".*holding.*\.htm[l]?$",  # 13F holdings HTML
            r"primary_doc\.htm[l]?$",  # 13F primary doc
        ]
        
        htm_files = []
        xml_files = []
        index_file = None
        skip_patterns = ["ex-", "exhibit", "_g", "graphic", "logo", "-headers"]
        
        for item in items:
            name = item.get("name", "")
            size = int(item.get("size", 0) or 0)
            
            if name.lower().endswith((".htm", ".html")):
                # Save the index.html as fallback for filings without HTML docs
                if name.lower().endswith("-index.html") or name.lower().endswith("-index.htm"):
                    index_file = name
                    continue
                if not any(skip in name.lower() for skip in skip_patterns):
                    htm_files.append({"name": name, "size": size})
            elif name.lower().endswith(".xml"):
                # Also track XML files for 13F filings (holdings data)
                if "holding" in name.lower() and size > 1000:
                    xml_files.append({"name": name, "size": size})
        
        # Try priority patterns first (HTML files)
        for pattern in primary_patterns:
            for f in htm_files:
                if re.match(pattern, f["name"], re.IGNORECASE):
                    return f["name"]
        
        # Fallback: largest HTML file
        if htm_files:
            htm_files.sort(key=lambda x: x["size"], reverse=True)
            return htm_files[0]["name"]
        
        # For 13F: return the XML file - we'll convert it to HTML in fetch_filing
        if xml_files:
            xml_files.sort(key=lambda x: x["size"], reverse=True)
            return xml_files[0]["name"]  # Return XML, will be converted to HTML
        
        # Last resort: return the index.html for filings without primary docs
        return index_file
    
    def _extract_primary_from_html(self, html: str) -> Optional[str]:
        """Extract primary document from HTML index page."""
        patterns = [
            r'href="([^"]+\.htm)"[^>]*>\s*\1\s*</a>.*?10-[KQ]',
            r'href="([a-z]+-\d{8}\.htm)"',
            r'href="([^"]+10[kq][^"]*\.htm)"',
            r'href="([^"]+8-?k[^"]*\.htm)"',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).split('/')[-1]
        
        # Fallback: any .htm not an exhibit
        skip_patterns = ['ex-', 'ex1', 'ex2', 'exhibit', 'graphic', 'logo', 'image', 'index']
        for match in re.finditer(r'href="([^"]+\.htm)"', html, re.IGNORECASE):
            filename = match.group(1).split('/')[-1]
            if not any(skip in filename.lower() for skip in skip_patterns):
                return filename
        
        return None


class SECEdgarError(Exception):
    """SEC EDGAR API error."""
    pass


def extract_accession_from_url(url: str) -> str:
    """Extract accession number from SEC EDGAR URL."""
    if not url:
        return ""
    
    # Pattern: 18-digit folder name
    match = re.search(r'/(\d{18})/', url)
    if match:
        raw = match.group(1)
        return f"{raw[:10]}-{raw[10:12]}-{raw[12:]}"
    
    # Already formatted
    match = re.search(r'(\d{10}-\d{2}-\d{6})', url)
    if match:
        return match.group(1)
    
    return ""


def build_sec_url(cik: str, accession: str, filename: Optional[str] = None) -> str:
    """Build SEC EDGAR URL from CIK and accession."""
    cik_clean = cik.lstrip("0")
    accession_clean = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}"
    return f"{base}/{filename}" if filename else base
