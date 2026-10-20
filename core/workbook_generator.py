"""
Workbook Generation using OpenAI Code Interpreter
Explicit container management for concurrent, non-blocking exports
"""
from typing import Dict, Any, Optional, List
import logging
import zipfile
import io
from datetime import datetime
from openai import OpenAI, AsyncOpenAI
import os

logger = logging.getLogger(__name__)

# Configuration - no hardcoding
MODEL = "gpt-5.4"  # Fast, cost-effective model for code execution
REASONING_EFFORT = "medium"  # Balanced reasoning for file generation
TEXT_VERBOSITY = "low"  # Minimal text output - files only
TIMEOUT_MS = 420000  # 7 minutes
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}  # Security whitelist


def _get_clients():
    """Lazy-initialize OpenAI clients to avoid import-time failures."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    timeout = TIMEOUT_MS / 1000
    return (
        AsyncOpenAI(api_key=api_key, timeout=timeout),
        OpenAI(api_key=api_key, timeout=timeout)
    )


async def generate_workbook(
    message_id: str,
    content: str,
    extras: Dict[str, Any],
    portfolio: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate Excel/CSV workbook(s) using OpenAI Code Interpreter.
    
    Uses explicit container creation with message_id for:
    - Non-blocking concurrent exports
    - Direct file access without parsing
    - Clean audit trail
    
    Task settings (workbook_type, verbosity, content_instructions) should be
    passed in the 'extras' dict and will be injected as prompt instructions.
    
    Args:
        message_id: Unique message identifier (becomes container name)
        content: Message content to structure into workbook
        extras: Additional data (metrics, tables, charts metadata, task settings)
        portfolio: Optional portfolio holdings data
    
    Returns:
        ZIP file bytes containing generated workbooks
    
    Raises:
        Exception: If generation fails or no valid files produced
    """
    
    # Initialize clients (lazy to avoid import-time failures)
    openai_async_client, openai_sync_client = _get_clients()
    
    container_name = f"workbook_{message_id[:12]}"
    logger.info(f"Starting workbook generation: {container_name}")
    
    # Create explicit container with message_id
    container = openai_sync_client.containers.create(name=container_name)
    container_id = container.id
    logger.info(f"Container created: {container_id}")
    
    try:
        # Build generation prompt (extracts task settings from extras)
        prompt = _build_prompt(content, extras, portfolio, message_id)
        
        # Execute code interpreter with explicit container
        await openai_async_client.responses.create(
            model=MODEL,
            tools=[{
                "type": "code_interpreter",
                "container": container_id  # Explicit - no parsing needed
            }],
            instructions=_get_instructions(),
            input=prompt,
            reasoning={"effort": REASONING_EFFORT},
            text={"verbosity": TEXT_VERBOSITY}
        )
        
        logger.info(f"Code execution completed: {container_id}")
        
        # List files directly from known container
        files_response = openai_sync_client.containers.files.list(container_id)
        
        file_metadata = [
            {
                'file_id': f.id,
                'filename': f.path.split('/')[-1] if f.path else f"file_{f.id}",
                'container_id': container_id
            }
            for f in files_response.data
        ]
        
        if not file_metadata:
            raise Exception("No files generated")
        
        logger.info(f"Found {len(file_metadata)} file(s)")
        
        # Filter to allowed extensions only
        filtered_files = [
            f for f in file_metadata 
            if any(f['filename'].lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)
        ]
        
        if not filtered_files:
            raise Exception("No Excel/CSV files generated")
        
        logger.info(f"Filtered to {len(filtered_files)} workbook file(s)")
        
        # Download and ZIP
        file_contents = _download_files(container_id, filtered_files)
        zip_bytes = _create_zip(file_contents)
        
        logger.info(f"ZIP created: {len(zip_bytes)} bytes")
        return zip_bytes
        
    except Exception as e:
        logger.error(f"Generation failed for {message_id}: {e}")
        raise


