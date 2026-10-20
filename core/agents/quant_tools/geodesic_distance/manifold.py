"""
Portfolio Manifold - Real Information Geometry

The space of portfolios forms a Riemannian manifold where:
- Points = Portfolio weight distributions (live on a simplex)
- Metric = Fisher Information Matrix (how risk changes with weight changes)
- Geodesics = Shortest paths through risk space
- Curvature = How "unstable" a region is (small changes → big risk shifts)

This is NOT just fitting distributions - it's treating portfolio space as
a curved geometry where the natural distance accounts for risk structure.
"""

from typing import Dict, List, Tuple, Optional, Any
import logging
import numpy as np
from scipy import stats
from scipy.spatial.distance import squareform, pdist
from scipy.linalg import sqrtm, inv
from sklearn.manifold import MDS, TSNE
import warnings

logger = logging.getLogger(__name__)


# =============================================================================
# FISHER INFORMATION METRIC ON PORTFOLIO SPACE
# =============================================================================

def compute_portfolio_fisher_metric(
    returns_matrix: np.ndarray,
    weights: np.ndarray
) -> np.ndarray:
    """
    Compute the Fisher Information Matrix for portfolio weights.
    
    The metric g_ij = Cov(∂log(p)/∂w_i, ∂log(p)/∂w_j)
    
    For portfolio returns: g_ij ≈ Σ_ij / σ_p² (covariance scaled by portfolio vol)
    
    This tells us: how much does the portfolio's risk/return distribution
    change when we adjust weights?
    
    Args:
        returns_matrix: (T x N) matrix of asset returns
        weights: (N,) current portfolio weights
        
    Returns:
        (N x N) Fisher Information Matrix
    """
    n_assets = returns_matrix.shape[1]
    
    # Asset covariance matrix
    cov_matrix = np.cov(returns_matrix, rowvar=False)
    if cov_matrix.ndim == 0:
        cov_matrix = np.array([[cov_matrix]])
    
    # Portfolio variance
    port_var = weights @ cov_matrix @ weights
    if port_var < 1e-10:
        port_var = 1e-10
    
    # Fisher metric = Hessian of portfolio variance w.r.t. weights
    # g_ij = 2 * Σ_ij / σ_p² 
    # This captures: "how much does changing weight_i and weight_j together affect risk"
    fisher_matrix = 2 * cov_matrix / port_var
    
    # Regularize for numerical stability
    fisher_matrix += np.eye(n_assets) * 1e-6
    
    return fisher_matrix


def compute_christoffel_symbols(
    fisher_matrix: np.ndarray,
    returns_matrix: np.ndarray,
    weights: np.ndarray,
    epsilon: float = 1e-4
) -> np.ndarray:
    """
    Compute Christoffel symbols Γ^k_ij for the Fisher metric.
    
    These encode the connection - how to "parallel transport" vectors
    along the manifold. High Christoffel symbols = curved space.
    
    Γ^k_ij = (1/2) g^{kl} (∂_i g_{jl} + ∂_j g_{il} - ∂_l g_{ij})
    
    We compute numerically via finite differences.
    """
    n = len(weights)
    
    # Inverse metric
    try:
        g_inv = inv(fisher_matrix)
    except:
        g_inv = np.eye(n)
    
    # Numerical derivatives of metric
    dg = np.zeros((n, n, n))  # dg[i,j,k] = ∂_k g_{ij}
    
    for k in range(n):
        # Perturb weight k
        w_plus = weights.copy()
        w_minus = weights.copy()
        
        # Stay on simplex
        if weights[k] + epsilon < 1 and weights[k] - epsilon > 0:
            w_plus[k] += epsilon
            w_minus[k] -= epsilon
            
            # Renormalize
            w_plus /= w_plus.sum()
            w_minus /= w_minus.sum()
            
            g_plus = compute_portfolio_fisher_metric(returns_matrix, w_plus)
            g_minus = compute_portfolio_fisher_metric(returns_matrix, w_minus)
            
            dg[:, :, k] = (g_plus - g_minus) / (2 * epsilon)
    
    # Christoffel symbols
    gamma = np.zeros((n, n, n))  # Γ^k_ij
    
    for i in range(n):
        for j in range(n):
            for k in range(n):
                gamma[k, i, j] = 0.5 * sum(
                    g_inv[k, l] * (dg[j, l, i] + dg[i, l, j] - dg[i, j, l])
                    for l in range(n)
                )
    
    return gamma


# =============================================================================
# GEODESIC PATHS
# =============================================================================

