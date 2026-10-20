"""
Graph Theory Portfolio Analyzer - Network-Based Risk Analysis

Models a portfolio as a correlation network and applies graph theory to identify:
- Minimum Spanning Tree (backbone of correlation structure)
- Bridge stocks (single points of failure)
- Community clusters (stocks that move together)
- Centrality scores (systemic importance)

Philosophy:
-----------
Traditional correlation matrices show pairwise relationships but miss the STRUCTURE.
Graph theory reveals:
- Which stocks are "bridges" connecting otherwise separate groups
- Which positions contribute most to systemic portfolio risk
- Natural clusters that will move together in stress
- The "backbone" of relationships (MST) that matter most

Mathematical Foundation:
-----------------------
1. Build weighted graph: nodes = stocks, edges = |correlation|
2. MST via Prim/Kruskal: backbone connections that explain most correlation
3. Bridges via DFS: edges whose removal disconnects the graph
4. Communities via Louvain: modularity-optimizing partition
5. Centrality via eigenvector iteration: importance weighted by neighbor importance

Alpha Application:
-----------------
- High bridge count + high density = fragile portfolio (single failures cascade)
- Few communities with high internal correlation = false diversification
- High centrality stocks = where to focus hedging
- MST structure reveals hidden dependencies

NO HARDCODING: Uses dynamic field discovery for all market data.
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import uuid
import json
from collections import defaultdict

# Agent framework
from agents import function_tool

# Internal utilities
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results

# Visualization
from core.visualization.plotly_charts import RiskCharts
from core.agents.risk_tools.shared import register_chart_handle

logger = logging.getLogger(__name__)


# =============================================================================
# DATA FETCHING (Reused pattern from correlation_matrix_tool)
# =============================================================================

def _discover_price_field(data: Dict[str, Any]) -> Optional[str]:
    """Dynamically discover the price field in FMP data."""
    if not data or not isinstance(data, dict):
        return None
    
    price_indicators = ['close', 'price', 'adj_close', 'adjusted']
    available_keys = list(data.keys())
    
    for indicator in price_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key
    return None


def _discover_date_field(data: Dict[str, Any]) -> Optional[str]:
    """Dynamically discover the date field in FMP data."""
    if not data or not isinstance(data, dict):
        return None
    
    date_indicators = ['date', 'time', 'timestamp']
    available_keys = list(data.keys())
    
    for indicator in date_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key
    return None


async def _fetch_price_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int
) -> Optional[pd.DataFrame]:
    """
    Fetch historical price data with dynamic field discovery.
    Returns None if ticker is invalid/not found (graceful skip).
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    try:
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        
        if not result or not hasattr(result, 'content'):
            logger.warning(f"No data returned for {ticker}")
            return None
        
        data = safe_parse_json(result)
        
        if not data or not isinstance(data, dict):
            logger.warning(f"Invalid data structure for {ticker}")
            return None
        
        date_field = _discover_date_field(data)
        price_field = _discover_price_field(data)
        
        if not date_field or not price_field:
            logger.warning(f"Could not discover date/price fields for {ticker}")
            return None
        
        dates = data[date_field]
        prices = data[price_field]
        
        if not dates or not prices or len(dates) != len(prices):
            return None
        
        df = pd.DataFrame({
            'date': pd.to_datetime(dates),
            'price': pd.to_numeric(prices, errors='coerce')
        })
        
        df = df.sort_values('date').reset_index(drop=True)
        df = df.dropna()
        
        if len(df) < 20:  # Need minimum data for meaningful analysis
            logger.warning(f"Insufficient data for {ticker}: {len(df)} points")
            return None
        
        return df
    
    except Exception as e:
        logger.warning(f"Error fetching {ticker}: {e}")
        return None


