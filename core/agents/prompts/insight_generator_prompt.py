"""
Insight Generator Agent Prompt - Simplified for fast batch processing.
Generates 6 quick market insights per page/region.
"""

from datetime import datetime


def get_insight_generator_prompt(page_type: str, region: str = None) -> str:
    """Generate a concise prompt for batch insight generation."""
    current_date = datetime.now().strftime("%B %d, %Y")

    # Minimal focus per page type
    if page_type == "markets":
        region = region or "us"
        region_focus = {
            "us": "S&P 500, Nasdaq, VIX, Treasury yields, sector ETFs (XLF, XLK, XLE)",
            "eu": "DAX, CAC 40, FTSE, EUR/USD, European banks",
            "china": "Shanghai Composite, Hang Seng, CNY, Chinese tech",
            "korea": "KOSPI, Samsung, Korean semiconductors, KRW",
            "japan": "Nikkei 225, TOPIX, JPY, BOJ policy, Japanese autos",
        }.get(region, f"{region} market indices and key sectors")
        focus = f"Focus: {region_focus}"
    elif page_type == "crypto":
        focus = "Focus: BTC, ETH, altcoins, DeFi trends, institutional flows"
    elif page_type == "macro":
        focus = "Focus: Fed policy, Treasury yields, gold, oil, USD, economic data"
    else:
        focus = "Focus: General market trends"

    return f"""Date: {current_date}

Task: Generate 6 brief market insights for the {page_type} dashboard{f' ({region})' if region else ''}.

{focus}

Instructions:
1. Use FMP tools to get current prices: get_fields(symbol="SPY", fields=["price", "changesPercentage"])
2. Use get_latest_news or get_news_by_symbol for recent headlines
3. Each insight: ONE sentence, 25-35 words, include ONE data point

Return JSON only:
{{
  "insights": [
    {{
      "title": "Brief title",
      "content": {{
        "summary": "One sentence with data",
        "data_point": "SPY: $480 (+0.5%)",
        "source": "FMP"
      }},
      "priority": 6,
      "metadata": {{"symbols": ["SPY"], "data_as_of": "{current_date}"}}
    }}
  ]
}}

Generate 6 insights. Return ONLY valid JSON, no explanations."""
