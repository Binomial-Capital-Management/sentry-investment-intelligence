"""
FinBERT Sentiment Canvas Executor

Wraps the FinBERT sentiment analysis tool for Canvas visualization.
Analyzes news sentiment using the ProsusAI/finbert model.
"""
from typing import Dict, List, Any, Optional
import logging

from .charts import build_sentiment_pie_chart, build_sentiment_timeline_chart, build_article_sentiment_chart

logger = logging.getLogger(__name__)


async def execute_finbert_sentiment(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute FinBERT sentiment analysis for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including ticker, news_type, max_articles
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.sentiment_tools.finbert_sentiment_tool import analyze_news_sentiment_internal
    
    ticker = params.get('ticker') or params.get('symbol')
    news_type = params.get('news_type', 'stock')
    max_articles = int(params.get('max_articles', 20))
    
    # Validate inputs based on news_type
    if news_type in ['stock', 'press-releases'] and not ticker:
        return {"status": "error", "error": f"Ticker is required for news_type='{news_type}'"}
    
    if ticker:
        ticker = ticker.upper()
    
    try:
        logger.info(f"[FINBERT] Analyzing sentiment for {ticker or 'market'}, type={news_type}, max={max_articles}")
        
        # Call the internal function directly
        result = await analyze_news_sentiment_internal(
            symbol=ticker,
            news_type=news_type,
            max_articles=max_articles
        )
        
        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error", "Sentiment analysis failed")}
        
        # Extract data
        sentiments = result.get("sentiments", [])
        aggregate = result.get("aggregate_sentiment", {})
        distribution = result.get("sentiment_distribution", {})
        metadata = result.get("metadata", {})
        
        if not sentiments:
            return {"status": "error", "error": "No articles found for sentiment analysis"}
        
        # Build charts
        charts = {}
        
        pie_chart = build_sentiment_pie_chart(distribution)
        if pie_chart:
            charts["sentiment_distribution"] = pie_chart
        
        timeline_chart = build_sentiment_timeline_chart(sentiments)
        if timeline_chart:
            charts["sentiment_timeline"] = timeline_chart
        
        article_chart = build_article_sentiment_chart(sentiments[:10])  # Top 10
        if article_chart:
            charts["article_sentiments"] = article_chart
        
        # Build metric cards
        agg_score = aggregate.get("score", 0)
        agg_label = aggregate.get("label", "neutral")
        agg_confidence = aggregate.get("confidence", 0)
        
        metric_cards = [
            {
                "id": "overall_sentiment",
                "label": "Overall Sentiment",
                "value": agg_label.upper(),
                "sentiment": "positive" if agg_label == "positive" else ("negative" if agg_label == "negative" else "neutral"),
            },
            {
                "id": "sentiment_score",
                "label": "Sentiment Score",
                "value": f"{agg_score:+.2f}",
                "description": "-1 (bearish) to +1 (bullish)",
                "sentiment": "positive" if agg_score > 0.2 else ("negative" if agg_score < -0.2 else "neutral"),
            },
            {
                "id": "confidence",
                "label": "Avg Confidence",
                "value": f"{agg_confidence:.0%}",
                "sentiment": "positive" if agg_confidence > 0.7 else "neutral",
            },
            {
                "id": "articles_analyzed",
                "label": "Articles Analyzed",
                "value": str(metadata.get("articles_analyzed", 0)),
                "sentiment": "neutral",
            },
            {
                "id": "positive_count",
                "label": "Positive",
                "value": str(distribution.get("positive", 0)),
                "sentiment": "positive",
            },
            {
                "id": "negative_count",
                "label": "Negative",
                "value": str(distribution.get("negative", 0)),
                "sentiment": "negative",
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Overview", "metric": "Symbol", "value": ticker or "Market-wide"},
            {"category": "Overview", "metric": "News Type", "value": news_type.replace("-", " ").title()},
            {"category": "Overview", "metric": "Articles Analyzed", "value": str(metadata.get("articles_analyzed", 0))},
            {"category": "Overview", "metric": "Model", "value": metadata.get("model", "ProsusAI/finbert")},
            {"category": "Aggregate", "metric": "Overall Sentiment", "value": agg_label.capitalize()},
            {"category": "Aggregate", "metric": "Sentiment Score", "value": f"{agg_score:+.3f}"},
            {"category": "Aggregate", "metric": "Avg Confidence", "value": f"{agg_confidence:.1%}"},
            {"category": "Distribution", "metric": "Positive Articles", "value": str(distribution.get("positive", 0))},
            {"category": "Distribution", "metric": "Neutral Articles", "value": str(distribution.get("neutral", 0))},
            {"category": "Distribution", "metric": "Negative Articles", "value": str(distribution.get("negative", 0))},
        ]
        
        # Add top articles
        stats_table.append({"category": "Top Articles", "metric": "─" * 20, "value": "─" * 15})
        for i, article in enumerate(sentiments[:5]):
            title = article.get("title", "")[:60]
            if len(article.get("title", "")) > 60:
                title += "..."
            label = article.get("label", "neutral")
            score = article.get("score", 0)
            stats_table.append({
                "category": f"#{i+1}",
                "metric": title,
                "value": f"{label.capitalize()} ({score:.0%})",
            })
        
        return {
            "status": "success",
            "tool_id": "finbert_sentiment",
            "tickers": [ticker] if ticker else [],
            "weights": [],
            "metrics": {
                "aggregate_score": agg_score,
                "aggregate_label": agg_label,
                "confidence": agg_confidence,
                "articles_analyzed": metadata.get("articles_analyzed", 0),
                "positive_count": distribution.get("positive", 0),
                "neutral_count": distribution.get("neutral", 0),
                "negative_count": distribution.get("negative", 0),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"FinBERT sentiment failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
