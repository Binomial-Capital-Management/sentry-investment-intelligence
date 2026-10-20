"""HTML sanitizer for SEC EDGAR filings."""

import re


# CSS styles for SEC filing rendering
FILING_STYLES = """
<style>
    body { 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        font-size: 13px;
        line-height: 1.6;
        padding: 20px 28px;
        max-width: 100%;
        overflow-x: auto;
        color: #1a1a1a;
        background: #fff;
    }
    h1, h2, h3, h4, h5 { margin-top: 1.5em; margin-bottom: 0.5em; color: #111; }
    p { margin: 0.75em 0; }
    
    /* Table styling */
    table { 
        border-collapse: collapse; 
        margin: 0.5em 0;
        font-size: 12px;
        border: none;
        border-spacing: 0;
    }
    td, th { 
        padding: 6px 12px;
        vertical-align: top;
        text-align: left;
        border: none;
    }
    th { 
        font-weight: 600;
        color: #333;
        border-bottom: 1px solid #ccc;
    }
    tr.has-content td { border-bottom: 1px solid #eee; }
    tr.has-content:hover td { background: #fafafa; }
    
    .empty-row, .empty-cell { display: none !important; }
    
    a { color: #1976d2; text-decoration: none; }
    a:hover { text-decoration: underline; }
    hr { border: none; border-top: 1px solid #e0e0e0; margin: 2em 0; }
    
    table table { margin: 0; }
    table table td, table table th { padding: 3px 8px; }
    
    ix\\:nonfraction, ix\\:nonnumeric { display: inline; }
</style>
"""

# JavaScript for DOM cleanup
CLEANUP_SCRIPT = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('table').forEach(function(table) {
        var rows = table.querySelectorAll('tr');
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td, th');
            var hasContent = false;
            cells.forEach(function(cell) {
                var text = (cell.textContent || '').trim();
                if (text && text !== '$' && text !== '—' && text !== '-' && text !== '(' && text !== ')' && text.length > 0 && !/^[\\s\\u00A0]+$/.test(text)) {
                    hasContent = true;
                } else if (!text || /^[\\s\\u00A0]*$/.test(text)) {
                    cell.classList.add('empty-cell');
                    cell.style.padding = '0';
                    cell.style.width = '0';
                    cell.style.border = 'none';
                }
            });
            if (hasContent) {
                row.classList.add('has-content');
            } else {
                row.classList.add('empty-row');
            }
        });
        
        var colCount = 0;
        var firstRow = table.querySelector('tr');
        if (firstRow) {
            colCount = firstRow.querySelectorAll('td, th').length;
        }
        for (var col = colCount - 1; col >= 0; col--) {
            var allEmpty = true;
            rows.forEach(function(row) {
                var cells = row.querySelectorAll('td, th');
                if (cells[col]) {
                    var text = (cells[col].textContent || '').trim();
                    if (text && !/^[\\s\\u00A0$—-]*$/.test(text)) {
                        allEmpty = false;
                    }
                }
            });
            if (allEmpty) {
                rows.forEach(function(row) {
                    var cells = row.querySelectorAll('td, th');
                    if (cells[col]) {
                        cells[col].style.display = 'none';
                    }
                });
            }
        }
    });
    
    document.querySelectorAll('br + br + br').forEach(function(br) {
        br.remove();
    });
});
</script>
"""


class HTMLSanitizer:
    """Sanitize SEC EDGAR HTML for safe iframe rendering."""
    
    def sanitize(self, content: str, base_url: str) -> str:
        """Sanitize HTML content for safe rendering."""
        # Add base tag
        content = self._add_base_tag(content, base_url)
        
        # Remove scripts (but keep noscript)
        content = self._remove_scripts(content)
        
        # Remove event handlers
        content = self._remove_event_handlers(content)
        
        # Remove javascript: URLs
        content = self._remove_js_urls(content)
        
        # Inject styles and cleanup script
        content = self._inject_styles(content)
        
        return content
    
    def _add_base_tag(self, content: str, base_url: str) -> str:
        """Add base tag for relative URLs."""
        if "<base" in content.lower():
            return content
        
        base_tag = f'<base href="{base_url}/" target="_blank">'
        
        if "<head>" in content.lower():
            return re.sub(
                r"(<head[^>]*>)",
                f"\\1\n{base_tag}",
                content, count=1, flags=re.IGNORECASE
            )
        elif "<html" in content.lower():
            return re.sub(
                r"(<html[^>]*>)",
                f"\\1\n<head>{base_tag}</head>",
                content, count=1, flags=re.IGNORECASE
            )
        else:
            return f"<head>{base_tag}</head>\n{content}"
    
    def _remove_scripts(self, content: str) -> str:
        """Remove script tags."""
        return re.sub(
            r"<script\b[^>]*>[\s\S]*?</script>",
            "", content, flags=re.IGNORECASE
        )
    
    def _remove_event_handlers(self, content: str) -> str:
        """Remove onclick and other event handlers."""
        return re.sub(
            r'\s+on\w+\s*=\s*["\'][^"\']*["\']',
            "", content, flags=re.IGNORECASE
        )
    
    def _remove_js_urls(self, content: str) -> str:
        """Remove javascript: URLs."""
        return re.sub(
            r'href\s*=\s*["\']javascript:[^"\']*["\']',
            'href="#"', content, flags=re.IGNORECASE
        )
    
    def _inject_styles(self, content: str) -> str:
        """Inject CSS and cleanup script."""
        injection = FILING_STYLES + CLEANUP_SCRIPT
        
        # Use simple string replacement to avoid regex interpreting \s in JS code
        lower_content = content.lower()
        head_close_idx = lower_content.find("</head>")
        
        if head_close_idx != -1:
            return content[:head_close_idx] + injection + content[head_close_idx:]
        else:
            return injection + content
