"""
Portfolio Geodesic Distance - Information Geometry Tool

Measures the "true" statistical distance between portfolio return distributions
using the Fisher-Rao metric on the manifold of probability distributions.

Supports:
- Pairwise portfolio comparison
- Portfolio vs historical baseline (regime detection)
- Multi-portfolio clustering (distance matrix)
"""

from .tool import analyze_portfolio_geodesic_distance

__all__ = ["analyze_portfolio_geodesic_distance"]

