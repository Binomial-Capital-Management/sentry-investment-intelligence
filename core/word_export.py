"""
Simple, unified Word export for institutional-quality reports.
Following KISS principle - one file, clear purpose, no magic numbers.
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os
from datetime import datetime
from typing import Dict, Optional, Any, List
import io

from .constants import (
    WORD_MARGINS, WORD_FONTS, WORD_SIZES, WORD_COLORS,
    LINE_SPACING, PARA_SPACING_AFTER, LOGO_WIDTH, TABLE_STYLE
)


def create_institutional_report(content: Optional[str] = None, 
                              analysis_data: Optional[Dict[str, Any]] = None,
                              logo_path: Optional[str] = None) -> bytes:
    """
    Create institutional-quality Word document for chat or analysis.
    
    Args:
        content: Chat conversation text (markdown formatted)
        analysis_data: Risk analysis results with metrics
        logo_path: Path to company logo
        
    Returns:
        Document as bytes for download
    """
    doc = Document()
    
    # Apply professional document styling
    setup_document_style(doc)
    
    # Add header with logo if available
    if logo_path and os.path.exists(logo_path):
        add_professional_header(doc, logo_path)
    
    # Add title page
    add_title_page(doc)
    
    # Add appropriate content based on type
    if analysis_data and 'risk_metrics' in analysis_data:
        format_risk_report(doc, analysis_data)
    else:
        format_chat_content(doc, content or "")
    
    # Add professional footer
    add_footer(doc)
    
    return save_to_bytes(doc)


def setup_document_style(doc: Document) -> None:
    """Apply institutional styling to document."""
    # Set margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(WORD_MARGINS['top'])
        section.bottom_margin = Inches(WORD_MARGINS['bottom'])
        section.left_margin = Inches(WORD_MARGINS['left'])
        section.right_margin = Inches(WORD_MARGINS['right'])
    
    # Set default font for entire document
    style = doc.styles['Normal']
    style.font.name = WORD_FONTS['primary']
    style.font.size = Pt(WORD_SIZES['body'])
    style.paragraph_format.line_spacing = LINE_SPACING
    style.paragraph_format.space_after = Pt(PARA_SPACING_AFTER)
    
    # Apply to all heading styles too
    for i in range(1, 4):
        try:
            heading_style = doc.styles[f'Heading {i}']
            heading_style.font.name = WORD_FONTS['primary']
            heading_style.paragraph_format.line_spacing = LINE_SPACING
        except:
            pass


def add_professional_header(doc: Document, logo_path: str) -> None:
    """Add header with company logo."""
    header = doc.sections[0].header
    header_para = header.paragraphs[0]
    header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    try:
        run = header_para.add_run()
        run.add_picture(logo_path, width=Inches(LOGO_WIDTH))
    except Exception:
        # If logo fails, add text fallback
        header_para.text = "BINOMIAL"
        header_para.runs[0].font.name = WORD_FONTS['primary']
        header_para.runs[0].font.size = Pt(WORD_SIZES['heading2'])
        header_para.runs[0].font.color.rgb = RGBColor(*WORD_COLORS['binomial_blue'])
        header_para.runs[0].font.bold = True


def add_title_page(doc: Document) -> None:
    """Add professional title page."""
    # Main title
    title = doc.add_heading('Binomial Risk Analysis Report', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    format_heading(title, 'title', 'heading_blue')
    
    # Date
    date_para = doc.add_paragraph(f"Report Date: {datetime.now().strftime('%B %d, %Y')}")
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_para.runs[0].font.size = Pt(WORD_SIZES['body'])
    date_para.runs[0].font.color.rgb = RGBColor(*WORD_COLORS['text_secondary'])
    
    # Separator
    doc.add_paragraph()
    separator = doc.add_paragraph('_' * 80)
    separator.alignment = WD_ALIGN_PARAGRAPH.CENTER
    separator.runs[0].font.color.rgb = RGBColor(*WORD_COLORS['text_secondary'])
    
    doc.add_page_break()


def format_chat_content(doc: Document, content: str) -> None:
    """Format chat conversation content with proper styling."""
    if not content:
        return
    
    lines = content.split('\n')
    current_para = None
    table_lines = []
    in_table = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Check if this line is part of a table
        if '|' in line and line.count('|') >= 2:
            # We're in a table
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            
            # Check if next line is not a table line (end of table)
            is_last_line = i == len(lines) - 1
            next_line_not_table = i < len(lines) - 1 and ('|' not in lines[i + 1] or lines[i + 1].count('|') < 2)
            
            if is_last_line or next_line_not_table:
                # End of table, parse and add it
                add_markdown_table(doc, table_lines)
                in_table = False
                table_lines = []
                current_para = None
            continue
        
        if not line:
            # Empty line = new paragraph
            current_para = None
            continue
        
        # Apply math symbol replacements
        line = replace_math_symbols(line)
        
        # Convert citation markers to superscripts
        line = convert_citations(line)
        
        # Handle headers
        if line.startswith('###'):
            add_styled_heading(doc, line.replace('#', '').strip(), 3)
            current_para = None
        elif line.startswith('##'):
            add_styled_heading(doc, line.replace('#', '').strip(), 2)
            current_para = None
        elif line.startswith('#'):
            add_styled_heading(doc, line.replace('#', '').strip(), 1)
            current_para = None
        elif line.startswith('-') or line.startswith('•'):
            # Bullet point
            add_bullet_point(doc, line[1:].strip())
            current_para = None
        else:
            # Regular paragraph
            if not current_para:
                current_para = doc.add_paragraph()
                apply_body_style(current_para)
            else:
                current_para.add_run(' ')
            
            # Handle bold text
            add_formatted_text(current_para, line)


def format_risk_report(doc: Document, analysis_data: Dict[str, Any]) -> None:
    """Format risk analysis data into institutional report."""
    # Executive Summary
    add_styled_heading(doc, "Executive Summary", 1)
    
    if 'summary' in analysis_data:
        para = doc.add_paragraph(analysis_data['summary'])
        apply_body_style(para)
    
    # Risk Metrics Section
    if 'risk_metrics' in analysis_data:
        add_styled_heading(doc, "Risk Metrics", 1)
        add_metrics_table(doc, analysis_data['risk_metrics'])
    
    # Portfolio Composition
    if 'portfolio' in analysis_data:
        add_styled_heading(doc, "Portfolio Composition", 1)
        add_portfolio_table(doc, analysis_data['portfolio'])
    
    # Additional sections as needed
    for section_name, section_data in analysis_data.items():
        if section_name not in ['summary', 'risk_metrics', 'portfolio']:
            add_styled_heading(doc, section_name.replace('_', ' ').title(), 1)
            if isinstance(section_data, dict):
                add_metrics_table(doc, section_data)
            elif isinstance(section_data, str):
                para = doc.add_paragraph(section_data)
                apply_body_style(para)


def add_metrics_table(doc: Document, metrics: Dict[str, Any]) -> None:
    """Add professionally formatted metrics table."""
    # Create table
    table = doc.add_table(rows=1, cols=2)
    table.style = TABLE_STYLE
    
    # Add header
    header_cells = table.rows[0].cells
    header_cells[0].text = 'Metric'
    header_cells[1].text = 'Value'
    
    # Style headers
    for cell in header_cells:
        for para in cell.paragraphs:
            para.runs[0].font.bold = True
            para.runs[0].font.color.rgb = RGBColor(*WORD_COLORS['table_header'])
    
    # Add data rows
    for i, (key, value) in enumerate(metrics.items()):
        row = table.add_row()
        row.cells[0].text = format_metric_name(key)
        row.cells[1].text = format_metric_value(key, value)
        
        # Alternate row coloring
        if i % 2 == 1:
            for cell in row.cells:
                set_cell_background(cell, WORD_COLORS['table_alt_row'])


def add_portfolio_table(doc: Document, portfolio: Dict[str, Any]) -> None:
    """Add portfolio composition table."""
    if 'tickers' in portfolio and 'weights' in portfolio:
        table = doc.add_table(rows=1, cols=2)
        table.style = TABLE_STYLE
        
        # Headers
        header_cells = table.rows[0].cells
        header_cells[0].text = 'Ticker'
        header_cells[1].text = 'Weight'
        
        for cell in header_cells:
            for para in cell.paragraphs:
                para.runs[0].font.bold = True
                para.runs[0].font.color.rgb = RGBColor(*WORD_COLORS['table_header'])
        
        # Data
        tickers = portfolio['tickers']
        weights = portfolio['weights']
        
        for i, (ticker, weight) in enumerate(zip(tickers, weights)):
            row = table.add_row()
            row.cells[0].text = ticker
            row.cells[1].text = f"{weight:.1%}"
            
            if i % 2 == 1:
                for cell in row.cells:
                    set_cell_background(cell, WORD_COLORS['table_alt_row'])


def add_footer(doc: Document) -> None:
    """Add professional footer."""
    doc.add_page_break()
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_text = footer_para.add_run(f'© {datetime.now().year} Binomial Technologies. All rights reserved.')
    footer_text.font.size = Pt(WORD_SIZES['footnote'])
    footer_text.font.color.rgb = RGBColor(*WORD_COLORS['text_secondary'])


# Helper functions
def format_heading(heading, size_key: str, color_key: str) -> None:
    """Apply consistent heading formatting."""
    heading.runs[0].font.name = WORD_FONTS['primary']
    heading.runs[0].font.size = Pt(WORD_SIZES[size_key])
    heading.runs[0].font.color.rgb = RGBColor(*WORD_COLORS[color_key])
    heading.runs[0].font.bold = True


def add_styled_heading(doc: Document, text: str, level: int) -> None:
    """Add heading with appropriate styling."""
    heading = doc.add_heading(text, level=level)
    size_key = f'heading{level}'
    format_heading(heading, size_key, 'heading_blue')


def apply_body_style(para) -> None:
    """Apply body text styling to paragraph."""
    para.paragraph_format.line_spacing = LINE_SPACING
    para.paragraph_format.space_after = Pt(PARA_SPACING_AFTER)


def add_bullet_point(doc: Document, text: str) -> None:
    """Add styled bullet point."""
    bullet = doc.add_paragraph(text, style='List Bullet')
    bullet.runs[0].font.name = WORD_FONTS['primary']
    bullet.runs[0].font.size = Pt(WORD_SIZES['body'])


def add_formatted_text(para, text: str) -> None:
    """Add text with bold formatting support."""
    # Apply math symbols first
    text = replace_math_symbols(text)
    
    parts = text.split('**')
    for i, part in enumerate(parts):
        if i % 2 == 1:  # Odd indices are bold
            run = para.add_run(part)
            run.font.bold = True
        else:
            run = para.add_run(part)
        run.font.name = WORD_FONTS['primary']
        run.font.size = Pt(WORD_SIZES['body'])


def convert_citations(text: str) -> str:
    """Convert [1], [2] etc to superscript characters."""
    replacements = {
        '[1]': '¹', '[2]': '²', '[3]': '³', '[4]': '⁴',
        '[5]': '⁵', '[6]': '⁶', '[7]': '⁷', '[8]': '⁸',
        '[9]': '⁹', '[10]': '¹⁰'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def format_metric_name(key: str) -> str:
    """Clean up metric names for display."""
    replacements = {
        'var': 'VaR',
        'cvar': 'CVaR',
        '_': ' ',
        'pct': '%'
    }
    name = key
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name.title()


def format_metric_value(key: str, value: Any) -> str:
    """Format metric values appropriately."""
    if isinstance(value, float):
        if 'var' in key.lower() or 'cvar' in key.lower():
            return f"${value:,.0f}" if value > 1000 else f"{value:.2%}"
        elif 'vol' in key.lower() or 'return' in key.lower():
            return f"{value:.2%}"
        elif 'ratio' in key.lower():
            return f"{value:.2f}"
        else:
            return f"{value:,.4f}" if abs(value) < 1 else f"{value:,.2f}"
    elif isinstance(value, int):
        return f"{value:,}"
    else:
        return str(value)


def set_cell_background(cell, color_rgb: tuple) -> None:
    """Set cell background color."""
    shading_elm = OxmlElement('w:shd')
    shading_elm.set(qn('w:fill'), '%02x%02x%02x' % color_rgb)
    cell._element.get_or_add_tcPr().append(shading_elm)


def save_to_bytes(doc: Document) -> bytes:
    """Save document to bytes for download."""
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream.getvalue()


def add_markdown_table(doc: Document, table_lines: List[str]) -> None:
    """Convert markdown table to Word table."""
    if len(table_lines) < 2:  # Need at least header and separator
        return
    
    # Parse table structure
    rows = []
    for line in table_lines:
        if '---' in line:  # Skip separator line
            continue
        # Split by | and clean up
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        if cells:
            rows.append(cells)
    
    if not rows:
        return
    
    # Create table
    num_cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=num_cols)
    table.style = TABLE_STYLE
    
    # Populate table
    for i, row_data in enumerate(rows):
        for j, cell_text in enumerate(row_data[:num_cols]):  # Ensure we don't exceed columns
            cell = table.rows[i].cells[j]
            cell.text = cell_text
            
            # Style header row
            if i == 0:
                for para in cell.paragraphs:
                    if para.runs:
                        para.runs[0].font.bold = True
                        para.runs[0].font.color.rgb = RGBColor(*WORD_COLORS['table_header'])
            
            # Alternate row coloring (skip header)
            elif i % 2 == 0:
                set_cell_background(cell, WORD_COLORS['table_alt_row'])


def replace_math_symbols(text: str) -> str:
    """Replace common math notation with proper Unicode symbols."""
    replacements = {
        ' x ': ' × ',
        '*': '×',
        'sqrt': '√',
        'sigma': 'σ',
        'delta': 'Δ',
        'alpha': 'α',
        'beta': 'β',
        'gamma': 'γ',
        'theta': 'θ',
        'mu': 'μ',
        'pi': 'π',
        '>=': '≥',
        '<=': '≤',
        '!=': '≠',
        '+-': '±',
        'infinity': '∞'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text