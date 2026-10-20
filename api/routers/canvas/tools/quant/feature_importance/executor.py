"""Executor for Feature Importance Canvas tool."""
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


async def execute_feature_importance(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute XGBoost feature importance analysis for Canvas."""
    try:
        from core.agents.quant_tools.feature_importance_tool import analyze_feature_importance_internal
        from core.services.portfolio_service import PortfolioService
        from .charts import (
            build_importance_bars_chart,
            build_permutation_scatter_chart,
            build_shap_chart,
            build_correlation_heatmap
        )
        
        # Extract parameters
        input_type = params.get("input_type", "ticker")
        portfolio_id = params.get("portfolio_id")
        tickers_str = params.get("tickers", "")
        target = params.get("target", "future_5day_return")
        period = params.get("period", "1Y")
        top_n = int(params.get("top_n", 15))
        methods = params.get("methods", "gain,permutation,shap")
        
        # Resolve tickers
        tickers = []
        if input_type == 'portfolio' and portfolio_id:
            portfolio_service = PortfolioService()
            result = await portfolio_service.get_portfolio(user_id, portfolio_id)
            
            if result.get("status") != "success":
                return {"status": "error", "error": f"Portfolio not found: {result.get('message', 'Unknown error')}"}
            
            portfolio = result.get("portfolio", {})
            tickers = portfolio.get("tickers", [])[:10]  # Limit to 10 for performance
            
        elif tickers_str:
            if isinstance(tickers_str, str):
                tickers = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]
            else:
                tickers = [t.upper() for t in tickers_str]
        
        if not tickers:
            return {"status": "error", "error": "Provide tickers or select a portfolio"}
        
        # Parse methods
        if isinstance(methods, str):
            importance_methods = [m.strip().lower() for m in methods.split(',')]
        else:
            importance_methods = methods
        
        logger.info(f"Feature Importance: {tickers}, target={target}, period={period}")
        
        # Call internal function
        result = await analyze_feature_importance_internal(
            tickers=tickers,
            target_variable=target,
            period=period,
            importance_methods=importance_methods,
            top_n_features=top_n,
            n_estimators=50,
            cv_folds=3,
            min_data_points=50
        )
        
        if result.get('status') != 'success':
            return {"status": "error", "error": result.get('error', 'Analysis failed')}
        
        results = result.get('results', {})
        importance_scores = results.get('feature_importance', {})
        top_features = results.get('top_features', [])
        model_metrics = results.get('model_metrics', {})
        metadata = results.get('metadata', {})
        correlations = results.get('feature_correlations', {})
        
        test_metrics = model_metrics.get('test', {})
        
        # Build metric cards
        metric_cards = [
            {
                "label": "Model R²",
                "value": f"{test_metrics.get('r2', 0):.3f}",
                "description": "Predictive accuracy",
                "sentiment": "positive" if test_metrics.get('r2', 0) > 0.1 else "neutral"
            },
            {
                "label": "CV Score",
                "value": f"{test_metrics.get('cv_mean', 0):.3f}",
                "description": f"±{test_metrics.get('cv_std', 0):.3f}"
            },
            {
                "label": "Features",
                "value": str(metadata.get('n_features', 0)),
                "description": "Engineered features"
            },
            {
                "label": "Samples",
                "value": str(metadata.get('n_samples', 0)),
                "description": "Data points"
            },
            {
                "label": "Top Feature",
                "value": top_features[0]['feature'] if top_features else "N/A",
                "description": f"Score: {top_features[0].get('avg_score', 0):.4f}" if top_features else ""
            },
            {
                "label": "Target",
                "value": target.replace('_', ' ').title(),
                "description": f"Period: {period}"
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Model", "metric": "R² (Test)", "value": f"{test_metrics.get('r2', 0):.4f}"},
            {"category": "Model", "metric": "MAE", "value": f"{test_metrics.get('mae', 0):.4f}"},
            {"category": "Model", "metric": "RMSE", "value": f"{test_metrics.get('rmse', 0):.4f}"},
            {"category": "Model", "metric": "CV Mean", "value": f"{test_metrics.get('cv_mean', 0):.4f}"},
            {"category": "Model", "metric": "CV Std", "value": f"{test_metrics.get('cv_std', 0):.4f}"},
            {"category": "Data", "metric": "Features", "value": str(metadata.get('n_features', 0))},
            {"category": "Data", "metric": "Samples", "value": str(metadata.get('n_samples', 0))},
            {"category": "Config", "metric": "Target", "value": target},
            {"category": "Config", "metric": "Period", "value": period},
        ]
        
        # Add top features to stats
        for i, feat in enumerate(top_features[:10]):
            stats_table.append({
                "category": "Top Features",
                "metric": f"#{i+1} {feat['feature']}",
                "value": f"Score: {feat.get('avg_score', 0):.4f}"
            })
        
        # Build charts
        charts = {}
        
        # Importance bars (gain)
        if 'gain' in importance_scores:
            gain_chart = build_importance_bars_chart(importance_scores['gain'], top_n)
            if gain_chart:
                charts['importance_bars'] = gain_chart
        
        # Permutation scatter
        if 'gain' in importance_scores and 'permutation' in importance_scores:
            scatter_chart = build_permutation_scatter_chart(
                importance_scores['gain'], 
                importance_scores['permutation']
            )
            if scatter_chart:
                charts['permutation_scatter'] = scatter_chart
        
        # SHAP
        if 'shap' in importance_scores and importance_scores['shap']:
            shap_chart = build_shap_chart(importance_scores['shap'], top_n)
            if shap_chart:
                charts['shap_summary'] = shap_chart
        
        # Correlation heatmap
        if correlations.get('matrix') and correlations.get('feature_names'):
            corr_chart = build_correlation_heatmap(
                correlations['matrix'],
                correlations['feature_names']
            )
            if corr_chart:
                charts['correlation'] = corr_chart
        
        return {
            "status": "success",
            "tool_id": "feature_importance",
            "tickers": tickers,
            "metrics": {
                "r2": test_metrics.get('r2', 0),
                "cv_score": test_metrics.get('cv_mean', 0),
                "n_features": metadata.get('n_features', 0),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
            "summary": f"XGBoost feature importance analysis for {', '.join(tickers)}: "
                      f"R²={test_metrics.get('r2', 0):.3f}, top feature is '{top_features[0]['feature']}' "
                      f"with {metadata.get('n_features', 0)} engineered features.",
        }
        
    except Exception as e:
        logger.error(f"Feature importance execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
