"""SEC form type descriptions."""

# Human-readable descriptions for SEC form types
FORM_DESCRIPTIONS = {
    "10-K": "Annual Report",
    "10-K/A": "Annual Report (Amended)",
    "10-Q": "Quarterly Report",
    "10-Q/A": "Quarterly Report (Amended)",
    "8-K": "Current Report",
    "8-K/A": "Current Report (Amended)",
    "DEF 14A": "Proxy Statement",
    "DEFA14A": "Additional Proxy Materials",
    "S-1": "Registration Statement",
    "S-1/A": "Registration Statement (Amended)",
    "4": "Insider Trading",
    "13F-HR": "Institutional Holdings",
    "SC 13G": "Beneficial Ownership",
    "SC 13D": "Beneficial Ownership (>5%)",
    "20-F": "Annual Report (Foreign)",
    "6-K": "Current Report (Foreign)",
}


def get_form_description(form_type: str) -> str:
    """Get human-readable description for SEC form type."""
    form_upper = form_type.upper().strip()
    
    # Try exact match
    if form_upper in FORM_DESCRIPTIONS:
        return FORM_DESCRIPTIONS[form_upper]
    
    # Try partial match
    for key, desc in FORM_DESCRIPTIONS.items():
        if key in form_upper or form_upper in key:
            return desc
    
    return form_type  # Return as-is if no match