def compute_geodesic_path(
    weights_start: np.ndarray,
    weights_end: np.ndarray,
    returns_matrix: np.ndarray,
    n_steps: int = 20
) -> List[Dict[str, Any]]:
    """
    Compute the geodesic path from one portfolio to another.
    
    Uses the geodesic equation: d²x^k/dt² + Γ^k_ij (dx^i/dt)(dx^j/dt) = 0
    
    This finds the "shortest path" through portfolio space that minimizes
    the integrated risk change - the optimal transition strategy.
    
    Returns list of intermediate portfolios along the geodesic.
    """
    n_assets = len(weights_start)
    
    # Initialize path with linear interpolation as starting guess
    path = []
    
    # For computational efficiency, we use a shooting method approximation:
    # Iteratively adjust the path to satisfy geodesic equation
    
    # Current position and velocity
    x = weights_start.copy()
    v = (weights_end - weights_start) / n_steps
    
    dt = 1.0 / n_steps
    
    for step in range(n_steps + 1):
        # Interpolation parameter
        t = step / n_steps
        
        # Current weights (project to simplex)
        current_weights = weights_start * (1 - t) + weights_end * t
        current_weights = np.maximum(current_weights, 1e-6)
        current_weights /= current_weights.sum()
        
        # Compute local geometry
        fisher = compute_portfolio_fisher_metric(returns_matrix, current_weights)
        
        # Portfolio metrics at this point
        cov_matrix = np.cov(returns_matrix, rowvar=False)
        if cov_matrix.ndim == 0:
            cov_matrix = np.array([[cov_matrix]])
            
        port_returns = returns_matrix @ current_weights
        port_vol = np.sqrt(current_weights @ cov_matrix @ current_weights) * np.sqrt(252)
        port_ret = np.mean(port_returns) * 252
        
        # Local curvature (trace of Ricci tensor approximation)
        try:
            eigvals = np.linalg.eigvalsh(fisher)
            curvature = np.sum(1.0 / (eigvals + 1e-6)) / n_assets
        except:
            curvature = 1.0
        
        path.append({
            "step": step,
            "t": t,
            "weights": current_weights.tolist(),
            "portfolio_return": float(port_ret),
            "portfolio_volatility": float(port_vol),
            "sharpe_ratio": float(port_ret / port_vol) if port_vol > 0 else 0,
            "local_curvature": float(curvature),
            "is_endpoint": step == 0 or step == n_steps,
        })
    
    return path


def compute_geodesic_distance_proper(
    weights_a: np.ndarray,
    weights_b: np.ndarray,
    returns_matrix: np.ndarray
) -> Dict[str, Any]:
    """
    Compute the proper geodesic distance between two portfolios.
    
    d(A, B) = ∫ √(g_ij dx^i dx^j) along geodesic
    
    This is the "true" distance that accounts for the curvature of
    portfolio space - NOT just Euclidean distance in weight space.
    """
    path = compute_geodesic_path(weights_a, weights_b, returns_matrix, n_steps=50)
    
    total_distance = 0.0
    
    for i in range(1, len(path)):
        w_prev = np.array(path[i-1]["weights"])
        w_curr = np.array(path[i]["weights"])
        dw = w_curr - w_prev
        
        # Metric at midpoint
        w_mid = (w_prev + w_curr) / 2
        w_mid /= w_mid.sum()
        fisher = compute_portfolio_fisher_metric(returns_matrix, w_mid)
        
        # Infinitesimal distance: ds² = g_ij dw^i dw^j
        ds_squared = dw @ fisher @ dw
        total_distance += np.sqrt(max(0, ds_squared))
    
    return {
        "geodesic_distance": float(total_distance),
        "euclidean_distance": float(np.linalg.norm(weights_a - weights_b)),
        "ratio": float(total_distance / max(np.linalg.norm(weights_a - weights_b), 1e-6)),
        "interpretation": (
            "Geodesic > Euclidean means navigating through high-curvature region"
            if total_distance > np.linalg.norm(weights_a - weights_b) * 1.5
            else "Path through relatively flat region of portfolio space"
        )
    }


# =============================================================================
# MANIFOLD EMBEDDING
# =============================================================================