def _calculate_returns_matrix(
    price_data: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Calculate returns matrix from price data."""
    merged = None
    
    for ticker, df in price_data.items():
        df_copy = df[['date', 'price']].copy()
        df_copy = df_copy.rename(columns={'price': ticker})
        
        if merged is None:
            merged = df_copy
        else:
            merged = pd.merge(merged, df_copy, on='date', how='inner')
    
    if merged is None or len(merged) < 2:
        raise ValueError("Insufficient overlapping data")
    
    returns_df = merged.set_index('date')
    
    for ticker in price_data.keys():
        returns_df[ticker] = np.log(returns_df[ticker] / returns_df[ticker].shift(1))
    
    returns_df = returns_df.iloc[1:].dropna()
    return returns_df


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def _build_correlation_graph(
    corr_matrix: pd.DataFrame,
    correlation_threshold: float = 0.3
) -> Dict[str, Any]:
    """
    Build graph representation from correlation matrix.
    
    Args:
        corr_matrix: Correlation matrix as DataFrame
        correlation_threshold: Minimum |correlation| to create an edge
    
    Returns:
        Graph dict with nodes, edges, and adjacency list
    """
    tickers = list(corr_matrix.columns)
    n = len(tickers)
    
    nodes = tickers
    edges = []  # List of (node_i, node_j, weight) tuples
    adjacency = defaultdict(list)  # node -> [(neighbor, weight), ...]
    
    for i in range(n):
        for j in range(i + 1, n):
            corr = abs(corr_matrix.iloc[i, j])
            if corr >= correlation_threshold:
                ticker_i, ticker_j = tickers[i], tickers[j]
                # Weight = correlation strength (higher = stronger connection)
                edges.append((ticker_i, ticker_j, corr))
                adjacency[ticker_i].append((ticker_j, corr))
                adjacency[ticker_j].append((ticker_i, corr))
    
    return {
        "nodes": nodes,
        "edges": edges,
        "adjacency": dict(adjacency),
        "num_nodes": n,
        "num_edges": len(edges)
    }


# =============================================================================
# GRAPH METRICS
# =============================================================================

def _calculate_graph_metrics(graph: Dict[str, Any]) -> Dict[str, float]:
    """Calculate basic graph metrics."""
    n = graph["num_nodes"]
    e = graph["num_edges"]
    
    # Density: actual edges / possible edges
    max_edges = n * (n - 1) / 2
    density = e / max_edges if max_edges > 0 else 0
    
    # Average degree
    degrees = [len(graph["adjacency"].get(node, [])) for node in graph["nodes"]]
    avg_degree = np.mean(degrees) if degrees else 0
    
    # Clustering coefficient (local)
    clustering_coeffs = []
    for node in graph["nodes"]:
        neighbors = [n for n, _ in graph["adjacency"].get(node, [])]
        k = len(neighbors)
        if k < 2:
            clustering_coeffs.append(0)
            continue
        
        # Count edges between neighbors
        neighbor_edges = 0
        for i, n1 in enumerate(neighbors):
            for n2 in neighbors[i+1:]:
                # Check if n1-n2 edge exists
                if any(neighbor == n2 for neighbor, _ in graph["adjacency"].get(n1, [])):
                    neighbor_edges += 1
        
        max_neighbor_edges = k * (k - 1) / 2
        clustering_coeffs.append(neighbor_edges / max_neighbor_edges if max_neighbor_edges > 0 else 0)
    
    avg_clustering = np.mean(clustering_coeffs) if clustering_coeffs else 0
    
    return {
        "density": round(density, 4),
        "avg_degree": round(avg_degree, 2),
        "avg_clustering_coefficient": round(avg_clustering, 4),
        "num_nodes": n,
        "num_edges": e
    }


# =============================================================================
# MINIMUM SPANNING TREE (Prim's Algorithm)
# =============================================================================

def _minimum_spanning_tree(
    graph: Dict[str, Any],
    corr_matrix: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Find Minimum Spanning Tree using Prim's algorithm.
    
    For correlation networks, we want MAXIMUM spanning tree (strongest connections)
    so we negate weights or use correlation directly.
    """
    nodes = graph["nodes"]
    if len(nodes) < 2:
        return []
    
    # Build adjacency with actual correlation values (not just above threshold)
    full_adj = defaultdict(list)
    for i, node_i in enumerate(nodes):
        for j, node_j in enumerate(nodes):
            if i < j:
                corr = abs(corr_matrix.loc[node_i, node_j])
                full_adj[node_i].append((node_j, corr))
                full_adj[node_j].append((node_i, corr))
    
    # Prim's algorithm for MAXIMUM spanning tree
    mst_edges = []
    visited = {nodes[0]}
    available_edges = [(corr, nodes[0], neighbor) for neighbor, corr in full_adj[nodes[0]]]
    
    import heapq
    # Use negative correlation for max heap behavior
    available_edges = [(-corr, n1, n2) for corr, n1, n2 in available_edges]
    heapq.heapify(available_edges)
    
    while available_edges and len(visited) < len(nodes):
        neg_corr, node1, node2 = heapq.heappop(available_edges)
        
        if node2 in visited:
            continue
        
        visited.add(node2)
        mst_edges.append({
            "source": node1,
            "target": node2,
            "correlation": round(-neg_corr, 4)
        })
        
        for neighbor, corr in full_adj[node2]:
            if neighbor not in visited:
                heapq.heappush(available_edges, (-corr, node2, neighbor))
    
    return mst_edges


# =============================================================================
# BRIDGE DETECTION (Tarjan's Algorithm)
# =============================================================================

def _find_bridges(graph: Dict[str, Any]) -> List[str]:
    """
    Find bridge nodes - nodes whose removal disconnects the graph.
    These are critical risk points in the portfolio network.
    """
    nodes = graph["nodes"]
    adj = graph["adjacency"]
    
    if len(nodes) < 2:
        return []
    
    visited = set()
    disc = {}  # Discovery time
    low = {}   # Lowest reachable discovery time
    parent = {}
    bridges = set()  # Set of (node1, node2) tuples
    time = [0]
    
    def dfs(u):
        visited.add(u)
        disc[u] = low[u] = time[0]
        time[0] += 1
        
        for v, _ in adj.get(u, []):
            if v not in visited:
                parent[v] = u
                dfs(v)
                low[u] = min(low[u], low[v])
                
                # Bridge condition: if lowest reachable from v is below u
                if low[v] > disc[u]:
                    bridges.add((u, v))
            elif v != parent.get(u):
                low[u] = min(low[u], disc[v])
    
    # Run DFS from each unvisited node (handles disconnected graphs)
    for node in nodes:
        if node not in visited:
            parent[node] = None
            dfs(node)
    
    # Extract unique bridge nodes (nodes that appear in bridge edges)
    bridge_nodes = set()
    for n1, n2 in bridges:
        bridge_nodes.add(n1)
        bridge_nodes.add(n2)
    
    return list(bridge_nodes)


# =============================================================================
# COMMUNITY DETECTION (Louvain-style modularity optimization)
# =============================================================================

def _detect_communities(
    graph: Dict[str, Any],
    corr_matrix: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Detect communities using a greedy modularity optimization approach.
    Simplified Louvain-style algorithm.
    """
    nodes = graph["nodes"]
    n = len(nodes)
    
    if n < 2:
        return [{"id": 1, "stocks": nodes, "avg_internal_correlation": 1.0}]
    
    # Initialize: each node in its own community
    node_to_community = {node: i for i, node in enumerate(nodes)}
    
    # Total edge weight
    total_weight = sum(edge[2] for edge in graph["edges"])
    if total_weight == 0:
        total_weight = 1
    
    # Node degrees (sum of edge weights)
    node_degrees = defaultdict(float)
    for n1, n2, w in graph["edges"]:
        node_degrees[n1] += w
        node_degrees[n2] += w
    
    # Greedy optimization
    improved = True
    max_iterations = 10
    iteration = 0
    
    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        
        for node in nodes:
            current_community = node_to_community[node]
            
            # Find neighboring communities
            neighbor_communities = set()
            for neighbor, _ in graph["adjacency"].get(node, []):
                neighbor_communities.add(node_to_community[neighbor])
            
            if not neighbor_communities:
                continue
            
            # Calculate modularity gain for each potential move
            best_community = current_community
            best_gain = 0
            
            for target_community in neighbor_communities:
                if target_community == current_community:
                    continue
                
                # Simplified modularity gain calculation
                edges_to_target = sum(
                    w for n2, w in graph["adjacency"].get(node, [])
                    if node_to_community[n2] == target_community
                )
                edges_in_current = sum(
                    w for n2, w in graph["adjacency"].get(node, [])
                    if node_to_community[n2] == current_community and n2 != node
                )
                
                gain = edges_to_target - edges_in_current
                
                if gain > best_gain:
                    best_gain = gain
                    best_community = target_community
            
            if best_community != current_community:
                node_to_community[node] = best_community
                improved = True
    
    # Build community list
    communities = defaultdict(list)
    for node, comm in node_to_community.items():
        communities[comm].append(node)
    
    # Calculate internal correlation for each community
    result = []
    for comm_id, members in communities.items():
        if len(members) < 2:
            avg_corr = 1.0
        else:
            corrs = []
            for i, m1 in enumerate(members):
                for m2 in members[i+1:]:
                    corrs.append(abs(corr_matrix.loc[m1, m2]))
            avg_corr = np.mean(corrs) if corrs else 0
        
        result.append({
            "id": len(result) + 1,
            "stocks": members,
            "size": len(members),
            "avg_internal_correlation": round(avg_corr, 4)
        })
    
    # Sort by size descending
    result.sort(key=lambda x: x["size"], reverse=True)
    
    return result


# =============================================================================
# CENTRALITY MEASURES
# =============================================================================

def _calculate_centrality(
    graph: Dict[str, Any],
    corr_matrix: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Calculate multiple centrality measures for each node.
    
    Returns list sorted by eigenvector centrality (most important first).
    """
    nodes = graph["nodes"]
    n = len(nodes)
    
    if n == 0:
        return []
    
    # Degree centrality (normalized)
    degree_centrality = {}
    for node in nodes:
        degree = sum(w for _, w in graph["adjacency"].get(node, []))
        degree_centrality[node] = degree
    
    max_degree = max(degree_centrality.values()) if degree_centrality else 1
    degree_centrality = {k: v / max_degree for k, v in degree_centrality.items()}
    
    # Betweenness centrality (simplified - count of shortest paths through node)
    betweenness = {node: 0 for node in nodes}
    
    for source in nodes:
        # BFS from source
        dist = {source: 0}
        paths = {source: 1}
        queue = [source]
        order = []
        
        while queue:
            current = queue.pop(0)
            order.append(current)
            
            for neighbor, _ in graph["adjacency"].get(current, []):
                if neighbor not in dist:
                    dist[neighbor] = dist[current] + 1
                    paths[neighbor] = 0
                    queue.append(neighbor)
                
                if dist[neighbor] == dist[current] + 1:
                    paths[neighbor] += paths[current]
        
        # Accumulate betweenness
        delta = {node: 0 for node in nodes}
        while order:
            w = order.pop()
            for v, _ in graph["adjacency"].get(w, []):
                if dist.get(v, float('inf')) == dist.get(w, 0) - 1:
                    delta[v] += (paths.get(v, 0) / paths.get(w, 1)) * (1 + delta[w])
            
            if w != source:
                betweenness[w] += delta[w]
    
    # Normalize betweenness
    max_between = max(betweenness.values()) if max(betweenness.values()) > 0 else 1
    betweenness = {k: v / max_between for k, v in betweenness.items()}
    
    # Eigenvector centrality (power iteration)
    eigenvector = {node: 1.0 for node in nodes}
    
    for _ in range(50):  # Power iteration
        new_eigenvector = {}
        for node in nodes:
            # Sum of neighbor centralities weighted by correlation
            score = sum(
                eigenvector[neighbor] * weight
                for neighbor, weight in graph["adjacency"].get(node, [])
            )
            new_eigenvector[node] = score if score > 0 else 0.01
        
        # Normalize
        norm = np.sqrt(sum(v**2 for v in new_eigenvector.values()))
        if norm > 0:
            eigenvector = {k: v / norm for k, v in new_eigenvector.items()}
    
    # Build result
    result = []
    for node in nodes:
        result.append({
            "ticker": node,
            "eigenvector_centrality": round(eigenvector.get(node, 0), 4),
            "degree_centrality": round(degree_centrality.get(node, 0), 4),
            "betweenness_centrality": round(betweenness.get(node, 0), 4),
            "risk_contribution": round(
                (eigenvector.get(node, 0) + betweenness.get(node, 0)) / 2, 4
            )
        })
    
    # Sort by eigenvector centrality
    result.sort(key=lambda x: x["eigenvector_centrality"], reverse=True)
    
    return result


# =============================================================================
# THEORETICAL BENCHMARKS (Random Graph Theory - Erdős–Rényi Model)
# =============================================================================

def _calculate_theoretical_benchmarks(
    n_nodes: int,
    edge_probability: float,
    correlation_threshold: float
) -> Dict[str, Dict[str, float]]:
    """
    Calculate theoretical expectations from random graph theory.
    
    Uses Erdős–Rényi G(n, p) model to establish baselines:
    - Expected density
    - Expected clustering coefficient
    - Expected number of communities
    - Expected bridge probability
    
    These provide statistically grounded benchmarks instead of hardcoded thresholds.
    
    Args:
        n_nodes: Number of nodes in graph
        edge_probability: Probability of edge existing (from avg correlation above threshold)
        correlation_threshold: The threshold used to create edges
    """
    # Erdős–Rényi expected values for G(n, p)
    
    # Expected density = p (by definition)
    expected_density = edge_probability
    
    # Expected clustering coefficient = p (in random graph, prob of triangle = p^2 for each pair)
    expected_clustering = edge_probability
    
    # Expected number of communities (heuristic based on modularity theory)
    # Random graphs have ~sqrt(n) weakly connected communities on average
    # But with high p, graph is likely fully connected -> 1 community
    if edge_probability > 0.5:
        expected_communities = 1.5
    else:
        expected_communities = max(1, np.sqrt(n_nodes) * (1 - edge_probability))
    
    # Bridge probability in random graph
    # For connected random graph, expected bridges ≈ 0 when p > ln(n)/n
    connectivity_threshold = np.log(n_nodes) / n_nodes if n_nodes > 1 else 0.5
    if edge_probability > connectivity_threshold * 2:
        expected_bridges = 0.1  # Very few expected
    else:
        expected_bridges = n_nodes * 0.1  # Some expected
    
    # Standard deviations (estimated from binomial/Poisson approximations)
    # Density std ≈ sqrt(p(1-p)/m) where m = n(n-1)/2
    m = n_nodes * (n_nodes - 1) / 2 if n_nodes > 1 else 1
    density_std = np.sqrt(edge_probability * (1 - edge_probability) / max(m, 1))
    
    # Clustering std (empirical approximation)
    clustering_std = 0.15  # Typical variance in clustering
    
    # Community count std
    community_std = np.sqrt(expected_communities) * 0.5
    
    # Bridge count std
    bridge_std = np.sqrt(expected_bridges + 1)
    
    return {
        "density": {
            "expected": expected_density,
            "std": max(density_std, 0.05)  # Floor to prevent division issues
        },
        "clustering": {
            "expected": expected_clustering,
            "std": max(clustering_std, 0.05)
        },
        "communities": {
            "expected": expected_communities,
            "std": max(community_std, 0.5)
        },
        "bridges": {
            "expected": expected_bridges,
            "std": max(bridge_std, 0.5)
        }
    }


def _calculate_z_score(observed: float, expected: float, std: float) -> float:
    """Calculate z-score with safe division."""
    if std <= 0:
        std = 0.01
    return (observed - expected) / std


def _assess_contagion_risk(
    graph_metrics: Dict[str, float],
    bridges: List[str],
    communities: List[Dict[str, Any]],
    centrality: List[Dict[str, Any]],
    correlation_threshold: float,
    avg_correlation: float
) -> Dict[str, Any]:
    """
    Generate risk assessment using z-score benchmarking against random graph theory.
    
    Instead of hardcoded thresholds, we compare portfolio graph metrics to 
    theoretical expectations from the Erdős–Rényi random graph model.
    
    Risk is measured in standard deviations from what a "random" portfolio 
    of the same size and correlation structure would exhibit.
    
    Z-score interpretation:
        |z| < 1.0: Within normal range
        |z| 1.0-2.0: Notable deviation
        |z| > 2.0: Significant deviation (95th percentile)
        |z| > 2.5: Extreme deviation (99th percentile)
    """
    n_nodes = graph_metrics["num_nodes"]
    observed_density = graph_metrics["density"]
    observed_clustering = graph_metrics["avg_clustering_coefficient"]
    n_bridges = len(bridges)
    n_communities = len(communities)
    
    # Estimate edge probability from correlation structure
    # Higher avg correlation above threshold = higher expected edge probability
    edge_probability = min(0.9, max(0.1, avg_correlation / (1 + correlation_threshold)))
    
    # Get theoretical benchmarks
    benchmarks = _calculate_theoretical_benchmarks(n_nodes, edge_probability, correlation_threshold)
    
    # Calculate z-scores for each metric
    z_scores = {
        "density": _calculate_z_score(
            observed_density,
            benchmarks["density"]["expected"],
            benchmarks["density"]["std"]
        ),
        "clustering": _calculate_z_score(
            observed_clustering,
            benchmarks["clustering"]["expected"],
            benchmarks["clustering"]["std"]
        ),
        "communities": _calculate_z_score(
            n_communities,
            benchmarks["communities"]["expected"],
            benchmarks["communities"]["std"]
        ),
        "bridges": _calculate_z_score(
            n_bridges,
            benchmarks["bridges"]["expected"],
            benchmarks["bridges"]["std"]
        )
    }
    
    # Build risk factors based on z-scores (not hardcoded thresholds)
    risk_factors = []
    recommendations = []
    
    # Density analysis
    if z_scores["density"] > 2.0:
        risk_factors.append({
            "metric": "density",
            "observed": round(observed_density, 3),
            "expected": round(benchmarks["density"]["expected"], 3),
            "z_score": round(z_scores["density"], 2),
            "interpretation": "Significantly higher than expected - portfolio is more interconnected than random",
            "severity": "high"
        })
        recommendations.append("Add uncorrelated assets to reduce network density")
    elif z_scores["density"] > 1.0:
        risk_factors.append({
            "metric": "density",
            "observed": round(observed_density, 3),
            "expected": round(benchmarks["density"]["expected"], 3),
            "z_score": round(z_scores["density"], 2),
            "interpretation": "Above expected density - moderate interconnection",
            "severity": "medium"
        })
    
    # Clustering analysis
    if z_scores["clustering"] > 2.0:
        risk_factors.append({
            "metric": "clustering",
            "observed": round(observed_clustering, 3),
            "expected": round(benchmarks["clustering"]["expected"], 3),
            "z_score": round(z_scores["clustering"], 2),
            "interpretation": "High clustering - positions form tight, correlated groups",
            "severity": "high"
        })
        recommendations.append("Diversify within clusters to reduce local correlation")
    elif z_scores["clustering"] > 1.0:
        risk_factors.append({
            "metric": "clustering",
            "observed": round(observed_clustering, 3),
            "expected": round(benchmarks["clustering"]["expected"], 3),
            "z_score": round(z_scores["clustering"], 2),
            "interpretation": "Above-average clustering",
            "severity": "medium"
        })
    
    # Community analysis (fewer communities = less diversified)
    if z_scores["communities"] < -1.5:
        risk_factors.append({
            "metric": "communities",
            "observed": n_communities,
            "expected": round(benchmarks["communities"]["expected"], 1),
            "z_score": round(z_scores["communities"], 2),
            "interpretation": "Fewer communities than expected - limited structural diversification",
            "severity": "high"
        })
        recommendations.append("Portfolio clusters into few groups; add cross-sector positions")
    elif z_scores["communities"] < -0.5:
        risk_factors.append({
            "metric": "communities",
            "observed": n_communities,
            "expected": round(benchmarks["communities"]["expected"], 1),
            "z_score": round(z_scores["communities"], 2),
            "interpretation": "Below-average community count",
            "severity": "medium"
        })
    
    # Bridge analysis
    if z_scores["bridges"] > 2.0:
        risk_factors.append({
            "metric": "bridges",
            "observed": n_bridges,
            "expected": round(benchmarks["bridges"]["expected"], 1),
            "z_score": round(z_scores["bridges"], 2),
            "interpretation": f"More bridge nodes than expected: {', '.join(bridges[:3])}",
            "severity": "high"
        })
        if bridges:
            recommendations.append(f"Hedge bridge stocks (single points of failure): {', '.join(bridges[:2])}")
    elif n_bridges > 0 and z_scores["bridges"] > 1.0:
        risk_factors.append({
            "metric": "bridges",
            "observed": n_bridges,
            "expected": round(benchmarks["bridges"]["expected"], 1),
            "z_score": round(z_scores["bridges"], 2),
            "interpretation": f"Some bridge nodes detected: {', '.join(bridges[:3])}",
            "severity": "medium"
        })
    
    # Centrality concentration (use Gini coefficient of centrality distribution)
    if centrality:
        centralities = [c["eigenvector_centrality"] for c in centrality]
        mean_cent = np.mean(centralities)
        std_cent = np.std(centralities)
        
        # High std relative to mean = concentrated centrality
        if mean_cent > 0:
            concentration_ratio = std_cent / mean_cent
            if concentration_ratio > 1.0:
                top_stock = centrality[0]["ticker"]
                risk_factors.append({
                    "metric": "centrality_concentration",
                    "top_stock": top_stock,
                    "concentration_ratio": round(concentration_ratio, 2),
                    "interpretation": f"Centrality concentrated in {top_stock} - single point of systemic risk",
                    "severity": "high"
                })
                recommendations.append(f"Hedge {top_stock} - it's the most systemically connected position")
            elif concentration_ratio > 0.5:
                risk_factors.append({
                    "metric": "centrality_concentration",
                    "top_stock": centrality[0]["ticker"],
                    "concentration_ratio": round(concentration_ratio, 2),
                    "interpretation": "Moderate centrality concentration",
                    "severity": "medium"
                })
    
    # Calculate composite risk score from z-scores
    # Weight by importance: density & clustering matter most for contagion
    weighted_z = (
        abs(z_scores["density"]) * 0.35 +
        abs(z_scores["clustering"]) * 0.25 +
        abs(z_scores["bridges"]) * 0.25 +
        max(0, -z_scores["communities"]) * 0.15  # Only penalize fewer communities
    )
    
    # Risk level from composite z-score
    if weighted_z > 2.0:
        risk_level = "HIGH"
        risk_percentile = min(99, 50 + weighted_z * 20)
        summary = f"Portfolio structure is {weighted_z:.1f}σ above expected contagion risk"
    elif weighted_z > 1.0:
        risk_level = "MODERATE"
        risk_percentile = 50 + weighted_z * 20
        summary = f"Portfolio structure is {weighted_z:.1f}σ above baseline - some contagion risk"
    elif weighted_z > 0.5:
        risk_level = "LOW-MODERATE"
        risk_percentile = 50 + weighted_z * 20
        summary = f"Portfolio structure is near expected baseline ({weighted_z:.1f}σ)"
    else:
        risk_level = "LOW"
        risk_percentile = 50 + weighted_z * 20
        summary = "Portfolio structure shows good diversification relative to theory"
    
    # Diversification score (inverse normalized)
    diversification_score = round(max(0, min(10, 5 - weighted_z * 2)), 1)
    
    return {
        "contagion_risk": risk_level,
        "composite_z_score": round(weighted_z, 2),
        "risk_percentile": round(risk_percentile, 0),
        "diversification_score": diversification_score,
        "benchmarks": {
            "model": "Erdős–Rényi G(n,p)",
            "n_nodes": n_nodes,
            "edge_probability": round(edge_probability, 3),
            "theoretical_expectations": {
                k: round(v["expected"], 3) for k, v in benchmarks.items()
            }
        },
        "z_scores": {k: round(v, 2) for k, v in z_scores.items()},
        "risk_factors": risk_factors,
        "recommendations": recommendations,
        "summary": summary
    }


# =============================================================================
# VISUALIZATION
# =============================================================================

def _build_network_chart(
    graph: Dict[str, Any],
    communities: List[Dict[str, Any]],
    centrality: List[Dict[str, Any]],
    mst_edges: List[Dict[str, Any]],
    chart_id: str
) -> Dict[str, Any]:
    """Build network visualization as Plotly figure."""
    import plotly.graph_objects as go
    
    nodes = graph["nodes"]
    n = len(nodes)
    
    if n == 0:
        return None
    
    # Create community color mapping
    community_colors = {}
    color_palette = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4']
    for comm in communities:
        color = color_palette[comm["id"] % len(color_palette)]
        for stock in comm["stocks"]:
            community_colors[stock] = color
    
    # Create centrality size mapping
    centrality_map = {c["ticker"]: c["eigenvector_centrality"] for c in centrality}
    
    # Generate node positions (circular layout)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    positions = {node: (np.cos(angles[i]), np.sin(angles[i])) for i, node in enumerate(nodes)}
    
    # Create edge traces (MST edges in bold, others lighter)
    mst_set = {(e["source"], e["target"]) for e in mst_edges}
    mst_set.update({(e["target"], e["source"]) for e in mst_edges})
    
    edge_traces = []
    
    # Regular edges (faint)
    for n1, n2, corr in graph["edges"]:
        if (n1, n2) not in mst_set:
            x0, y0 = positions[n1]
            x1, y1 = positions[n2]
            edge_traces.append(go.Scatter(
                x=[x0, x1, None], y=[y0, y1, None],
                mode='lines',
                line=dict(width=1, color='rgba(200, 200, 200, 0.3)'),
                hoverinfo='skip',
                showlegend=False
            ))
    
    # MST edges (bold)
    for edge in mst_edges:
        x0, y0 = positions[edge["source"]]
        x1, y1 = positions[edge["target"]]
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode='lines',
            line=dict(width=2.5, color='#1E40AF'),
            hoverinfo='skip',
            showlegend=False
        ))
    
    # Node trace
    node_x = [positions[node][0] for node in nodes]
    node_y = [positions[node][1] for node in nodes]
    node_colors = [community_colors.get(node, '#6B7280') for node in nodes]
    node_sizes = [20 + 30 * centrality_map.get(node, 0.5) for node in nodes]
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color='white')
        ),
        text=nodes,
        textposition='top center',
        textfont=dict(size=10, color='#374151'),
        hovertemplate='<b>%{text}</b><br>Centrality: %{customdata:.3f}<extra></extra>',
        customdata=[centrality_map.get(node, 0) for node in nodes],
        showlegend=False
    )
    
    fig = go.Figure(data=edge_traces + [node_trace])
    
    fig.update_layout(
        title=dict(
            text='<b>Portfolio Correlation Network</b><br><sub>Node size = centrality, Color = community, Bold lines = MST</sub>',
            font=dict(size=14)
        ),
        showlegend=False,
        hovermode='closest',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white',
        height=600,
        margin=dict(l=40, r=40, t=80, b=40)
    )
    
    return {
        'id': chart_id,
        'title': 'Portfolio Correlation Network',
        'plotly': fig.to_dict()
    }


