"""
Financial News Sentiment Analysis Tool using FinBERT

Fetches news from FMP and analyzes sentiment using Hugging Face's FinBERT model.
FinBERT is a BERT model fine-tuned on financial text for sentiment classification.

NO HARDCODING: Uses dynamic field discovery for news data.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from agents import function_tool
from huggingface_hub import InferenceClient

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
from core.utils.risk_adapter import jsonify_results

logger = logging.getLogger(__name__)


async def analyze_news_sentiment_internal(
    symbol: Optional[str] = None,
    news_type: str = "stock",
    max_articles: int = 20
) -> Dict[str, Any]:
    """Internal callable for Canvas - analyzes news sentiment using FinBERT.
    
    Args:
        symbol: Stock/crypto/forex symbol (e.g., 'AAPL', 'BTCUSD', 'EURUSD'). If None, fetches market-wide news.
        news_type: Type of news ('stock', 'press-releases', 'general', 'crypto', 'forex')
        max_articles: Maximum number of news articles to analyze (default: 20, max: 100)
        
    Returns:
        Dictionary with sentiments, aggregate_sentiment, sentiment_distribution, metadata
    """
    news_server = None
    try:
        # Validate inputs
        max_articles = min(max(1, max_articles), 100)

        if news_type in ['stock', 'press-releases'] and not symbol:
            return {
                "status": "error",
                "error": f"news_type='{news_type}' requires a symbol parameter",
                "error_type": "validation_error"
            }

        # Call internal handlers directly to bypass bh_ingest which would
        # replace the raw JSON with a compact summary the parser can't read.
        if news_type in ['crypto', 'forex']:
            news_server = FMPAlternativesServer()
            await news_server.connect()

            if symbol:
                news_data = await news_server._handle_get_alternatives_news_by_symbol({
                    "news_type": news_type,
                    "symbol": symbol,
                    "max_results": max_articles
                })
            else:
                news_data = await news_server._handle_get_latest_alternatives_news({
                    "news_type": news_type,
                    "max_results": max_articles
                })
        else:
            news_server = FMPMarketDataServer()
            await news_server.connect()

            if symbol:
                news_data = await news_server._handle_get_news_by_symbol({
                    "symbol": symbol,
                    "news_type": "news" if news_type == "stock" else "press-releases",
                    "max_results": max_articles
                })
            else:
                news_data = await news_server._handle_get_latest_news({
                    "news_type": news_type,
                    "max_results": max_articles
                })

        if not isinstance(news_data, dict):
            news_data = {}

        if not news_data or news_data.get("status") == "error" or news_data.get("error"):
            return {
                "status": "error",
                "error": f"Failed to fetch news: {news_data.get('error', 'Unknown error')}",
                "error_type": "news_fetch_error"
            }

        # Extract articles from response (FMP returns dict with 'data' key)
        articles = news_data.get("data", [])
        if not articles:
            return {
                "status": "success",
                "sentiments": [],
                "aggregate_sentiment": {"score": 0.0, "label": "neutral", "confidence": 0.0},
                "metadata": {
                    "symbol": symbol,
                    "news_type": news_type,
                    "articles_analyzed": 0,
                    "model": "ProsusAI/finbert"
                }
            }

        # Initialize Hugging Face Inference Client with new serverless API
        api_key = os.environ.get("HF_TOKEN")
        if not api_key:
            logger.error("HF_TOKEN not found in environment variables")
            return {
                "status": "error",
                "error": "HF_TOKEN not configured. Please set HF_TOKEN environment variable.",
                "error_type": "configuration_error"
            }

        # Use model-specific client with serverless inference
        client = InferenceClient(model="ProsusAI/finbert", token=api_key)

        # Analyze sentiment for each article
        sentiment_results = []

        for article in articles[:max_articles]:
            # Extract text from article (title is most important, combine with snippet if available)
            title = article.get("title", "")
            text_snippet = article.get("text", "")

            # Use title + snippet for sentiment (limit to avoid API issues)
            full_text = f"{title}. {text_snippet}".strip()[:500]

            if not full_text:
                continue

            try:
                # Call FinBERT model using serverless inference
                result = client.text_classification(full_text)

                # Extract top prediction
                if result and len(result) > 0:
                    top_result = result[0]
                    sentiment_results.append({
                        "title": title,
                        "url": article.get("url", ""),
                        "publishedDate": article.get("publishedDate", ""),
                        "site": article.get("site", ""),
                        "label": top_result.get("label", "neutral").lower(),
                        "score": round(top_result.get("score", 0.0), 3)
                    })

            except Exception as e:
                logger.warning(f"Error analyzing article sentiment: {e}")
                # Continue with other articles
                continue

        if not sentiment_results:
            return {
                "status": "error",
                "error": "No articles could be analyzed for sentiment",
                "error_type": "analysis_error"
            }

        # Calculate aggregate sentiment
        # Map labels to numeric scores: positive=1, neutral=0, negative=-1
        label_to_score = {"positive": 1, "neutral": 0, "negative": -1}
        weighted_scores = []

        for result in sentiment_results:
            label = result["label"]
            confidence = result["score"]
            numeric_score = label_to_score.get(label, 0)
            # Weight by confidence
            weighted_scores.append(numeric_score * confidence)

        # Calculate aggregate
        avg_score = sum(weighted_scores) / len(weighted_scores)

        # Determine aggregate label
        if avg_score > 0.1:
            agg_label = "positive"
        elif avg_score < -0.1:
            agg_label = "negative"
        else:
            agg_label = "neutral"

        aggregate = {
            "score": round(avg_score, 3),
            "label": agg_label,
            "confidence": round(sum(r["score"] for r in sentiment_results) / len(sentiment_results), 3)
        }

        # Count sentiment distribution
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for result in sentiment_results:
            sentiment_counts[result["label"]] += 1

        return jsonify_results({
            "status": "success",
            "sentiments": sentiment_results,
            "aggregate_sentiment": aggregate,
            "sentiment_distribution": sentiment_counts,
            "metadata": {
                "symbol": symbol,
                "news_type": news_type,
                "articles_analyzed": len(sentiment_results),
                "articles_fetched": len(articles),
                "model": "ProsusAI/finbert"
            }
        })

    except Exception as e:
        logger.error(f"News sentiment analysis failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_type": "analysis_error"
        }
    finally:
        # Properly close MCP server connection
        if news_server:
            try:
                await news_server.cleanup()
            except Exception as e:
                logger.warning(f"Failed to cleanup news server: {e}")


@function_tool
async def analyze_news_sentiment(
    symbol: Optional[str] = None,
    news_type: str = "stock",
    max_articles: int = 20
) -> Dict[str, Any]:
    """
    Analyze sentiment of financial news for a stock or market-wide news.

    Automatically fetches news from FMP and analyzes sentiment using FinBERT,
    a specialized financial sentiment model. Returns per-article sentiment scores
    and aggregate sentiment analysis.

    Args:
        symbol: Stock/crypto/forex symbol (e.g., 'AAPL', 'BTCUSD', 'EURUSD'). If None, fetches market-wide news.
        news_type: Type of news to analyze:
                   - 'stock' = stock-specific news (requires symbol)
                   - 'press-releases' = official company announcements (requires symbol)
                   - 'general' = broad market news (symbol optional)
                   - 'crypto' = cryptocurrency news (symbol optional, e.g., 'BTCUSD')
                   - 'forex' = foreign exchange news (symbol optional, e.g., 'EURUSD')
        max_articles: Maximum number of news articles to analyze (default: 20, max: 100)

    Returns:
        Dictionary containing:
        - sentiments: List of per-article sentiment analysis
        - aggregate_sentiment: Overall sentiment across all articles
        - metadata: Analysis details (model, article count, symbol, etc.)

    Examples:
        >>> analyze_news_sentiment(symbol="AAPL", news_type="press-releases", max_articles=10)
        >>> analyze_news_sentiment(news_type="general", max_articles=50)
        >>> analyze_news_sentiment(symbol="BTCUSD", news_type="crypto", max_articles=15)
    """
    return await analyze_news_sentiment_internal(
        symbol=symbol,
        news_type=news_type,
        max_articles=max_articles
    )