def _get_instructions() -> str:
    """System instructions for hedge fund / IB-grade Excel styling."""
    
    return """You are DataExportSpecialist - generate Excel/CSV workbooks with elite hedge-fund / investment-bank polish. Every sheet must look like a pretty IB/HF deliverable from a top-tier desk.

## OUTPUT RULES
- Produce workbook files only (.xlsx or .csv as prompted). Never emit raw tables.
- Print ONLY the absolute file path when finished. No trailing commentary.
- Pandas + openpyxl for Excel, pandas `to_csv()` for CSV.
- Never include client or bank names. Use "Sentry Investment Intelligence" or neutral labels.
- Always include sheet-level titles, footers with data timestamp, and source notes when provided.

## CONTENT FLEXIBILITY
- Follow the requested structure but think like an associate: craft executive Summary tabs, detail tabs, and optional appendix tabs when the data warrants.
- Extract metrics, time series, comps, and scenario tables organically. Avoid rigid templates.
- When multiple analyses are requested, dedicate one worksheet per topic and cross-reference totals in the Summary sheet.

## IB / HEDGE FUND STYLING (MANDATORY)

### Palette & Visual Hierarchy
```
PRIMARY HEADER:   #0F1F3D (deep navy) background, white text
SECONDARY HEADER: #1C3D5A (slate blue) background, white text
ALT ROW FILL:     #F5F7FA (cool gray) for every other row
TOTAL ROW FILL:   #E3ECF6 (ice blue)
BORDERS:          #C7CEDB thin outline for every cell
POSITIVE TEXT:    #0F7B3F (dark green)
NEGATIVE TEXT:    #C41E3A (maroon red)
WARNING TEXT:     #B26B00 (amber) for flags
```

### Typography & Alignment
```
Font:         Calibri
Header font:  11pt bold, center-aligned, white on navy/slate
Body font:    10pt regular
Numbers:      right-aligned with thousands separators
Text:         left-aligned, wrap long commentary cells
Date columns: center-aligned, format DD-MMM-YYYY
```

### Number Formatting Standards
```
Currency:     $#,##0.00;($#,##0.00)
Percentages:  +0.00%;-0.00% (forced +/-)
Multiples:    0.0x
Large ints:   #,##0 (append K/M/B in adjacent text column if > 1,000)
Rates / spreads: 0.0000
NaNs / blanks: display "–" (en dash)
```

### Workbook Polish Checklist
```
- Freeze header row and first column on every sheet with tabular data.
- Auto-fit columns to data width, cap between 8 and 60 characters.
- Apply alternating row shading (white / ALT ROW) starting with row 2.
- Outline every block with thin borders; add double border above total rows.
- Use conditional formatting bars or icon sets for KPI sheets when requested.
- Summaries should include sparklines (if time series provided) or miniature charts.
- Insert a "Prepared for internal analysis only" footer with run timestamp.
- If multiple sheets exist, include a "Contents" table on the Summary sheet with hyperlinks to each tab.
```

## IMPLEMENTATION PATTERN

```python
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime

# 1. Create DataFrame(s) from analysis data
# 2. Write to Excel with pd.ExcelWriter
# 3. Load with openpyxl and apply hedge fund styling

filename = f'/mnt/data/sentry_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

with pd.ExcelWriter(filename, engine='openpyxl') as writer:
    # Write your sheets here based on data
    pass

# Apply professional styling
wb = load_workbook(filename)

# Hedge fund color scheme
primary_header_fill = PatternFill(start_color="0F1F3D", end_color="0F1F3D", fill_type="solid")
secondary_header_fill = PatternFill(start_color="1C3D5A", end_color="1C3D5A", fill_type="solid")
header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
data_font = Font(name="Calibri", size=10, color="000000")
alt_fill = PatternFill(start_color="F5F7FA", end_color="F5F7FA", fill_type="solid")
total_fill = PatternFill(start_color="E3ECF6", end_color="E3ECF6", fill_type="solid")
border = Border(
    left=Side(style='thin', color='C7CEDB'),
    right=Side(style='thin', color='C7CEDB'),
    top=Side(style='thin', color='C7CEDB'),
    bottom=Side(style='thin', color='C7CEDB')
)

for sheet in wb.worksheets:
    # Apply header styling (row 1)
    # Apply alternating row colors (rows 2+)
    # Apply borders to all cells
    # Apply number formats
    # Auto-size columns
    # Freeze top row

wb.save(filename)
print(filename)
```

FOCUS: Institutional investment research aesthetic. Dark, professional, precise.
NO TEXT OUTPUT. ONLY FILE PATH."""


