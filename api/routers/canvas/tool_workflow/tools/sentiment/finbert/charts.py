"""FinBERT Sentiment Canvas Charts.

Builds Plotly chart configurations for sentiment analysis visualization.
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Color palette for sentiments
COLORS = {
    "positive": "#10b981",  # Green
    "neutral": "#6b7280",   # Gray
    "negative": "#ef4444",  # Red
}


def build_sentiment_pie_chart(distribution: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """Build sentiment distribution pie chart.
    
    Args:
        distribution: Dict with positive, neutral, negative counts
        
    Returns:
        Plotly chart configuration or None
    """
    if not distribution:
        return None
    
    # Only include non-zero values
    labels = []
    values = []
    colors = []
    
    if distribution.get("positive", 0) > 0:
        labels.append("Bullish")
        values.append(distribution["positive"])
        colors.append(COLORS["positive"])
    
    if distribution.get("neutral", 0) > 0:
        labels.append("Neutral")
        values.append(distribution["neutral"])
        colors.append(COLORS["neutral"])
    
    if distribution.get("negative", 0) > 0:
        labels.append("Bearish")
        values.append(distribution["negative"])
        colors.append(COLORS["negative"])
    
    # Skip if no data
    if not values:
        return None
    
    return {
        "plotly": {
            "data": [{
                "type": "pie",
                "labels": labels,
                "values": values,
                "marker": {
                    "colors": colors,
                    "line": {"color": "white", "width": 2}
                },
                "hole": 0.5,  # Donut chart
                "textinfo": "percent+label",
                "textposition": "outside",
                "textfont": {"size": 12},
                "pull": [0.02] * len(values),  # Slight separation
                "hovertemplate": "<b>%{label}</b><br>%{value} articles<br>%{percent}<extra></extra>",
            }],
            "layout": {
                "title": {"text": "News Sentiment Mix", "font": {"size": 14}, "x": 0.5},
                "showlegend": False,
                "height": 320,
                "margin": {"t": 60, "r": 80, "b": 40, "l": 80},
                "paper_bgcolor": "white",
                "annotations": [{
                    "text": f"{sum(values)}<br>articles",
                    "x": 0.5, "y": 0.5,
                    "font": {"size": 16, "color": "#374151"},
                    "showarrow": False,
                }],
            },
        },
        "type": "pie",
        "label": "Sentiment Distribution",
    }


def build_sentiment_timeline_chart(sentiments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build sentiment bar chart showing daily sentiment counts.
    
    Args:
        sentiments: List of article sentiment results with publishedDate
        
    Returns:
        Plotly chart configuration or None
    """
    if not sentiments:
        return None
    
    # Filter articles with dates
    dated_articles = [s for s in sentiments if s.get("publishedDate")]
    if len(dated_articles) < 2:
        return None
    
    # Group by date and sentiment
    from collections import defaultdict
    daily_counts = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    
    for a in dated_articles:
        date = a.get("publishedDate", "")[:10]
        label = a.get("label", "neutral")
        daily_counts[date][label] += 1
    
    # Sort dates
    dates = sorted(daily_counts.keys())
    
    if len(dates) < 1:
        return None
    
    pos_counts = [daily_counts[d]["positive"] for d in dates]
    neu_counts = [daily_counts[d]["neutral"] for d in dates]
    neg_counts = [-daily_counts[d]["negative"] for d in dates]  # Negative for stacked below
    
    traces = []
    
    # Bullish bars (above zero)
    traces.append({
        "type": "bar",
        "x": dates,
        "y": pos_counts,
        "name": "Bullish",
        "marker": {"color": COLORS["positive"]},
        "hovertemplate": "%{x}<br>Bullish: %{y}<extra></extra>",
    })
    
    # Bearish bars (below zero)
    traces.append({
        "type": "bar",
        "x": dates,
        "y": neg_counts,
        "name": "Bearish",
        "marker": {"color": COLORS["negative"]},
        "hovertemplate": "%{x}<br>Bearish: %{customdata}<extra></extra>",
        "customdata": [daily_counts[d]["negative"] for d in dates],
    })
    
    return {
        "plotly": {
            "data": traces,
            "layout": {
                "title": {"text": "Daily Sentiment Count", "font": {"size": 14}},
                "xaxis": {"title": "Date", "tickangle": -45},
                "yaxis": {
                    "title": "Article Count",
                    "zeroline": True,
                    "zerolinecolor": "#374151",
                    "zerolinewidth": 1,
                },
                "barmode": "relative",
                "height": 300,
                "margin": {"t": 50, "r": 30, "b": 70, "l": 50},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "legend": {"orientation": "h", "y": 1.12, "x": 0.5, "xanchor": "center"},
            },
        },
        "type": "bar",
        "label": "Daily Sentiment",
    }


def build_article_sentiment_chart(sentiments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart showing confidence scores colored by sentiment.
    
    Args:
        sentiments: List of article sentiment results
        
    Returns:
        Plotly chart configuration or None
    """
    if not sentiments:
        return None
    
    # Take top 8 articles with strongest signals (highest confidence non-neutral)
    scored_articles = []
    for a in sentiments:
        label = a.get("label", "neutral")
        score = a.get("score", 0)
        # Prioritize non-neutral with high confidence
        priority = score if label != "neutral" else score * 0.5
        scored_articles.append((priority, a))
    
    scored_articles.sort(key=lambda x: -x[0])
    articles = [a for _, a in scored_articles[:8]]
    
    if not articles:
        return None
    
    # Prepare data (reverse for top-to-bottom reading order in horizontal bars)
    articles = list(reversed(articles))
    
    titles = []
    for a in articles:
        title = a.get("title", "")[:50]
        if len(a.get("title", "")) > 50:
            title += "..."
        titles.append(title)
    
    # All scores as positive (confidence), color indicates sentiment
    scores = [a.get("score", 0) * 100 for a in articles]  # Convert to percentage
    labels = [a.get("label", "neutral") for a in articles]
    colors = [COLORS.get(label, COLORS["neutral"]) for label in labels]
    
    # Text shows the sentiment label
    text_labels = [f"{label.capitalize()}" for label in labels]
    
    return {
        "plotly": {
            "data": [{
                "type": "bar",
                "y": titles,
                "x": scores,
                "orientation": "h",
                "marker": {"color": colors},
                "text": text_labels,
                "textposition": "inside",
                "insidetextanchor": "start",
                "textfont": {"color": "white", "size": 11},
                "hovertemplate": "<b>%{y}</b><br>%{text}: %{x:.0f}% confidence<extra></extra>",
            }],
            "layout": {
                "title": {"text": "Top Articles by Confidence", "font": {"size": 14}},
                "xaxis": {
                    "title": "Confidence %",
                    "range": [0, 105],
                    "ticksuffix": "%",
                },
                "yaxis": {"tickfont": {"size": 9}, "automargin": True},
                "height": max(280, len(articles) * 35 + 80),
                "margin": {"t": 50, "r": 20, "b": 50, "l": 10},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
            },
        },
        "type": "bar",
        "label": "Top Articles",
    }
