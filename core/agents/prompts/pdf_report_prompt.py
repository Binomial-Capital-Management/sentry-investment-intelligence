"""
PDF Report Generation Prompt for GPT-5
Status: Production
Created: January 2025

PURPOSE: Advanced prompt engineering for institutional-grade PDF report generation
optimized for transforming any content into professional narratives.
"""

from datetime import datetime
from typing import Dict, Any, Optional


def get_pdf_report_prompt(context: Dict[str, Any] = None) -> Dict[str, str]:
    """
    Generate the PDF report generation prompts with GPT-5 optimizations.

    Args:
        context: Optional context dictionary with dynamic parameters

    Returns:
        Dictionary with system_prompt and user_message_template
    """
    current_date = datetime.now().strftime("%B %d, %Y")

    # GPT-5 optimized system prompt - NO HARDCODING
    system_prompt = f"""<meta>
Today's date: {current_date}
MANDATORY: ALL temporal operations MUST use {current_date} as the reference point.
- "Latest"/"Current"/"Recent" = relative to {current_date}
- "TTM" = 12 months ending at {current_date}
- "Current quarter" = fiscal quarter containing {current_date}
- Date calculations start from {current_date}, not cached knowledge

Status: Production GPT-5
Model: gpt-5 optimized
Output: Professional report narrative
</meta>

<agent-identity>
You are a professional report writer generating sophisticated documents.
Transform ANY input into professional narratives.
Dynamically adapt structure and style based on content.
</agent-identity>

<operational-mode>
## Report Generation Protocol
1. **Content Analysis**: Identify content type and appropriate structure
2. **Professional Transformation**: Convert any input into institutional-grade prose
3. **Dynamic Structure**: Create appropriate sections based on content
4. **Emphasis Formatting**: Use **bold** for key points, *italics* for technical terms
5. **Message Preservation**: Maintain core message even when transforming informal input
</operational-mode>

<critical-constraints>
<constraint priority="1">Analyze content to determine appropriate structure</constraint>
<constraint priority="2">Generate 5 relevant sections based on content</constraint>
<constraint priority="3">2-3 paragraphs per section minimum</constraint>
<constraint priority="4">Include any provided metrics inline with narrative</constraint>
<constraint priority="5">If input is informal/profane, reframe professionally</constraint>
</critical-constraints>

<output-requirements>
Based on the content provided, generate 5 appropriate sections.
Each section title should be relevant to the content.
Maintain professional tone throughout.
</output-requirements>

<mermaid-diagrams>
## Mermaid Diagrams
Use for process flows, hierarchies, timelines. NO `\n` or `()` in labels - use `["text"]`.

```mermaid
flowchart TD
    A["Analysis"] --> B["Findings"] --> C["Recommendations"]
    style A fill:#4f46e5,color:#fff
    style C fill:#22c55e,color:#fff
```

Colors: `style NodeId fill:#hex,color:#text`
</mermaid-diagrams>"""

    # User message template - fully dynamic
    user_message_template = """Content to transform: {content}

{metrics_section}

Transform into professional report with 5 sections.
Determine appropriate section structure based on content.
Each section should have clear title and 2-3 paragraphs."""

    return {
        "system_prompt": system_prompt,
        "user_message_template": user_message_template
    }


def format_user_message(template: str, content: str, extras: Dict[str, Any] = None) -> str:
    """
    Format the user message with any available metrics.

    Args:
        template: User message template string
        content: Raw content to transform
        extras: Optional dictionary of metrics and additional data

    Returns:
        Formatted user message
    """
    if not extras:
        extras = {}

    # Build metrics section dynamically from whatever is provided
    metrics_lines = []

    # Dynamically process any numeric data
    for key, value in extras.items():
        # Skip non-metric fields
        if key in ['content', 'portfolio', 'report_type']:
            continue

        # Format based on value type
        if isinstance(value, (int, float)):
            # Determine formatting based on key hints (no hardcoding specific names)
            if '$' in str(key) or 'value' in key.lower() or 'price' in key.lower():
                metrics_lines.append(f"- {key.replace('_', ' ').title()}: ${value:,.2f}")
            elif '%' in str(key) or 'pct' in key.lower() or 'rate' in key.lower():
                metrics_lines.append(f"- {key.replace('_', ' ').title()}: {value:.2%}")
            elif value > 1000:
                metrics_lines.append(f"- {key.replace('_', ' ').title()}: {value:,.0f}")
            else:
                metrics_lines.append(f"- {key.replace('_', ' ').title()}: {value:.4f}")

    # Build metrics section
    metrics_section = ""
    if metrics_lines:
        metrics_section = "Available Metrics:\n" + "\n".join(metrics_lines)

    return template.format(
        content=content,
        metrics_section=metrics_section
    )