def _build_prompt(
    content: str,
    extras: Dict[str, Any],
    portfolio: Optional[Dict[str, Any]],
    message_id: str,
) -> str:
    """Build generation prompt with data context."""
    
    from datetime import datetime
    
    # Extract task settings from extras (injected by executor)
    workbook_type = extras.get("workbook_type", "excel") if isinstance(extras, dict) else "excel"
    verbosity = extras.get("verbosity", "mid") if isinstance(extras, dict) else "mid"
    content_instructions = extras.get("content_instructions") if isinstance(extras, dict) else None
    
    # Extract key data intelligently - no hardcoding
    has_portfolio = bool(portfolio and isinstance(portfolio, dict) and portfolio.get('holdings'))
    has_metrics = bool(extras and isinstance(extras, dict))
    
    # Build structured context
    format_str = "CSV" if workbook_type == "csv" else "EXCEL"
    context_parts = [
        f"# INSTITUTIONAL {format_str} WORKBOOK GENERATION",
        f"\nExport Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Message ID: {message_id[:12]}",
    ]
    
    # Inject format instructions as HARD PROMPT
    if workbook_type == "csv":
        context_parts.append("""
## OUTPUT FORMAT INSTRUCTIONS
- Generate ONLY .csv files
- Use pandas to_csv() with proper formatting
- Single file focus - one comprehensive CSV
- Plain text format, no styling""")
    else:
        context_parts.append("""
## OUTPUT FORMAT INSTRUCTIONS
- Generate ONLY .xlsx files
- Use pandas + openpyxl for rich formatting
- Multiple sheets allowed - structure intelligently
- Apply hedge fund styling (see below)""")
    
    # Inject verbosity instructions as HARD PROMPT
    verbosity_instructions = {
        "high": """
## VERBOSITY LEVEL: HIGH (Comprehensive Detail)
- Include ALL available metrics and breakdowns
- Create multiple sheets for different data categories
- Add supporting calculations, drill-downs, and intermediate steps
- Include metadata sheet with definitions and sources
- Richer data density - more rows, more columns""",
        "mid": """
## VERBOSITY LEVEL: MID (Balanced)
- Focus on key metrics and essential breakdowns
- 2-4 sheets typical - main analysis + supporting data
- Include important calculations but skip minor intermediates
- Balanced data density - core insights emphasized""",
        "low": """
## VERBOSITY LEVEL: LOW (Executive Summary)
- Single sheet preferred - core insights only
- Top-level metrics and key takeaways
- Minimal supporting data - results-focused
- Lean data density - essential information only"""
    }
    context_parts.append(verbosity_instructions.get(verbosity, verbosity_instructions["mid"]))
    
    # Add user content instructions if provided
    if content_instructions and content_instructions.strip():
        context_parts.append(f"\n## USER CONTENT INSTRUCTIONS\n{content_instructions.strip()}")
    
    # Add data availability
    context_parts.append(f"\n## DATA SOURCES")
    context_parts.append(f"Portfolio Data: {'Available' if has_portfolio else 'Not Available'}")
    context_parts.append(f"Metrics Data: {'Available' if has_metrics else 'Not Available'}")
    
    # Analysis content (truncated intelligently)
    context_parts.append(f"\n## ANALYSIS CONTENT\n{content[:4000]}")
    
    # Metrics context (dynamic fields)
    if has_metrics:
        # Get non-private keys only
        metric_keys = [k for k in extras.keys() if not k.startswith('_')][:20]
        context_parts.append(f"\n## AVAILABLE METRICS\nFields: {', '.join(metric_keys)}")
        context_parts.append(f"Sample data:\n{str(extras)[:2000]}")
    
    # Portfolio context
    if has_portfolio:
        holdings = portfolio.get('holdings', [])
        context_parts.append(f"\n## PORTFOLIO DATA")
        context_parts.append(f"Holdings count: {len(holdings)}")
        context_parts.append(f"Sample:\n{str(holdings[:3])[:1000]}")
    
    # Generation directive
    file_ext = "csv" if workbook_type == "csv" else "xlsx"
    
    if workbook_type == "csv":
        task_steps = f"""

## GENERATION TASK

1. **Extract structured data** from the analysis above:
   - Parse for tables, metrics, comparisons, time series
   - Identify key data points and breakdowns
   - Structure logically ({verbosity} verbosity level - see instructions above)

2. **Quality standards**:
   - Clean, {'lean' if verbosity == 'low' else 'dense'}, professional appearance
   - Numbers aligned right, text aligned left
   - Proper $ and % formatting
   - Institutional investment research quality
   - Use generic branding only (no external company names)

3. **Output**:
   - Save to /mnt/data/sentry_analysis_{{timestamp}}.{file_ext}
   - Print ONLY the file path (no other output)

EXECUTE. Make it look expensive."""
    else:
        task_steps = f"""

## GENERATION TASK

1. **Extract structured data** from the analysis above:
   - Parse for tables, metrics, comparisons, time series
   - Identify key data points and breakdowns
   - Structure logically ({verbosity} verbosity level - see instructions above)

2. **Apply HEDGE FUND STYLING** (mandatory for Excel):
   - Slate blue (#1C3D5A) headers with white bold text
   - Alternating light gray rows (#F7F9FB)
   - Thin gray borders on all cells
   - Professional number formats (see system instructions)
   - Conditional colors: dark green for positive, dark red for negative
   - Auto-sized columns, frozen headers

3. **Quality standards**:
   - Clean, {'lean' if verbosity == 'low' else 'dense'}, professional appearance
   - Numbers aligned right, text aligned left
   - Proper $ and % formatting
   - Institutional investment research quality
   - Use generic branding only (no external company names)

4. **Output**:
   - Save to /mnt/data/sentry_analysis_{{timestamp}}.{file_ext}
   - Print ONLY the file path (no other output)

EXECUTE. Make it look expensive."""
    
    context_parts.append(task_steps)
    
    return "\n".join(context_parts)