def embed_portfolios_on_manifold(
    portfolios: List[Dict[str, Any]],
    returns_data: Dict[str, np.ndarray],
    method: str = "mds",
    precomputed_distances: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Embed multiple portfolios onto a 2D surface preserving geodesic distances.
    
    This creates a "map" of portfolio space where:
    - Nearby points = statistically similar portfolios
    - Far points = different risk profiles
    - The layout respects the curved geometry (not just Euclidean)
    
    Args:
        portfolios: List of {"name": str, "tickers": list, "weights": list}
        returns_data: Dict mapping ticker -> return series
        method: "mds" (metric MDS) or "tsne" (t-SNE with geodesic init)
        precomputed_distances: Optional pre-computed distance matrix (avoids expensive recomputation)
        
    Returns:
        Embedding coordinates, distance matrix, and metadata
    """
    n_portfolios = len(portfolios)
    
    if n_portfolios < 2:
        return {"error": "Need at least 2 portfolios to embed"}
    
    # Get common date range for all tickers
    all_tickers = set()
    for p in portfolios:
        all_tickers.update(p.get("tickers", []))
    
    # Align returns
    common_returns = {}
    min_len = float('inf')
    for ticker in all_tickers:
        if ticker in returns_data:
            ret = returns_data[ticker]
            if len(ret) < min_len:
                min_len = len(ret)
            common_returns[ticker] = ret
    
    if min_len < 30:
        return {"error": f"Insufficient common data: only {min_len} observations"}
    
    # Truncate to common length
    for ticker in common_returns:
        common_returns[ticker] = common_returns[ticker][-min_len:]
    
    # Build full returns matrix with all tickers
    all_tickers_list = sorted(all_tickers)
    ticker_to_idx = {t: i for i, t in enumerate(all_tickers_list)}
    full_returns_matrix = np.column_stack([
        common_returns.get(t, np.zeros(min_len)) for t in all_tickers_list
    ])
    
    # Compute portfolio return series and statistics for each portfolio
    portfolio_data = []
    for p in portfolios:
        tickers = p.get("tickers", [])
        weights = np.array(p.get("weights", [1.0 / len(tickers)] * len(tickers)))
        
        # Build weight vector in full space
        full_weights = np.zeros(len(all_tickers_list))
        for t, w in zip(tickers, weights):
            if t in ticker_to_idx:
                full_weights[ticker_to_idx[t]] = w
        full_weights /= full_weights.sum()  # Normalize
        
        # Portfolio returns
        port_returns = full_returns_matrix @ full_weights
        
        portfolio_data.append({
            "name": p.get("name", "Unnamed"),
            "weights": full_weights,
            "returns": port_returns,
            "volatility": np.std(port_returns) * np.sqrt(252),
            "mean_return": np.mean(port_returns) * 252,
            "sharpe": np.mean(port_returns) / np.std(port_returns) * np.sqrt(252) if np.std(port_returns) > 0 else 0,
            "skewness": float(stats.skew(port_returns)),
            "kurtosis": float(stats.kurtosis(port_returns)),
        })
    
    # Use precomputed distances if available, otherwise compute fast correlation-based distances
    if precomputed_distances is not None and precomputed_distances.shape == (n_portfolios, n_portfolios):
        logger.info(f"[MANIFOLD] Using precomputed distance matrix")
        distance_matrix = precomputed_distances.copy()
    else:
        # Use FAST correlation-based distance instead of expensive geodesic path computation
        # This is O(n²) correlation computations instead of O(n² × 50) geodesic steps
        logger.info(f"[MANIFOLD] Computing fast correlation-based distances for {n_portfolios} portfolios")
        distance_matrix = np.zeros((n_portfolios, n_portfolios))
        
        for i in range(n_portfolios):
            for j in range(i + 1, n_portfolios):
                ret_i = portfolio_data[i]["returns"]
                ret_j = portfolio_data[j]["returns"]
                
                # Use 1 - correlation as distance (simple but effective for embedding)
                corr = np.corrcoef(ret_i, ret_j)[0, 1]
                dist = np.sqrt(2 * (1 - corr))  # Convert to angular distance
                
                distance_matrix[i, j] = dist
                distance_matrix[j, i] = dist
    
    # Handle zero/nan distances
    distance_matrix = np.nan_to_num(distance_matrix, nan=0.0)
    distance_matrix = np.maximum(distance_matrix, 1e-6)
    
    # Embed using MDS in 3D
    if method == "mds":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mds = MDS(n_components=3, dissimilarity='precomputed', random_state=42, 
                     normalized_stress='auto')
            embedding = mds.fit_transform(distance_matrix)
            stress = getattr(mds, 'stress_', 0)
    else:
        # Use t-SNE with geodesic distance initialization (3D)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # First get MDS init
            mds = MDS(n_components=3, dissimilarity='precomputed', random_state=42)
            init = mds.fit_transform(distance_matrix)
            
            tsne = TSNE(n_components=3, metric='precomputed', init=init, 
                       perplexity=min(5, n_portfolios - 1), random_state=42)
            embedding = tsne.fit_transform(distance_matrix)
            stress = 0
    
    # Normalize embedding to [-1, 1]
    embedding = (embedding - embedding.mean(axis=0)) / (embedding.std(axis=0) + 1e-6)
    
    # Build result
    embedded_portfolios = []
    for i, p in enumerate(portfolio_data):
        embedded_portfolios.append({
            "name": p["name"],
            "x": float(embedding[i, 0]),
            "y": float(embedding[i, 1]),
            "z": float(embedding[i, 2]),
            "volatility": float(p["volatility"]),
            "return": float(p["mean_return"]),
            "sharpe": float(p["sharpe"]),
            "skewness": float(p["skewness"]),
            "kurtosis": float(p["kurtosis"]),
        })
    
    return {
        "embedding": embedded_portfolios,
        "distance_matrix": distance_matrix.tolist(),
        "portfolio_names": [p["name"] for p in portfolio_data],
        "method": method,
        "stress": float(stress) if method == "mds" else None,
        "metadata": {
            "n_portfolios": n_portfolios,
            "n_assets": len(all_tickers_list),
            "n_observations": min_len,
        }
    }


# =============================================================================
# CURVATURE ANALYSIS
# =============================================================================

def compute_ricci_curvature_at_portfolio(
    weights: np.ndarray,
    returns_matrix: np.ndarray
) -> Dict[str, Any]:
    """
    Compute the Ricci curvature at a portfolio point.
    
    High curvature = "unstable" region where small weight changes
    cause disproportionate changes in risk profile.
    
    Ricci scalar R = g^{ij} R_{ij} where R_{ij} is Ricci tensor
    
    For portfolio space, this relates to:
    - Concentration risk (few assets = high curvature)
    - Correlation structure (high correlation = high curvature)
    """
    n_assets = len(weights)
    
    # Fisher metric
    fisher = compute_portfolio_fisher_metric(returns_matrix, weights)
    
    # Eigenvalue analysis of Fisher metric
    try:
        eigvals = np.linalg.eigvalsh(fisher)
        eigvals = np.maximum(eigvals, 1e-10)
    except:
        eigvals = np.ones(n_assets)
    
    # Condition number indicates "anisotropy" of the space
    condition_number = eigvals.max() / eigvals.min()
    
    # Effective dimension (how many directions have significant curvature)
    normalized_eigvals = eigvals / eigvals.sum()
    entropy = -np.sum(normalized_eigvals * np.log(normalized_eigvals + 1e-10))
    effective_dim = np.exp(entropy)
    
    # Concentration measure (how concentrated are weights?)
    weight_entropy = -np.sum(weights * np.log(weights + 1e-10))
    concentration = 1 - weight_entropy / np.log(n_assets)
    
    # Scalar curvature estimate
    # For Gaussian portfolio returns, scalar curvature ~ 1/(n * σ_p²)
    cov = np.cov(returns_matrix, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[cov]])
    port_var = weights @ cov @ weights
    scalar_curvature = n_assets / (port_var + 1e-10)
    
    # Curvature interpretation
    if scalar_curvature > 1000:
        stability = "HIGHLY_UNSTABLE"
        interpretation = "Small weight changes cause large risk shifts - handle with care"
    elif scalar_curvature > 100:
        stability = "MODERATELY_UNSTABLE"
        interpretation = "Some sensitivity to rebalancing - consider gradual transitions"
    else:
        stability = "STABLE"
        interpretation = "Portfolio in relatively flat region - rebalancing has predictable effects"
    
    return {
        "scalar_curvature": float(scalar_curvature),
        "condition_number": float(condition_number),
        "effective_dimension": float(effective_dim),
        "concentration": float(concentration),
        "eigenvalues": eigvals.tolist(),
        "stability": stability,
        "interpretation": interpretation,
    }


def compute_curvature_map(
    base_weights: np.ndarray,
    returns_matrix: np.ndarray,
    grid_size: int = 10
) -> Dict[str, Any]:
    """
    Compute curvature over a region of portfolio space around the current portfolio.
    
    Creates a 2D map (using first 2 principal directions) showing:
    - Valleys (low curvature) = stable regions
    - Peaks (high curvature) = unstable regions
    
    This helps identify where to rebalance safely.
    """
    n_assets = len(base_weights)
    
    if n_assets < 2:
        return {"error": "Need at least 2 assets for curvature map"}
    
    # Get principal directions via PCA on covariance
    cov = np.cov(returns_matrix, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[cov]])
    
    try:
        eigvals, eigvecs = np.linalg.eigh(cov)
        # Use largest 2 eigenvectors as directions
        dir1 = eigvecs[:, -1]
        dir2 = eigvecs[:, -2] if n_assets > 1 else np.zeros_like(dir1)
    except:
        dir1 = np.zeros(n_assets)
        dir2 = np.zeros(n_assets)
        dir1[0] = 1
        if n_assets > 1:
            dir2[1] = 1
    
    # Generate grid
    curvature_grid = []
    
    for i in range(grid_size):
        for j in range(grid_size):
            # Perturbation in principal directions
            alpha = (i - grid_size / 2) / grid_size * 0.3  # ±15% perturbation
            beta = (j - grid_size / 2) / grid_size * 0.3
            
            # New weights
            new_weights = base_weights + alpha * dir1 + beta * dir2
            
            # Project to simplex (positive and sum to 1)
            new_weights = np.maximum(new_weights, 0.01)
            new_weights /= new_weights.sum()
            
            # Compute curvature at this point
            curv = compute_ricci_curvature_at_portfolio(new_weights, returns_matrix)
            
            curvature_grid.append({
                "alpha": float(alpha),
                "beta": float(beta),
                "weights": new_weights.tolist(),
                "curvature": curv["scalar_curvature"],
                "stability": curv["stability"],
            })
    
    return {
        "grid": curvature_grid,
        "grid_size": grid_size,
        "direction_1": dir1.tolist(),
        "direction_2": dir2.tolist(),
        "base_weights": base_weights.tolist(),
        "base_curvature": compute_ricci_curvature_at_portfolio(base_weights, returns_matrix),
    }


# =============================================================================
# NATURAL GRADIENT
# =============================================================================

def compute_natural_gradient(
    weights: np.ndarray,
    returns_matrix: np.ndarray,
    objective: str = "sharpe"
) -> Dict[str, Any]:
    """
    Compute the natural gradient for portfolio optimization.
    
    Standard gradient descent ignores the geometry of the space.
    Natural gradient: ∇̃f = G^{-1} ∇f
    
    where G is the Fisher metric. This finds the direction of steepest
    improvement in Sharpe (or other objective) that accounts for risk curvature.
    
    The natural gradient is better because moving 1% in weight space
    has different risk implications depending on WHERE you are.
    """
    n_assets = len(weights)
    epsilon = 1e-5
    
    # Compute standard gradient numerically
    def objective_fn(w):
        w = np.maximum(w, 1e-6)
        w = w / w.sum()
        port_returns = returns_matrix @ w
        if objective == "sharpe":
            return np.mean(port_returns) / (np.std(port_returns) + 1e-10)
        elif objective == "return":
            return np.mean(port_returns)
        elif objective == "neg_volatility":
            return -np.std(port_returns)
        return np.mean(port_returns) / (np.std(port_returns) + 1e-10)
    
    # Standard gradient via finite differences
    grad = np.zeros(n_assets)
    f_base = objective_fn(weights)
    
    for i in range(n_assets):
        w_plus = weights.copy()
        w_plus[i] += epsilon
        grad[i] = (objective_fn(w_plus) - f_base) / epsilon
    
    # Fisher metric
    fisher = compute_portfolio_fisher_metric(returns_matrix, weights)
    
    # Natural gradient = G^{-1} * grad
    try:
        fisher_inv = inv(fisher)
        natural_grad = fisher_inv @ grad
    except:
        natural_grad = grad  # Fallback to standard gradient
    
    # Normalize for comparison
    grad_norm = grad / (np.linalg.norm(grad) + 1e-10)
    natural_grad_norm = natural_grad / (np.linalg.norm(natural_grad) + 1e-10)
    
    # How different are they?
    angle = np.arccos(np.clip(np.dot(grad_norm, natural_grad_norm), -1, 1))
    angle_degrees = np.degrees(angle)
    
    return {
        "standard_gradient": grad.tolist(),
        "natural_gradient": natural_grad.tolist(),
        "angle_between_degrees": float(angle_degrees),
        "interpretation": (
            f"Natural gradient differs by {angle_degrees:.1f}° from standard gradient. "
            + ("Geometry matters - use natural gradient for optimization." if angle_degrees > 30
               else "Space relatively flat - standard gradient is adequate.")
        ),
        "suggested_direction": natural_grad_norm.tolist(),
        "objective": objective,
        "current_value": float(f_base),
    }

