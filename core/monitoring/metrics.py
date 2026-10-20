"""
Monitoring metrics for SEC filing integration
Track embeddings, search, cache, and pool performance
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingMetrics:
    """Track embedding service performance"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_429s: int = 0
    server_errors_5xx: int = 0
    timeouts: int = 0
    total_latency_ms: float = 0
    max_latency_ms: float = 0
    min_latency_ms: float = float('inf')
    batch_sizes: list = field(default_factory=list)
    circuit_breaker_opens: int = 0
    circuit_breaker_closes: int = 0
    
    def record_request(self, success: bool, latency_ms: float, batch_size: int, 
                       error_type: Optional[str] = None):
        """Record a single embedding request"""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.batch_sizes.append(batch_size)
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error_type == '429':
                self.rate_limit_429s += 1
            elif error_type and error_type.startswith('5'):
                self.server_errors_5xx += 1
            elif error_type == 'timeout':
                self.timeouts += 1
    
    def get_p95_latency(self) -> float:
        """Calculate p95 latency"""
        if not self.batch_sizes:
            return 0
        # Simplified p95 calculation
        return self.max_latency_ms * 0.95
    
    def get_avg_latency(self) -> float:
        """Calculate average latency"""
        if self.total_requests == 0:
            return 0
        return self.total_latency_ms / self.total_requests


@dataclass
class SearchMetrics:
    """Track search performance"""
    pgvector_queries: int = 0
    pgvector_total_latency_ms: float = 0
    pgvector_max_latency_ms: float = 0
    pgvector_min_latency_ms: float = float('inf')
    pgvector_timeouts: int = 0
    rows_scanned: int = 0
    cache_searches: int = 0
    cache_search_latency_ms: float = 0
    
    def record_pgvector_query(self, latency_ms: float, rows: int, timeout: bool = False):
        """Record a pgvector query"""
        self.pgvector_queries += 1
        self.pgvector_total_latency_ms += latency_ms
        self.pgvector_max_latency_ms = max(self.pgvector_max_latency_ms, latency_ms)
        self.pgvector_min_latency_ms = min(self.pgvector_min_latency_ms, latency_ms)
        self.rows_scanned += rows
        if timeout:
            self.pgvector_timeouts += 1
    
    def record_cache_search(self, latency_ms: float):
        """Record a cache search"""
        self.cache_searches += 1
        self.cache_search_latency_ms += latency_ms
    
    def get_avg_pgvector_latency(self) -> float:
        """Calculate average pgvector latency"""
        if self.pgvector_queries == 0:
            return 0
        return self.pgvector_total_latency_ms / self.pgvector_queries


@dataclass
class PoolMetrics:
    """Track connection pool performance"""
    pool_size_current: int = 0
    pool_size_max: int = 0
    pool_acquisitions: int = 0
    pool_wait_time_ms: float = 0
    pool_saturation_events: int = 0
    
    def record_acquisition(self, wait_time_ms: float, pool_size: int, max_size: int):
        """Record a pool acquisition"""
        self.pool_acquisitions += 1
        self.pool_wait_time_ms += wait_time_ms
        self.pool_size_current = pool_size
        self.pool_size_max = max_size
        if pool_size >= max_size * 0.9:
            self.pool_saturation_events += 1


@dataclass 
class QualityMetrics:
    """Track search quality"""
    revenue_query_successes: int = 0
    revenue_query_failures: int = 0
    top3_preview_samples: list = field(default_factory=list)
    
    def record_revenue_query(self, success: bool, top3_previews: Optional[list] = None):
        """Record a revenue query result"""
        if success:
            self.revenue_query_successes += 1
        else:
            self.revenue_query_failures += 1
        
        if top3_previews:
            # Store truncated previews for audit
            truncated = [preview[:120] for preview in top3_previews[:3]]
            self.top3_preview_samples.append({
                'timestamp': datetime.now().isoformat(),
                'previews': truncated
            })
            # Keep only last 100 samples
            if len(self.top3_preview_samples) > 100:
                self.top3_preview_samples.pop(0)
    
    def get_revenue_success_rate(self) -> float:
        """Calculate revenue query success rate"""
        total = self.revenue_query_successes + self.revenue_query_failures
        if total == 0:
            return 0
        return (self.revenue_query_successes / total) * 100


class SECMetricsCollector:
    """Central metrics collector for SEC filing integration"""
    
    def __init__(self):
        self.embeddings = EmbeddingMetrics()
        self.search = SearchMetrics()
        self.pool = PoolMetrics()
        self.quality = QualityMetrics()
        self._start_time = time.time()
    
    def log_summary(self):
        """Log a summary of all metrics"""
        uptime_hours = (time.time() - self._start_time) / 3600
        
        logger.info("=== SEC Filing Integration Metrics ===")
        
        # Embeddings
        logger.info(f"Embeddings: QPS={self.embeddings.total_requests/uptime_hours/3600:.2f}, "
                   f"Success={self.embeddings.successful_requests}, "
                   f"429s={self.embeddings.rate_limit_429s}, "
                   f"5xx={self.embeddings.server_errors_5xx}, "
                   f"p95={self.embeddings.get_p95_latency():.0f}ms")
        
        # Search
        logger.info(f"Search: pgvector_p50={self.search.get_avg_pgvector_latency():.0f}ms, "
                   f"Queries={self.search.pgvector_queries}, "
                   f"Timeouts={self.search.pgvector_timeouts}, "
                   f"Rows/scan={self.search.rows_scanned/(self.search.pgvector_queries or 1):.0f}")
        
        # Pool
        logger.info(f"Pool: Size={self.pool.pool_size_current}/{self.pool.pool_size_max}, "
                   f"Saturations={self.pool.pool_saturation_events}, "
                   f"Avg_wait={self.pool.pool_wait_time_ms/(self.pool.pool_acquisitions or 1):.1f}ms")
        
        # Quality
        logger.info(f"Quality: Revenue_success={self.quality.get_revenue_success_rate():.1f}%, "
                   f"Samples={len(self.quality.top3_preview_samples)}")
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary"""
        return {
            'embeddings': {
                'qps': self.embeddings.total_requests / max((time.time() - self._start_time), 1),
                '429_count': self.embeddings.rate_limit_429s,
                '5xx_count': self.embeddings.server_errors_5xx,
                'p95_latency_ms': self.embeddings.get_p95_latency(),
                'avg_batch_size': sum(self.embeddings.batch_sizes) / max(len(self.embeddings.batch_sizes), 1) if self.embeddings.batch_sizes else 0
            },
            'search': {
                'pgvector_p50_ms': self.search.get_avg_pgvector_latency(),
                'pgvector_p95_ms': self.search.pgvector_max_latency_ms * 0.95,
                'timeout_count': self.search.pgvector_timeouts,
                'avg_rows_scanned': self.search.rows_scanned / max(self.search.pgvector_queries, 1)
            },
            'pool': {
                'current_size': self.pool.pool_size_current,
                'max_size': self.pool.pool_size_max,
                'saturation_events': self.pool.pool_saturation_events,
                'avg_wait_ms': self.pool.pool_wait_time_ms / max(self.pool.pool_acquisitions, 1)
            },
            'quality': {
                'revenue_success_rate': self.quality.get_revenue_success_rate(),
                'total_samples': len(self.quality.top3_preview_samples)
            }
        }


# Global metrics instance
metrics_collector = SECMetricsCollector()