def _download_files(
    container_id: str,
    files: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Download files from container using direct HTTP access."""
    
    import httpx
    api_key = os.getenv("OPENAI_API_KEY")
    downloaded = []
    
    for file in files:
        try:
            # Direct HTTP download (same as v6.py router does)
            url = f"https://api.openai.com/v1/containers/{container_id}/files/{file['file_id']}/content"
            
            with httpx.Client(timeout=60.0) as client:
                response = client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "containers=v1"
                    }
                )
                response.raise_for_status()
                content_bytes = response.content
            
            downloaded.append({
                'filename': file['filename'],
                'content': content_bytes,
                'size': len(content_bytes)
            })
            
            logger.info(f"Downloaded: {file['filename']} ({len(content_bytes)} bytes)")
            
        except Exception as e:
            # Log full traceback for debugging
            import traceback
            logger.error(f"Failed to download {file['filename']}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    return downloaded


def _create_zip(files: List[Dict[str, Any]]) -> bytes:
    """Create ZIP archive from files."""
    
    if not files:
        raise Exception("No files to archive")
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.writestr(file['filename'], file['content'])
    
    zip_bytes = zip_buffer.getvalue()
    logger.info(f"ZIP: {len(zip_bytes)} bytes, {len(files)} file(s)")
    
    return zip_bytes
