"""
PCA & Eigen-Portfolios Tool
Principal Component Analysis for portfolio returns with factor loadings and eigen-portfolio construction
Based on StockPredictionAI approach following arima_forecast_tool.py and fft_denoising_tool.py patterns
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from dotenv import load_dotenv

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.charts.models import ChartSpec, ChartType, ChartPriority
from core.utils.risk_adapter import jsonify_results
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

load_dotenv()
logger = logging.getLogger(__name__)


async def _build_scree_plot(
    explained_variance: List[float],
    cumulative_variance: List[float],
    n_components: int,
    variance_thresholds: List[float],
    chart_id: str
) -> Dict[str, Any]:
    """Build scree plot showing explained variance by component"""

    try:
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=["Explained Variance by Principal Component"]
        )

        # Individual variance bars
        fig.add_trace(go.Bar(
            x=[f"PC{i+1}" for i in range(n_components)],
            y=explained_variance,
            name="Individual",
            marker_color='#2E86AB',
            opacity=0.7,
            hovertemplate='<b>%{x}</b><br>Variance: %{y:.2%}<extra></extra>'
        ))

        # Cumulative variance line
        fig.add_trace(go.Scatter(
            x=[f"PC{i+1}" for i in range(n_components)],
            y=cumulative_variance,
            name="Cumulative",
            mode='lines+markers',
            line=dict(color='red', width=2),
            marker=dict(size=8),
            yaxis='y2',
            hovertemplate='<b>%{x}</b><br>Cumulative: %{y:.2%}<extra></extra>'
        ))

        # Add variance threshold reference lines
        colors = ['green', 'orange', 'purple', 'brown']
        for idx, threshold in enumerate(variance_thresholds):
            color = colors[idx % len(colors)]
            fig.add_hline(
                y=threshold, line_dash="dash", line_color=color,
                annotation_text=f"{int(threshold*100)}% threshold", yref='y2'
            )

        fig.update_layout(
            title="PCA Scree Plot - Explained Variance",
            xaxis_title="Principal Component",
            yaxis_title="Explained Variance Ratio",
            yaxis2=dict(
                title="Cumulative Variance",
                overlaying='y',
                side='right',
                range=[0, 1.05]
            ),
            template="plotly_white",
            height=500,
            showlegend=True,
            legend=dict(x=0.7, y=0.95),
            hovermode='x unified'
        )

        return {
            'id': f"{chart_id}_scree",
            'title': "PCA Scree Plot",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Scree plot generation failed: {e}")
        return None


async def _build_loadings_heatmap(
    loadings: np.ndarray,
    tickers: List[str],
    n_components: int,
    chart_id: str
) -> Dict[str, Any]:
    """Build heatmap showing factor loadings (stock contributions to PCs)"""

    try:
        # Transpose for better visualization (tickers on Y-axis, PCs on X-axis)
        loadings_t = loadings.T  # shape: (n_tickers, n_components)

        fig = go.Figure(data=go.Heatmap(
            z=loadings_t,
            x=[f"PC{i+1}" for i in range(n_components)],
            y=tickers,
            colorscale='RdBu',
            zmid=0,
            text=[[f'{val:.3f}' for val in row] for row in loadings_t],
            texttemplate='%{text}',
            textfont={"size": 9},
            colorbar=dict(
                title="Loading",
                thickness=15,
                len=0.7
            ),
            hovertemplate='<b>%{y}</b> on %{x}<br>Loading: %{z:.4f}<extra></extra>'
        ))

        fig.update_layout(
            title="Factor Loadings Heatmap",
            xaxis_title="Principal Component",
            yaxis_title="Ticker",
            template="plotly_white",
            height=max(400, len(tickers) * 25),  # Scale with number of tickers
            width=max(600, n_components * 80),
            margin=dict(l=100, r=100, t=80, b=80),
            yaxis=dict(autorange='reversed')
        )

        return {
            'id': f"{chart_id}_loadings",
            'title': "Factor Loadings Heatmap",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Loadings heatmap generation failed: {e}")
        return None


async def _build_eigenportfolio_weights(
    eigen_portfolios: Dict[str, List[float]],
    tickers: List[str],
    chart_id: str
) -> Dict[str, Any]:
    """Build horizontal bar charts showing eigen-portfolio weights (long/short positions)"""

    try:
        n_portfolios = len(eigen_portfolios)
        n_tickers = len(tickers)

        # Increased spacing to prevent label overlap
        vertical_spacing = 0.25 if n_portfolios > 2 else 0.20

        # Vertical stack - one portfolio per row for clarity
        fig = make_subplots(
            rows=n_portfolios,
            cols=1,
            subplot_titles=[f"<b>Eigen-Portfolio {name}</b>" for name in eigen_portfolios.keys()],
            vertical_spacing=vertical_spacing,
            specs=[[{"type": "bar"}] for _ in range(n_portfolios)]
        )

        # Add horizontal bar chart for each eigen-portfolio
        for idx, (name, weights) in enumerate(eigen_portfolios.items()):
            row = idx + 1

            # Color bars: green for positive (long), red for negative (short)
            colors = ['#2E7D32' if w > 0 else '#C62828' for w in weights]

            # Show text only for bars with significant weights (>0.1 absolute value)
            text_values = []
            text_positions = []
            for w in weights:
                if abs(w) > 0.1:
                    text_values.append(f'{w:+.2f}')  # Reduced decimals for readability
                    text_positions.append('inside')
                else:
                    text_values.append('')
                    text_positions.append('none')

            # Horizontal bars for better label readability
            fig.add_trace(
                go.Bar(
                    y=tickers,
                    x=weights,
                    orientation='h',
                    name=name,
                    marker=dict(
                        color=colors,
                        line=dict(color='white', width=1)
                    ),
                    showlegend=False,
                    hovertemplate='<b>%{y}</b><br>Weight: %{x:.4f}<extra></extra>',
                    text=text_values,
                    textposition=text_positions,
                    textfont=dict(size=11, color='white', family='Arial Black')
                ),
                row=row,
                col=1
            )

            # Add zero line
            fig.add_vline(
                x=0, line_dash="solid", line_color="black", line_width=2,
                row=row, col=1
            )

            # Update X-axis for this subplot
            fig.update_xaxes(
                title_text="Weight" if row == n_portfolios else "",
                row=row, col=1,
                gridcolor='lightgray',
                zeroline=True,
                zerolinecolor='black',
                zerolinewidth=2,
                tickfont=dict(size=11),
                title_font=dict(size=12, color='#1f1f1f')
            )

            # Update Y-axis for this subplot - CRITICAL FIX for overlap
            fig.update_yaxes(
                row=row, col=1,
                autorange='reversed',
                tickfont=dict(size=12, family='Arial', color='#1f1f1f'),  # Larger, clearer font
                tickmode='linear',  # Ensure all tickers are shown
                dtick=1,  # One tick per ticker
                showgrid=False,  # Remove Y-axis gridlines for clarity
                automargin=True  # Auto-expand margin to fit labels
            )

        # Dynamic height: give more space per ticker to prevent overlap
        base_height = 120  # Base height per portfolio
        ticker_height = max(35, 50 - n_tickers)  # Scale down ticker spacing if many tickers
        total_height = n_portfolios * (base_height + n_tickers * ticker_height) + 120

        fig.update_layout(
            title={
                'text': "<b>Eigen-Portfolio Weights (Long/Short)</b>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#1f1f1f', 'family': 'Arial'}
            },
            template="plotly_white",
            height=total_height,
            width=900,  # Slightly wider for better readability
            margin=dict(l=120, r=80, t=100, b=80),  # More left margin for ticker labels
            hovermode='closest',
            paper_bgcolor='white',
            plot_bgcolor='#f9f9f9',
            font=dict(family='Arial', size=12)
        )

        # Update subplot title styling
        for annotation in fig['layout']['annotations']:
            annotation['font'] = dict(size=14, color='#1f1f1f', family='Arial')
            annotation['y'] = annotation['y'] + 0.01  # Slight upward adjustment

        return {
            'id': f"{chart_id}_eigenweights",
            'title': "Eigen-Portfolio Weights",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Eigen-portfolio weights chart failed: {e}")
        return None


async def _build_projection_scatter(
    returns_projected: np.ndarray,
    dates: List[str],
    tickers: List[str],
    chart_id: str
) -> Dict[str, Any]:
    """Build 2D scatter plot of returns projected onto first 2 PCs"""

    try:
        # Use first 2 components for 2D visualization
        if returns_projected.shape[1] < 2:
            return None

        pc1 = returns_projected[:, 0]
        pc2 = returns_projected[:, 1]

        fig = go.Figure(data=go.Scatter(
            x=pc1,
            y=pc2,
            mode='markers',
            marker=dict(
                size=6,
                color=np.arange(len(pc1)),
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Time")
            ),
            text=[f"{date}" for date in dates],
            hovertemplate='<b>%{text}</b><br>PC1: %{x:.4f}<br>PC2: %{y:.4f}<extra></extra>'
        ))

        # Add origin lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig.update_layout(
            title="Returns Projection on First 2 Principal Components",
            xaxis_title="PC1",
            yaxis_title="PC2",
            template="plotly_white",
            height=600,
            width=700,
            hovermode='closest'
        )

        return {
            'id': f"{chart_id}_projection",
            'title': "PCA 2D Projection",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Projection scatter plot failed: {e}")
        return None


async def analyze_pca_internal(
    tickers: List[str],
    n_components: Optional[int] = None,
    normalize: bool = True,
    period: str = "1Y",
    variance_thresholds: Optional[List[float]] = None,
    n_eigen_portfolios: Optional[int] = None,
    top_contributors_count: Optional[int] = None,
    min_data_points: Optional[int] = None
) -> dict:
    """Internal callable for Canvas - same logic as analyze_pca_eigen_portfolios but without @function_tool."""
    try:
        if variance_thresholds is None:
            variance_thresholds = [0.80, 0.95]
        if top_contributors_count is None:
            top_contributors_count = 5
        if min_data_points is None:
            min_data_points = 50

        if len(tickers) < 3:
            return {"status": "error", "error": "PCA requires at least 3 tickers"}

        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()
            logger.info(f"Fetching data for {len(tickers)} tickers...")
            returns_data = {}
            dates_common = None
            skipped_tickers = []
            valid_tickers = []

            for ticker in tickers:
                try:
                    result = await fmp_server.call_tool("get_historical_data", {
                        "symbol": ticker,
                        "period": period
                    })

                    if not result or not hasattr(result, 'content'):
                        logger.warning(f"No data for {ticker}, skipping...")
                        skipped_tickers.append({"ticker": ticker, "reason": "no_data"})
                        continue

                    data = safe_parse_json(result)
                    if not data or "dates" not in data:
                        logger.warning(f"No date data for {ticker}, skipping...")
                        skipped_tickers.append({"ticker": ticker, "reason": "no_date_data"})
                        continue

                    dates = data.get("dates", [])
                    prices = data.get("prices", []) or data.get("closes", [])

                    if not dates or not prices or len(dates) < min_data_points:
                        logger.warning(f"Insufficient data for {ticker} ({len(dates)} points), skipping...")
                        skipped_tickers.append({"ticker": ticker, "reason": f"insufficient_data ({len(dates)} points)"})
                        continue

                    df = pd.DataFrame({"date": pd.to_datetime(dates), "price": prices})
                    df = df.sort_values("date")
                    df['return'] = df['price'].pct_change()
                    df = df.dropna()
                    if df['return'].isna().any():
                        df['return'] = df['return'].fillna(0)

                    returns_data[ticker] = df
                    valid_tickers.append(ticker)

                    if dates_common is None:
                        dates_common = set(df['date'])
                    else:
                        dates_common = dates_common.intersection(set(df['date']))
                except Exception as e:
                    logger.warning(f"Error fetching data for {ticker}: {e}, skipping...")
                    skipped_tickers.append({"ticker": ticker, "reason": str(e)})
                    continue

            # Check if we have enough valid tickers after skipping
            if len(valid_tickers) < 3:
                return {
                    "status": "error",
                    "error": f"PCA requires at least 3 valid tickers. Only {len(valid_tickers)} had sufficient data.",
                    "skipped_tickers": skipped_tickers,
                    "valid_tickers": valid_tickers
                }

            # Update tickers to only valid ones
            tickers = valid_tickers

            # Now set n_components based on valid tickers
            if n_components is None:
                n_components = len(tickers)
            else:
                n_components = min(n_components, len(tickers))

            if n_eigen_portfolios is None:
                n_eigen_portfolios = min(4, n_components)
            else:
                n_eigen_portfolios = min(n_eigen_portfolios, n_components)

            if not dates_common or len(dates_common) < min_data_points:
                return {"status": "error", "error": f"Insufficient common dates: {len(dates_common)}"}

            dates_common_sorted = sorted(list(dates_common))
            returns_matrix = []

            for ticker in tickers:
                df = returns_data[ticker]
                df_aligned = df[df['date'].isin(dates_common_sorted)].sort_values('date')
                returns_matrix.append(df_aligned['return'].values)

            returns_matrix = np.array(returns_matrix).T

            if np.isnan(returns_matrix).any() or np.isinf(returns_matrix).any():
                returns_matrix = np.nan_to_num(returns_matrix, nan=0.0, posinf=0.0, neginf=0.0)

            variances = np.var(returns_matrix, axis=0)
            if np.any(variances < 1e-10):
                constant_tickers = [tickers[i] for i in range(len(tickers)) if variances[i] < 1e-10]
                return {"status": "error", "error": f"Constant returns detected: {constant_tickers}"}

            pca = PCA(n_components=n_components)

            if normalize:
                returns_mean = np.mean(returns_matrix, axis=0)
                returns_std = np.std(returns_matrix, axis=0)
                returns_std[returns_std < 1e-10] = 1.0
                returns_normalized = (returns_matrix - returns_mean) / returns_std
            else:
                returns_normalized = returns_matrix

            returns_projected = pca.fit_transform(returns_normalized)

            explained_variance = pca.explained_variance_ratio_.tolist()
            cumulative_variance = np.cumsum(explained_variance).tolist()
            loadings = pca.components_

            components_for_thresholds = {}
            for threshold in variance_thresholds:
                n_needed = next((i + 1 for i, cv in enumerate(cumulative_variance) if cv >= threshold), n_components)
                components_for_thresholds[f"{int(threshold*100)}pct"] = n_needed

            eigen_portfolios = {}
            for i in range(n_eigen_portfolios):
                weights = loadings[i, :]
                # Normalize weights so absolute values sum to 1 (tradeable portfolio)
                weights = weights / np.sum(np.abs(weights))
                eigen_portfolios[f"PC{i+1}"] = weights.tolist()

            factor_contributions = {}
            for i in range(n_components):
                loadings_pc = loadings[i, :]
                sorted_indices = np.argsort(np.abs(loadings_pc))[::-1]
                top_contributors = []
                for idx in sorted_indices[:top_contributors_count]:
                    top_contributors.append({
                        'ticker': tickers[idx],
                        'loading': float(loadings_pc[idx]),
                        'abs_loading': float(np.abs(loadings_pc[idx]))
                    })
                factor_contributions[f"PC{i+1}"] = top_contributors

            # Return summary (omit loadings_matrix to prevent context overflow)
            result = {
                'status': 'success',
                'tickers': tickers,
                'n_components': n_components,
                'period': period,
                'explained_variance': explained_variance,
                'cumulative_variance': cumulative_variance,
                'components_for_thresholds': components_for_thresholds,
                # Removed: loadings_matrix (large n_components × n_tickers array)
                'eigen_portfolios': eigen_portfolios,
                'factor_contributions': factor_contributions,  # Summary of top contributors
                'n_samples': len(dates_common_sorted),
                'date_range': [
                    dates_common_sorted[0].strftime('%Y-%m-%d'),
                    dates_common_sorted[-1].strftime('%Y-%m-%d')
                ],
            }

            # Include skipped tickers if any were skipped
            if skipped_tickers:
                result['skipped_tickers'] = skipped_tickers

            return result

        except Exception as e:
            logger.error(f"PCA analysis failed: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"PCA analysis failed: {e}")
        return {"status": "error", "error": str(e)}


@function_tool
async def analyze_pca_eigen_portfolios(
    tickers: List[str],
    n_components: Optional[int] = None,
    normalize: bool = True,
    period: str = "1Y",
    variance_thresholds: Optional[List[float]] = None,
    n_eigen_portfolios: Optional[int] = None,
    top_contributors_count: Optional[int] = None,
    min_data_points: Optional[int] = None
) -> dict:
    """
    Perform Principal Component Analysis on portfolio returns to identify dominant factors.

    Constructs eigen-portfolios (long/short strategies) based on principal components,
    calculates factor loadings showing which stocks drive each component, and provides
    explained variance analysis. Useful for factor-based risk decomposition and systematic
    strategy construction.

    Args:
        tickers: Stock symbols to analyze (minimum 3 for meaningful PCA)
        n_components: Number of components to extract (default: all, max: len(tickers))
        normalize: Standardize returns before PCA (default: True, recommended)
        period: Historical period for analysis (default: "1Y"). Use "1M", "3M", "6M", "1Y", "2Y", "5Y", "max"
        variance_thresholds: Threshold lines to show in scree plot (default: [0.80, 0.95])
        n_eigen_portfolios: Number of eigen-portfolios to construct (default: 4)
        top_contributors_count: Number of top contributors to show per PC (default: 5)
        min_data_points: Minimum required data points per ticker (default: 50)

    Returns:
        Dict with explained variance, factor loadings, eigen-portfolios, and visualization charts
    """
    try:
        # Set defaults if not provided
        if variance_thresholds is None:
            variance_thresholds = [0.80, 0.95]
        if top_contributors_count is None:
            top_contributors_count = 5
        if min_data_points is None:
            min_data_points = 50

        # Validation
        if len(tickers) < 3:
            raise ValueError("PCA requires at least 3 tickers for meaningful analysis")

        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Fetch historical data for all tickers
            logger.info(f"Fetching data for {len(tickers)} tickers...")
            returns_data = {}
            dates_common = None
            skipped_tickers = []
            valid_tickers = []

            for ticker in tickers:
                try:
                    data = await fmp_server.fetch_historical_data(ticker, period=period)

                    if not data or "dates" not in data:
                        logger.warning(f"No date data for {ticker}, skipping...")
                        skipped_tickers.append({"ticker": ticker, "reason": "no_date_data"})
                        continue

                    dates = data.get("dates", [])
                    prices = data.get("prices", []) or data.get("closes", [])

                    if not dates or not prices or len(dates) < min_data_points:
                        logger.warning(f"Insufficient data for {ticker} ({len(dates)} points), skipping...")
                        skipped_tickers.append({"ticker": ticker, "reason": f"insufficient_data ({len(dates)} points)"})
                        continue

                    # Create DataFrame
                    df = pd.DataFrame({
                        "date": pd.to_datetime(dates),
                        "price": prices
                    })
                    df = df.sort_values("date")

                    # Calculate returns
                    df['return'] = df['price'].pct_change()
                    df = df.dropna()

                    # Handle NaN in returns
                    if df['return'].isna().any():
                        df['return'] = df['return'].fillna(0)

                    returns_data[ticker] = df
                    valid_tickers.append(ticker)

                    # Track common dates (intersection)
                    if dates_common is None:
                        dates_common = set(df['date'])
                    else:
                        dates_common = dates_common.intersection(set(df['date']))
                except Exception as e:
                    logger.warning(f"Error fetching data for {ticker}: {e}, skipping...")
                    skipped_tickers.append({"ticker": ticker, "reason": str(e)})
                    continue

            # Check if we have enough valid tickers after skipping
            if len(valid_tickers) < 3:
                return {
                    'status': 'error',
                    'error': f"PCA requires at least 3 valid tickers. Only {len(valid_tickers)} had sufficient data.",
                    'skipped_tickers': skipped_tickers,
                    'valid_tickers': valid_tickers,
                    'calculation_type': 'pca_analysis'
                }

            # Update tickers to only valid ones
            tickers = valid_tickers

            # Now set n_components based on valid tickers
            if n_components is None:
                n_components = len(tickers)
            else:
                n_components = min(n_components, len(tickers))

            # Set n_eigen_portfolios default based on n_components
            if n_eigen_portfolios is None:
                n_eigen_portfolios = min(4, n_components)
            else:
                n_eigen_portfolios = min(n_eigen_portfolios, n_components)

            if not dates_common or len(dates_common) < min_data_points:
                raise ValueError(f"Insufficient common dates across tickers: {len(dates_common)} (need {min_data_points}+)")

            # Align all returns to common dates
            dates_common_sorted = sorted(list(dates_common))
            returns_matrix = []

            for ticker in tickers:
                df = returns_data[ticker]
                df_aligned = df[df['date'].isin(dates_common_sorted)].sort_values('date')
                returns_matrix.append(df_aligned['return'].values)

            # Shape: (n_samples, n_features) = (n_dates, n_tickers)
            returns_matrix = np.array(returns_matrix).T

            # Check for invalid values
            if np.isnan(returns_matrix).any() or np.isinf(returns_matrix).any():
                logger.warning("NaN or Inf detected in returns matrix, cleaning...")
                returns_matrix = np.nan_to_num(returns_matrix, nan=0.0, posinf=0.0, neginf=0.0)

            # Check for constant columns (zero variance)
            variances = np.var(returns_matrix, axis=0)
            if np.any(variances < 1e-10):
                constant_tickers = [tickers[i] for i in range(len(tickers)) if variances[i] < 1e-10]
                raise ValueError(f"Constant returns detected (zero variance): {constant_tickers}. Cannot perform PCA.")

            # Perform PCA
            logger.info(f"Running PCA with {n_components} components...")

            try:
                pca = PCA(n_components=n_components)

                if normalize:
                    # Standardize returns (mean=0, std=1)
                    returns_mean = np.mean(returns_matrix, axis=0)
                    returns_std = np.std(returns_matrix, axis=0)
                    returns_std[returns_std < 1e-10] = 1.0  # Prevent division by zero
                    returns_normalized = (returns_matrix - returns_mean) / returns_std
                else:
                    returns_normalized = returns_matrix

                # Fit PCA
                returns_projected = pca.fit_transform(returns_normalized)

            except np.linalg.LinAlgError as e:
                raise ValueError(f"PCA failed due to singular matrix: {e}. Try using fewer tickers or longer period.")

            # Extract results
            explained_variance = pca.explained_variance_ratio_.tolist()
            cumulative_variance = np.cumsum(explained_variance).tolist()
            loadings = pca.components_  # Shape: (n_components, n_features)

            # Find number of components needed for each variance threshold
            components_for_thresholds = {}
            for threshold in variance_thresholds:
                n_needed = next((i + 1 for i, cv in enumerate(cumulative_variance) if cv >= threshold), n_components)
                components_for_thresholds[f"{int(threshold*100)}pct"] = n_needed

            # Construct eigen-portfolios (normalized so absolute weights sum to 1)
            eigen_portfolios = {}
            for i in range(n_eigen_portfolios):
                weights = loadings[i, :]
                # Normalize weights so absolute values sum to 1 (tradeable portfolio)
                weights = weights / np.sum(np.abs(weights))
                eigen_portfolios[f"PC{i+1}"] = weights.tolist()

            # Factor loadings breakdown (top contributors per PC)
            factor_contributions = {}
            for i in range(n_components):
                loadings_pc = loadings[i, :]
                sorted_indices = np.argsort(np.abs(loadings_pc))[::-1]

                top_contributors = []
                for idx in sorted_indices[:top_contributors_count]:
                    top_contributors.append({
                        'ticker': tickers[idx],
                        'loading': float(loadings_pc[idx]),
                        'abs_loading': float(np.abs(loadings_pc[idx]))
                    })

                factor_contributions[f"PC{i+1}"] = top_contributors

            # Generate charts
            chart_id = f"pca_{abs(hash(str(tickers)))&0xFFFF:04x}"
            charts = []

            # 1. Scree plot
            scree_chart = await _build_scree_plot(
                explained_variance, cumulative_variance, n_components, variance_thresholds, chart_id
            )
            if scree_chart:
                charts.append(scree_chart)

            # 2. Loadings heatmap
            loadings_chart = await _build_loadings_heatmap(
                loadings, tickers, n_components, chart_id
            )
            if loadings_chart:
                charts.append(loadings_chart)

            # 3. Eigen-portfolio weights
            eigen_weights_chart = await _build_eigenportfolio_weights(
                eigen_portfolios, tickers, chart_id
            )
            if eigen_weights_chart:
                charts.append(eigen_weights_chart)

            # 4. 2D projection scatter
            projection_chart = await _build_projection_scatter(
                returns_projected, [d.strftime('%Y-%m-%d') for d in dates_common_sorted], tickers, chart_id
            )
            if projection_chart:
                charts.append(projection_chart)

            charts = wrap_plotly_charts(charts, default_type="pca_chart")

            # Prepare results (omit large arrays to prevent context overflow)
            # Full loadings matrix is embedded in cached charts
            results = {
                'explained_variance': {
                    'individual': explained_variance,
                    'cumulative': cumulative_variance,
                    'components_for_thresholds': components_for_thresholds
                },
                'factor_loadings': {
                    # Removed: loadings_matrix (n_components × n_tickers, embedded in charts)
                    'top_contributors': factor_contributions  # Summary of most important loadings
                },
                'eigen_portfolios': eigen_portfolios,
                'metadata': {
                    'n_samples': len(dates_common_sorted),
                    'n_tickers': len(tickers),
                    'n_components': n_components,
                    'normalized': normalize,
                    'period': period,
                    'variance_thresholds': variance_thresholds,
                    'n_eigen_portfolios': n_eigen_portfolios,
                    'top_contributors_count': top_contributors_count,
                    'min_data_points': min_data_points,
                    'date_range': [
                        dates_common_sorted[0].strftime('%Y-%m-%d'),
                        dates_common_sorted[-1].strftime('%Y-%m-%d')
                    ]
                }
            }

            # Include skipped tickers info if any were skipped
            if skipped_tickers:
                results['skipped_tickers'] = skipped_tickers

            return jsonify_results({
                'status': 'success',
                'results': results,
                'tickers': tickers,
                'n_components': n_components,
                'period': period,
                'charts': charts,
                'skipped_tickers': skipped_tickers if skipped_tickers else None
            })

        except Exception as e:
            logger.error(f"PCA analysis failed: {e}")
            error_type = 'data_error' if any(
                kw in str(e).lower() for kw in ['no data', 'insufficient', 'singular', 'constant']
            ) else 'general_error'

            return {
                'status': 'error',
                'error': str(e),
                'error_type': error_type,
                'calculation_type': 'pca_analysis'
            }

    except Exception as e:
        logger.error(f"PCA analysis failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'calculation_type': 'pca_analysis'
        }