def _build_risk_sunburst(
    communities: List[Dict[str, Any]],
    centrality: List[Dict[str, Any]],
    corr_matrix: pd.DataFrame,
    bridges: List[str],
    chart_id: str
) -> Optional[Dict[str, Any]]:
    """
    Build a Risk Contribution Sunburst showing portfolio structure and risk hierarchy.
    
    Visual structure:
    - Center: Portfolio total
    - Inner ring: Communities (sized by member count, colored by internal correlation)
    - Outer ring: Individual stocks (sized by centrality, colored by risk contribution)
    - Bridge nodes highlighted with distinct markers
    
    This creates a dramatic visual showing where risk concentrates in the portfolio.
    """
    import plotly.graph_objects as go
    
    if len(communities) < 1 or not centrality:
        return None
    
    # Build centrality lookup
    centrality_map = {c["ticker"]: c for c in centrality}
    bridge_set = set(bridges) if bridges else set()
    
    # Community color palette (vibrant)
    community_colors = [
        '#3B82F6',  # Blue
        '#10B981',  # Emerald
        '#F59E0B',  # Amber
        '#EF4444',  # Red
        '#8B5CF6',  # Violet
        '#EC4899',  # Pink
        '#06B6D4',  # Cyan
        '#84CC16',  # Lime
    ]
    
    # Prepare sunburst data
    ids = ["Portfolio"]
    labels = ["Portfolio"]
    parents = [""]
    values = []
    colors = ["#1F2937"]  # Dark center
    hover_texts = ["<b>Portfolio Risk Structure</b><br>Click to explore"]
    
    total_stocks = sum(comm["size"] for comm in communities)
    values.append(total_stocks)
    
    # Add communities (inner ring)
    for i, comm in enumerate(communities):
        comm_id = f"comm_{comm['id']}"
        comm_color = community_colors[i % len(community_colors)]
        internal_corr = comm.get("avg_internal_correlation", 0)
        
        ids.append(comm_id)
        labels.append(f"Cluster {comm['id']}")
        parents.append("Portfolio")
        values.append(comm["size"])
        
        # Darken color based on internal correlation (higher = more risk)
        # Mix with red for high correlation
        if internal_corr > 0.7:
            colors.append('#DC2626')  # Red for high correlation
        elif internal_corr > 0.5:
            colors.append('#F97316')  # Orange for moderate-high
        else:
            colors.append(comm_color)
        
        hover_texts.append(
            f"<b>Cluster {comm['id']}</b><br>"
            f"Stocks: {', '.join(comm['stocks'][:4])}{'...' if len(comm['stocks']) > 4 else ''}<br>"
            f"Internal Correlation: {internal_corr:.0%}<br>"
            f"Size: {comm['size']} positions"
        )
        
        # Add stocks (outer ring)
        for stock in comm["stocks"]:
            stock_id = f"stock_{stock}"
            cent_data = centrality_map.get(stock, {})
            eigen_cent = cent_data.get("eigenvector_centrality", 0.5)
            risk_contrib = cent_data.get("risk_contribution", 0.5)
            is_bridge = stock in bridge_set
            
            ids.append(stock_id)
            parents.append(comm_id)
            # Size by centrality (more central = bigger slice)
            values.append(max(0.5, eigen_cent * 2))
            
            # Color by risk contribution - gradient from green to red
            if is_bridge:
                colors.append('#7C3AED')  # Purple for bridges (stand out)
                label = f"🔗 {stock}"
            elif risk_contrib > 0.6:
                colors.append('#DC2626')  # Red - high risk
                label = stock
            elif risk_contrib > 0.4:
                colors.append('#F97316')  # Orange
                label = stock
            elif risk_contrib > 0.2:
                colors.append('#FBBF24')  # Yellow
                label = stock
            else:
                colors.append('#10B981')  # Green - low risk
                label = stock
            
            labels.append(label)
            
            bridge_label = "<br><b>⚠️ BRIDGE NODE</b>" if is_bridge else ""
            hover_texts.append(
                f"<b>{stock}</b>{bridge_label}<br>"
                f"Centrality: {eigen_cent:.2f}<br>"
                f"Risk Contribution: {risk_contrib:.2f}<br>"
                f"Community: Cluster {comm['id']}"
            )
    
    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(
            colors=colors,
            line=dict(color='white', width=2)
        ),
        hovertemplate='%{customdata}<extra></extra>',
        customdata=hover_texts,
        branchvalues='total',
        insidetextorientation='radial',
        textfont=dict(size=11, color='white'),
    ))
    
    fig.update_layout(
        title=dict(
            text='<b>Portfolio Risk Sunburst</b><br><sub>Inner = Communities | Outer = Stocks | Size = Centrality | 🔗 = Bridge Nodes</sub>',
            font=dict(size=14, color='#1F2937'),
            x=0.5
        ),
        height=600,
        margin=dict(l=20, r=20, t=80, b=20),
        paper_bgcolor='white',
        font=dict(family="Inter, system-ui, sans-serif")
    )
    
    # Add annotation explaining colors
    fig.add_annotation(
        text="<b>Risk Scale:</b> 🟢 Low → 🟡 Medium → 🟠 High → 🔴 Critical | 🟣 Bridge",
        xref="paper", yref="paper",
        x=0.5, y=-0.02,
        showarrow=False,
        font=dict(size=10, color='#6B7280'),
        align="center"
    )
    
    return {
        'id': chart_id,
        'title': 'Portfolio Risk Sunburst',
        'plotly': fig.to_dict()
    }


# =============================================================================
# IMPACT ANALYSIS HELPERS
# =============================================================================

def _calculate_cascade_impact(
    ticker: str,
    shock_pct: float,
    corr_matrix: pd.DataFrame,
    graph: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate the estimated cascade impact if a given ticker drops by shock_pct.
    
    Uses correlation-weighted propagation to estimate how a shock spreads through
    the portfolio network.
    
    Args:
        ticker: The stock experiencing the shock
        shock_pct: The percentage drop (e.g., -0.10 for -10%)
        corr_matrix: Correlation matrix
        graph: Portfolio graph structure
        weights: Optional ticker->weight mapping
    
    Returns:
        Impact analysis with direct and indirect effects
    """
    if ticker not in corr_matrix.columns:
        return {"error": f"Ticker {ticker} not in correlation matrix"}
    
    nodes = list(corr_matrix.columns)
    n = len(nodes)
    
    # Default equal weights if not provided
    if weights is None:
        weights = {t: 1.0 / n for t in nodes}
    
    # Direct impact on the shocked stock
    direct_impact = shock_pct * weights.get(ticker, 0)
    
    # Calculate propagated impacts to each connected stock
    # Impact propagation = shock * correlation * decay_factor
    propagated_impacts = {}
    total_propagated = 0.0
    
    for other in nodes:
        if other == ticker:
            continue
        
        corr = corr_matrix.loc[ticker, other]
        # Propagation: shock transfers proportionally to correlation
        # We use correlation^2 as the transfer coefficient (more conservative)
        propagation_factor = corr ** 2 if corr > 0 else 0
        
        other_weight = weights.get(other, 1.0 / n)
        propagated = shock_pct * propagation_factor * other_weight
        
        if abs(propagated) > 0.001:  # Only include meaningful impacts
            propagated_impacts[other] = {
                "correlation": round(corr, 3),
                "propagation_factor": round(propagation_factor, 3),
                "estimated_impact_pct": round(propagated * 100, 2)
            }
            total_propagated += propagated
    
    # Sort by impact magnitude
    sorted_impacts = dict(sorted(
        propagated_impacts.items(),
        key=lambda x: abs(x[1]["estimated_impact_pct"]),
        reverse=True
    ))
    
    total_portfolio_impact = direct_impact + total_propagated
    
    return {
        "shocked_ticker": ticker,
        "shock_magnitude": f"{shock_pct * 100:.0f}%",
        "direct_portfolio_impact": f"{direct_impact * 100:.2f}%",
        "propagated_impact": f"{total_propagated * 100:.2f}%",
        "total_portfolio_impact": f"{total_portfolio_impact * 100:.2f}%",
        "cascade_multiplier": round(total_portfolio_impact / direct_impact, 2) if direct_impact != 0 else 0,
        "affected_positions": sorted_impacts,
        "positions_impacted": len(propagated_impacts)
    }


def _estimate_hedge_effectiveness(
    ticker: str,
    hedge_ratio: float,
    corr_matrix: pd.DataFrame,
    returns_df: Optional[pd.DataFrame],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Estimate the effectiveness of hedging a given position.
    
    Calculates:
    - Portfolio volatility reduction
    - Risk contribution before/after hedge
    - Estimated hedge cost (rough approximation)
    """
    nodes = list(corr_matrix.columns)
    n = len(nodes)
    
    if weights is None:
        weights = {t: 1.0 / n for t in nodes}
    
    # Calculate stock's contribution to portfolio risk
    ticker_weight = weights.get(ticker, 1.0 / n)
    
    # Sum of correlation-weighted connections
    risk_contribution = 0.0
    for other in nodes:
        if other == ticker:
            continue
        corr = abs(corr_matrix.loc[ticker, other])
        other_weight = weights.get(other, 1.0 / n)
        risk_contribution += corr * ticker_weight * other_weight
    
    # Estimate portfolio volatility contribution
    if returns_df is not None and ticker in returns_df.columns:
        ticker_vol = returns_df[ticker].std() * np.sqrt(252)  # Annualized
    else:
        ticker_vol = 0.25  # Default assumption: 25% annualized vol
    
    vol_contribution = ticker_weight * ticker_vol
    
    # Hedge reduces position's effective weight
    hedged_weight = ticker_weight * (1 - hedge_ratio)
    hedged_risk_contribution = risk_contribution * (1 - hedge_ratio)
    hedged_vol_contribution = hedged_weight * ticker_vol
    
    # Risk reduction estimates
    risk_reduction_pct = (1 - (1 - hedge_ratio)) * 100
    
    # Rough hedge cost estimate (based on typical options pricing)
    # 3-month ATM put ≈ 5-8% of notional for avg volatility
    # Scales with vol and hedge ratio
    estimated_cost_pct = ticker_vol * hedge_ratio * 0.25  # ~25% of vol*hedge as cost
    
    return {
        "ticker": ticker,
        "current_weight": round(ticker_weight * 100, 1),
        "hedge_ratio": round(hedge_ratio * 100, 0),
        "effective_weight_after_hedge": round(hedged_weight * 100, 1),
        "volatility_contribution_before": f"{vol_contribution * 100:.1f}%",
        "volatility_contribution_after": f"{hedged_vol_contribution * 100:.1f}%",
        "risk_contribution_reduction": f"{risk_reduction_pct:.0f}%",
        "estimated_annual_hedge_cost": f"{estimated_cost_pct * 100:.1f}%",
        "cost_benefit_ratio": round(risk_reduction_pct / max(estimated_cost_pct * 100, 1), 1)
    }


# =============================================================================
# HEDGE OPTIMIZATION
# =============================================================================

def _generate_hedge_optimization(
    graph: Dict[str, Any],
    bridges: List[str],
    communities: List[Dict[str, Any]],
    centrality: List[Dict[str, Any]],
    corr_matrix: pd.DataFrame,
    risk_assessment: Dict[str, Any],
    weights: Optional[List[float]] = None,
    returns_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Generate actionable hedge and rebalancing recommendations based on network analysis.
    
    Strategy:
    1. Bridge stocks: Highest priority hedges (single points of failure)
    2. High centrality stocks: Secondary hedges (systemic connectors)
    3. Community imbalance: Rebalancing suggestions to improve structure
    4. Density reduction: Positions to reduce or uncorrelated assets to add
    
    Now includes:
    - Cascade impact analysis for high-priority hedges
    - Hedge effectiveness estimates (volatility reduction, cost-benefit)
    - Quantified portfolio impact metrics
    """
    nodes = graph["nodes"]
    n = len(nodes)
    
    if n < 2:
        return {"status": "insufficient_positions", "message": "Need 2+ positions for optimization"}
    
    # Convert weights list to dict - flexible handling
    weights_dict: Dict[str, float] = {}
    if weights and len(weights) > 0:
        # Handle partial or unnormalized weights
        provided_weights = weights[:n] if len(weights) >= n else weights
        total_provided = sum(provided_weights)
        
        # Assign provided weights (normalized if needed)
        for i, w in enumerate(provided_weights):
            if i < n:
                # Normalize if total > 1, otherwise use as-is
                weights_dict[nodes[i]] = w / total_provided if total_provided > 1 else w
        
        # Distribute remainder equally among unassigned positions
        assigned_weight = sum(weights_dict.values())
        unassigned = [t for t in nodes if t not in weights_dict]
        if unassigned and assigned_weight < 1.0:
            remainder_per_pos = (1.0 - assigned_weight) / len(unassigned)
            for t in unassigned:
                weights_dict[t] = remainder_per_pos
        
        # Final normalization to ensure sum = 1
        total = sum(weights_dict.values())
        if total > 0:
            weights_dict = {k: v / total for k, v in weights_dict.items()}
    else:
        # Default equal weights
        weights_dict = {t: 1.0 / n for t in nodes}
    
    hedge_priority = []
    rebalance_suggestions = []
    diversification_adds = []
    cascade_analyses = []
    
    # Get risk metrics
    composite_z = risk_assessment.get("composite_z_score", 0)
    z_scores = risk_assessment.get("z_scores", {})
    
    # -----------------------------
    # 1. BRIDGE STOCK HEDGES (Highest Priority)
    # -----------------------------
    if bridges:
        for bridge in bridges:
            # Find which communities this bridge connects
            connected_communities = []
            for comm in communities:
                if bridge in comm["stocks"]:
                    connected_communities.append(comm["id"])
            
            # Calculate hedge urgency based on centrality
            bridge_centrality = next(
                (c["eigenvector_centrality"] for c in centrality if c["ticker"] == bridge),
                0.5
            )
            
            hedge_ratio = min(1.0, 0.5 + bridge_centrality)
            
            # Calculate cascade impact (what happens if this bridge drops 10%)
            cascade = _calculate_cascade_impact(
                ticker=bridge,
                shock_pct=-0.10,
                corr_matrix=corr_matrix,
                graph=graph,
                weights=weights_dict
            )
            cascade_analyses.append(cascade)
            
            # Calculate hedge effectiveness
            effectiveness = _estimate_hedge_effectiveness(
                ticker=bridge,
                hedge_ratio=hedge_ratio,
                corr_matrix=corr_matrix,
                returns_df=returns_df,
                weights=weights_dict
            )
            
            hedge_priority.append({
                "ticker": bridge,
                "priority": "CRITICAL",
                "reason": "bridge_node",
                "action": "hedge",
                "hedge_ratio": round(hedge_ratio, 2),
                "rationale": f"Bridge connecting {len(connected_communities)} community clusters. A -10% shock cascades to {cascade['positions_impacted']} positions.",
                "cascade_impact": {
                    "if_drops_10pct": cascade["total_portfolio_impact"],
                    "cascade_multiplier": cascade["cascade_multiplier"],
                    "positions_affected": cascade["positions_impacted"]
                },
                "hedge_effectiveness": effectiveness,
                "suggested_instruments": [
                    f"3-month ATM put on {bridge} (estimated cost: {effectiveness['estimated_annual_hedge_cost']})",
                    f"Collar strategy on {bridge} (lower cost, capped upside)",
                    f"Reduce position by {int(hedge_ratio * 100)}% instead of hedging"
                ],
                "centrality_score": round(bridge_centrality, 3)
            })
    
    # -----------------------------
    # 2. HIGH CENTRALITY HEDGES (Secondary Priority)
    # -----------------------------
    # Top 3 by centrality that aren't already bridges
    bridge_set = set(bridges) if bridges else set()
    high_centrality = [c for c in centrality[:5] if c["ticker"] not in bridge_set]
    
    for c in high_centrality[:3]:
        if c["eigenvector_centrality"] > 0.3:  # Only if meaningfully central
            ticker = c["ticker"]
            hedge_ratio = min(0.7, c["eigenvector_centrality"])
            
            # Calculate cascade impact
            cascade = _calculate_cascade_impact(
                ticker=ticker,
                shock_pct=-0.10,
                corr_matrix=corr_matrix,
                graph=graph,
                weights=weights_dict
            )
            
            # Calculate hedge effectiveness
            effectiveness = _estimate_hedge_effectiveness(
                ticker=ticker,
                hedge_ratio=hedge_ratio,
                corr_matrix=corr_matrix,
                returns_df=returns_df,
                weights=weights_dict
            )
            
            hedge_priority.append({
                "ticker": ticker,
                "priority": "HIGH",
                "reason": "high_centrality",
                "action": "partial_hedge",
                "hedge_ratio": round(hedge_ratio, 2),
                "rationale": f"High systemic connectivity (centrality: {c['eigenvector_centrality']:.2f}). A -10% shock impacts {cascade['positions_impacted']} positions.",
                "cascade_impact": {
                    "if_drops_10pct": cascade["total_portfolio_impact"],
                    "cascade_multiplier": cascade["cascade_multiplier"],
                    "positions_affected": cascade["positions_impacted"]
                },
                "hedge_effectiveness": effectiveness,
                "suggested_instruments": [
                    f"OTM puts on {ticker} (15-20% OTM, lower cost)",
                    f"Collar on {ticker} (sell {int(10 + hedge_ratio * 10)}% OTM calls, buy {int(10 + hedge_ratio * 5)}% OTM puts)",
                    f"Reduce position by {int(hedge_ratio * 50)}% as alternative to hedge"
                ],
                "centrality_score": round(c["eigenvector_centrality"], 3)
            })
    
    # -----------------------------
    # 3. COMMUNITY REBALANCING
    # -----------------------------
    if len(communities) >= 2:
        # Check for community size imbalance
        sizes = [comm["size"] for comm in communities]
        max_size = max(sizes)
        total_size = sum(sizes)
        
        # If one community dominates (>60% of portfolio)
        dominant_comm = next((c for c in communities if c["size"] == max_size), None)
        if dominant_comm and (max_size / total_size) > 0.6:
            rebalance_suggestions.append({
                "type": "reduce_concentration",
                "community_id": dominant_comm["id"],
                "stocks": dominant_comm["stocks"],
                "current_weight": round(max_size / total_size, 2),
                "target_weight": 0.5,
                "action": f"Reduce exposure to {', '.join(dominant_comm['stocks'][:3])}{'...' if len(dominant_comm['stocks']) > 3 else ''}",
                "rationale": "Single community dominates portfolio - reduces diversification benefit"
            })
        
        # Communities with very high internal correlation (>0.8)
        for comm in communities:
            if comm.get("avg_internal_correlation", 0) > 0.8 and comm["size"] >= 3:
                rebalance_suggestions.append({
                    "type": "reduce_internal_correlation",
                    "community_id": comm["id"],
                    "stocks": comm["stocks"],
                    "internal_correlation": round(comm["avg_internal_correlation"], 2),
                    "action": f"Reduce redundancy - keep 1-2 of: {', '.join(comm['stocks'][:4])}",
                    "rationale": f"High internal correlation ({comm['avg_internal_correlation']:.0%}) means these move together"
                })
    
    # -----------------------------
    # 4. DIVERSIFICATION SUGGESTIONS
    # -----------------------------
    # Find positions with lowest average correlation to rest of portfolio
    if n >= 4:
        avg_corrs = {}
        for ticker in nodes:
            other_corrs = [
                abs(corr_matrix.loc[ticker, other])
                for other in nodes if other != ticker
            ]
            avg_corrs[ticker] = np.mean(other_corrs) if other_corrs else 0
        
        # Stocks with highest avg correlation are candidates to replace
        high_corr_stocks = sorted(avg_corrs.items(), key=lambda x: x[1], reverse=True)[:3]
        
        for ticker, avg_corr in high_corr_stocks:
            if avg_corr > 0.6:  # Only flag if meaningfully high
                diversification_adds.append({
                    "type": "replace_correlated",
                    "ticker": ticker,
                    "avg_correlation": round(avg_corr, 2),
                    "action": f"Consider replacing {ticker} with uncorrelated asset",
                    "suggested_replacements": [
                        "Bonds (TLT, AGG) for equity portfolio",
                        "Commodities (GLD, USO) for non-commodity portfolio",
                        "International (EFA, EEM) for US-focused portfolio",
                        "REITs (VNQ) for non-real estate portfolio"
                    ]
                })
    
    # If density is too high, suggest adding uncorrelated assets
    if z_scores.get("density", 0) > 1.5:
        diversification_adds.append({
            "type": "add_uncorrelated",
            "reason": "high_density",
            "density_z_score": round(z_scores.get("density", 0), 2),
            "action": "Add uncorrelated assets to reduce network density",
            "suggested_assets": [
                "Treasury bonds (TLT, IEF, SHY)",
                "Gold (GLD, IAU)",
                "Managed futures / trend-following (DBMF, KMLM)",
                "Volatility strategies (SVXY in low-vol, VXX in high-vol)"
            ]
        })
    
    # -----------------------------
    # 5. SUMMARY OPTIMIZATION SCORE & IMPACT ANALYSIS
    # -----------------------------
    # How much would following recommendations improve structure?
    estimated_improvement = 0
    total_hedge_cost = 0.0
    total_risk_reduction = 0.0
    
    if bridges:
        estimated_improvement += len(bridges) * 0.5  # Each bridge hedge reduces risk
    
    if high_centrality:
        estimated_improvement += len([c for c in high_centrality if c["eigenvector_centrality"] > 0.3]) * 0.3
    
    if rebalance_suggestions:
        estimated_improvement += len(rebalance_suggestions) * 0.2
    
    # Aggregate hedge costs and benefits
    for hedge in hedge_priority:
        eff = hedge.get("hedge_effectiveness", {})
        if isinstance(eff, dict):
            cost_str = eff.get("estimated_annual_hedge_cost", "0%")
            try:
                cost = float(cost_str.replace("%", "")) / 100
                total_hedge_cost += cost * weights_dict.get(hedge["ticker"], 0)
            except (ValueError, AttributeError):
                pass
            
            reduction_str = eff.get("risk_contribution_reduction", "0%")
            try:
                reduction = float(reduction_str.replace("%", "")) / 100
                total_risk_reduction += reduction * weights_dict.get(hedge["ticker"], 0)
            except (ValueError, AttributeError):
                pass
    
    estimated_new_z = max(0, composite_z - estimated_improvement)
    
    # Calculate worst-case scenario (all bridge stocks drop 10% simultaneously)
    worst_case_impact = 0.0
    for cascade in cascade_analyses:
        try:
            impact_str = cascade.get("total_portfolio_impact", "0%")
            impact = float(impact_str.replace("%", "")) / 100
            worst_case_impact += impact
        except (ValueError, AttributeError):
            pass
    
    return {
        "status": "success",
        "current_risk_z_score": round(composite_z, 2),
        "estimated_post_hedge_z_score": round(estimated_new_z, 2),
        "estimated_risk_reduction": f"{min(100, estimated_improvement / max(composite_z, 0.1) * 100):.0f}%",
        "impact_analysis": {
            "worst_case_scenario": {
                "description": "All bridge/high-centrality stocks drop 10% simultaneously",
                "estimated_portfolio_impact": f"{worst_case_impact * 100:.1f}%",
                "positions_at_risk": len(cascade_analyses)
            },
            "hedge_cost_benefit": {
                "total_estimated_annual_cost": f"{total_hedge_cost * 100:.2f}%",
                "total_risk_reduction": f"{total_risk_reduction * 100:.1f}%",
                "cost_per_unit_risk_reduction": round(
                    total_hedge_cost / max(total_risk_reduction, 0.01), 2
                ) if total_risk_reduction > 0 else "N/A"
            },
            "cascade_scenarios": cascade_analyses[:3]  # Top 3 most impactful
        },
        "hedge_priority": hedge_priority,
        "rebalance_suggestions": rebalance_suggestions,
        "diversification_opportunities": diversification_adds,
        "summary": {
            "critical_hedges": len([h for h in hedge_priority if h["priority"] == "CRITICAL"]),
            "high_priority_hedges": len([h for h in hedge_priority if h["priority"] == "HIGH"]),
            "rebalancing_actions": len(rebalance_suggestions),
            "diversification_adds": len(diversification_adds),
            "total_positions_to_hedge": len(hedge_priority),
            "estimated_total_hedge_cost": f"{total_hedge_cost * 100:.2f}% annually"
        },
        "execution_order": [
            "1. Hedge CRITICAL priority positions (bridge nodes) immediately - highest cascade risk",
            "2. Implement HIGH priority hedges on high-centrality stocks within 1 week",
            "3. Rebalance community concentrations over 2-4 weeks",
            "4. Add diversifying assets over 1-2 months to reduce network density",
            "5. Re-run analysis after changes to verify improvement"
        ]
    }


# =============================================================================
# INTERNAL IMPLEMENTATION (callable by other tools)
# =============================================================================

async def _analyze_graph_theory_risk_impl(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    lookback_days: int = 252,
    correlation_threshold: float = 0.3,
    correlation_method: str = "pearson",
    generate_chart: bool = True,
    optimize_hedges: bool = False
) -> dict:
    """
    Internal implementation of graph theory risk analysis.
    
    This function can be called directly by other tools (like systemic_risk_score_tool)
    without going through the @function_tool decorator.
    
    See analyze_graph_theory_risk() for full documentation.
    """
    try:
        # Input validation
        if not tickers or len(tickers) < 2:
            return jsonify_results({
                "error": "Need at least 2 tickers for network analysis",
                "provided": len(tickers) if tickers else 0
            })
        
        if correlation_method not in ['pearson', 'spearman', 'kendall']:
            return jsonify_results({
                "error": f"Invalid correlation method: {correlation_method}",
                "valid_methods": ['pearson', 'spearman', 'kendall']
            })
        
        if not 0 <= correlation_threshold <= 1:
            return jsonify_results({
                "error": f"correlation_threshold must be between 0 and 1: {correlation_threshold}"
            })
        
        # Connect to FMP server
        fmp_server = FMPMarketDataServer()
        
        try:
            await fmp_server.connect()
            
            logger.info(f"[CONTAGION] Analyzing {len(tickers)} tickers with {lookback_days} day lookback")
            
            # Fetch price data for all tickers (skip invalid ones)
            price_data = {}
            skipped_tickers = []
            
            for ticker in tickers:
                ticker = ticker.upper().strip()
                df = await _fetch_price_data(fmp_server, ticker, lookback_days)
                
                if df is not None:
                    price_data[ticker] = df
                else:
                    skipped_tickers.append(ticker)
                    logger.warning(f"[CONTAGION] Skipping {ticker} - no valid data")
            
            valid_tickers = list(price_data.keys())
            
            if len(valid_tickers) < 2:
                return jsonify_results({
                    "error": "Need at least 2 valid tickers after data fetch",
                    "valid_tickers": valid_tickers,
                    "skipped_tickers": skipped_tickers
                })
            
            # Calculate returns matrix
            returns_df = _calculate_returns_matrix(price_data)
            sample_size = len(returns_df)
            
            if sample_size < 20:
                return jsonify_results({
                    "error": f"Insufficient overlapping data: {sample_size} points",
                    "minimum_required": 20
                })
            
            # Calculate correlation matrix
            corr_matrix = returns_df.corr(method=correlation_method)
            
            # Build graph
            graph = _build_correlation_graph(corr_matrix, correlation_threshold)
            
            # Calculate all metrics
            graph_metrics = _calculate_graph_metrics(graph)
            mst_edges = _minimum_spanning_tree(graph, corr_matrix)
            bridges = _find_bridges(graph)
            communities = _detect_communities(graph, corr_matrix)
            centrality = _calculate_centrality(graph, corr_matrix)
            
            # Calculate average correlation for benchmarking
            upper_tri = corr_matrix.values[np.triu_indices(len(valid_tickers), k=1)]
            avg_correlation = float(np.mean(np.abs(upper_tri)))
            
            # Risk assessment with z-score benchmarking
            risk_assessment = _assess_contagion_risk(
                graph_metrics=graph_metrics,
                bridges=bridges,
                communities=communities,
                centrality=centrality,
                correlation_threshold=correlation_threshold,
                avg_correlation=avg_correlation
            )
            
            # Convert correlation matrix to dict
            corr_dict = {}
            for t1 in valid_tickers:
                corr_dict[t1] = {}
                for t2 in valid_tickers:
                    corr_dict[t1][t2] = round(float(corr_matrix.loc[t1, t2]), 4)
            
            # Build result
            result = {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "tickers_requested": len(tickers),
                    "tickers_analyzed": len(valid_tickers),
                    "lookback_days": lookback_days,
                    "sample_size": sample_size,
                    "correlation_threshold": correlation_threshold,
                    "correlation_method": correlation_method,
                    "avg_correlation": round(avg_correlation, 4)
                },
                "valid_tickers": valid_tickers,
                "skipped_tickers": skipped_tickers if skipped_tickers else None,
                "graph_metrics": graph_metrics,
                "minimum_spanning_tree": mst_edges,
                "bridge_stocks": bridges if bridges else None,
                "communities": communities,
                "centrality_ranking": centrality[:10],  # Top 10
                "risk_assessment": risk_assessment,
                "correlation_matrix": corr_dict
            }
            
            # Generate hedge optimization if requested
            if optimize_hedges:
                hedge_optimization = _generate_hedge_optimization(
                    graph=graph,
                    bridges=bridges,
                    communities=communities,
                    centrality=centrality,
                    corr_matrix=corr_matrix,
                    risk_assessment=risk_assessment,
                    weights=weights,
                    returns_df=returns_df
                )
                result["hedge_optimization"] = hedge_optimization
            
            # Generate visualizations
            if generate_chart and len(valid_tickers) >= 2:
                charts_list = []
                
                # 1. Network chart
                network_chart_id = f"contagion_network_{uuid.uuid4().hex[:8]}"
                network_chart = _build_network_chart(
                    graph, communities, centrality, mst_edges, network_chart_id
                )
                if network_chart:
                    charts_list.append(
                        register_chart_handle(
                            network_chart['plotly'],
                            chart_type="network",
                            title=network_chart['title'],
                            alt_text=f"Portfolio correlation network with {len(valid_tickers)} stocks",
                            metadata={"tickers": valid_tickers},
                            chart_id=network_chart_id
                        )
                    )
                
                # 2. Risk sunburst chart
                if len(communities) >= 1:
                    sunburst_chart_id = f"risk_sunburst_{uuid.uuid4().hex[:8]}"
                    sunburst_chart = _build_risk_sunburst(
                        communities=communities,
                        centrality=centrality,
                        corr_matrix=corr_matrix,
                        bridges=bridges,
                        chart_id=sunburst_chart_id
                    )
                    if sunburst_chart:
                        charts_list.append(
                            register_chart_handle(
                                sunburst_chart['plotly'],
                                chart_type="sunburst",
                                title=sunburst_chart['title'],
                                alt_text=f"Risk contribution sunburst showing {len(communities)} clusters and {len(valid_tickers)} stocks",
                                metadata={"n_communities": len(communities), "n_bridges": len(bridges) if bridges else 0},
                                chart_id=sunburst_chart_id
                            )
                        )
                
                if charts_list:
                    result["charts"] = charts_list
            
            return jsonify_results(result)
        
        except Exception as e:
            logger.error(f"Portfolio contagion analysis failed: {e}", exc_info=True)
            return jsonify_results({
                "error": "Analysis failed",
                "details": str(e)
            })
        finally:
            await fmp_server.cleanup()
    
    except Exception as e:
        logger.error(f"Portfolio contagion tool failed: {e}", exc_info=True)
        return jsonify_results({
            "error": "Tool initialization failed",
            "details": str(e)
        })


# =============================================================================
# MAIN TOOL (wrapper for agent framework)
# =============================================================================

@function_tool
async def analyze_graph_theory_risk(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    lookback_days: int = 252,
    correlation_threshold: float = 0.3,
    correlation_method: str = "pearson",
    generate_chart: bool = True,
    optimize_hedges: bool = False
) -> dict:
    """
    Analyze portfolio risk using graph theory to reveal hidden structural vulnerabilities.
    
    This tool models your portfolio as a correlation network and applies advanced graph
    algorithms to uncover risks that traditional correlation analysis misses - particularly
    "contagion risk" where a shock to one position cascades through the network.
    
    **When to Use This Tool:**
    - Assessing structural diversification quality (not just average correlation)
    - Identifying single points of failure (bridge stocks)
    - Finding which positions to hedge for maximum portfolio protection
    - Detecting false diversification (stocks that appear uncorrelated but cluster together)
    - Understanding how a shock to one stock would propagate through the portfolio
    
    **Key Concepts Explained:**
    
    1. **Bridge Stocks**: Positions whose failure would disconnect parts of your portfolio.
       If AAPL is a bridge connecting your tech cluster to your value cluster, an AAPL
       crash impacts BOTH clusters. These are your highest-priority hedge targets.
    
    2. **Communities/Clusters**: Groups of stocks that move together. A portfolio with
       5 "communities" of 2 stocks each is more diversified than one with 1 community
       of 10 stocks, even if average correlations are similar.
    
    3. **Centrality**: Measures how "systemically important" each stock is. High-centrality
       stocks are connected to many other highly-connected stocks - they're the network hubs.
    
    4. **Minimum Spanning Tree (MST)**: The "backbone" of your portfolio's correlation
       structure - the N-1 strongest links that connect all positions.
    
    5. **Z-Score Benchmarking**: Compares your portfolio's structure against random graph
       theory (Erdős–Rényi model) to identify statistically significant deviations.
    
    **Interpreting Key Outputs:**
    
    - `contagion_risk`: HIGH/MODERATE/LOW - overall structural risk level
    - `composite_z_score`: How many standard deviations above expected risk (>2.0 = significant)
    - `diversification_score`: 0-10 scale (10 = excellent structural diversification)
    - `bridge_stocks`: HEDGE THESE FIRST - they're single points of failure
    - `communities`: Each cluster moves together; check `avg_internal_correlation`
    - `centrality_ranking`: Top stocks are your systemic risk contributors
    
    **Visualizations:**
    
    1. **Network Chart**: Shows portfolio structure with node size = centrality,
       colors = community membership, bold lines = MST backbone
    
    2. **Risk Sunburst**: Radial hierarchy showing communities (inner ring) and
       individual stocks (outer ring). Size = centrality, color = risk level.
       Bridge nodes highlighted in purple. Interactive - click to drill down.
    
    Args:
        tickers: List of stock symbols (e.g., ["AAPL", "MSFT", "GOOGL", "JPM"])
        weights: Optional portfolio weights for hedge sizing. Can be:
            - Exact weights matching ticker order (e.g., [0.2, 0.3, 0.25, 0.25])
            - Approximate weights (will be normalized automatically)
            - Partial weights (missing positions get equal share of remainder)
            - None (defaults to equal-weight: 1/N per position)
            NOTE: If user provides rough estimates like "30% AAPL, 20% MSFT, rest split",
            approximate as [0.30, 0.20, 0.125, 0.125, ...] - precision isn't critical
            for network analysis, directional accuracy matters more.
        lookback_days: Historical window for correlation calculation (default: 252 = 1 year)
        correlation_threshold: Minimum |correlation| to create network edge (default: 0.3)
            - Lower (0.2): More edges, reveals weaker connections
            - Higher (0.5): Fewer edges, focuses on strong relationships
        correlation_method: 'pearson' (default), 'spearman' (rank-based), or 'kendall'
        generate_chart: Include network and risk sunburst visualizations (default: True)
        optimize_hedges: Generate detailed hedge recommendations with impact analysis (default: False)
    
    Returns:
        Comprehensive analysis including:
        - graph_metrics: Network density, clustering coefficient, node count
        - minimum_spanning_tree: Backbone correlation links
        - bridge_stocks: Critical connector nodes (HEDGE THESE)
        - communities: Stock clusters with internal correlation scores
        - centrality_ranking: Systemic importance scores per stock
        - risk_assessment: Contagion risk level, z-scores, recommendations
        - correlation_matrix: Full pairwise correlations
        - charts: Network visualization + Risk Sunburst (interactive radial hierarchy)
        - hedge_optimization: (if enabled) Prioritized hedges with cascade impact analysis
    
    Examples:
        # Basic analysis - find structural risks
        await analyze_graph_theory_risk(
            tickers=["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA"]
        )
        # Returns: communities, bridge stocks, centrality ranking, contagion risk
        
        # Full hedge optimization with impact analysis
        await analyze_graph_theory_risk(
            tickers=["AAPL", "MSFT", "GOOGL", "JPM", "GS", "TLT", "GLD"],
            weights=[0.2, 0.15, 0.15, 0.15, 0.1, 0.15, 0.1],
            optimize_hedges=True
        )
        # Returns: Prioritized hedges with estimated portfolio impact, cascade analysis
        
        # Sensitive analysis for detecting weaker relationships
        await analyze_graph_theory_risk(
            tickers=["SPY", "QQQ", "TLT", "GLD", "USO", "EFA"],
            correlation_threshold=0.2,
            lookback_days=504  # 2 years
        )
        
        # Stress-period correlations (shorter window captures recent regime)
        await analyze_graph_theory_risk(
            tickers=["AAPL", "MSFT", "XLF", "XLE", "TLT"],
            lookback_days=63  # 3 months
        )
    """
    # Delegate to internal implementation
    return await _analyze_graph_theory_risk_impl(
        tickers=tickers,
        weights=weights,
        lookback_days=lookback_days,
        correlation_threshold=correlation_threshold,
        correlation_method=correlation_method,
        generate_chart=generate_chart,
        optimize_hedges=optimize_hedges
    )

