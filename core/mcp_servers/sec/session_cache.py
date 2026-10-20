"""
Session-scoped LRU cache with TTL for SEC filing embeddings
Fast follow-up queries within a session without database bloat
"""

import time
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from collections import OrderedDict
from dataclasses import dataclass
import sys

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached filing with chunks and embeddings"""
    chunks: List[Dict[str, Any]]
    embeddings: List[List[float]]
    timestamp: float
    size_bytes: int
    
    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if entry has expired"""
        return time.time() - self.timestamp > ttl_seconds


class SessionCache:
    """
    LRU cache with TTL for session-scoped SEC filing embeddings.
    
    Features:
    - Per-session isolation: Each session has its own cache space
    - TTL expiration: Entries expire after configured time
    - LRU eviction: Least recently used entries removed when full
    - Size limits: Max entries and max memory usage
    """
    
    def __init__(self, ttl_minutes: int = 30, max_entries: int = 100, max_mb: int = 500):
        """
        Initialize session cache.
        
        Args:
            ttl_minutes: Time-to-live in minutes for cache entries
            max_entries: Maximum number of entries across all sessions
            max_mb: Maximum memory usage in megabytes
        """
        self._cache: Dict[str, Dict[str, CacheEntry]] = {}  # {session_id: {accession: CacheEntry}}
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._lru: OrderedDict[Tuple[str, str], float] = OrderedDict()  # (session_id, accession) -> timestamp
        self._ttl_seconds = ttl_minutes * 60
        self._max_entries = max_entries
        self._max_bytes = max_mb * 1024 * 1024
        self._current_bytes = 0
        
        # Add async locks for concurrent access protection
        self._locks: Dict[Tuple[str, str, str], asyncio.Lock] = {}  # (user_id, session_id, accession) -> Lock
        self._persist_semaphore = asyncio.Semaphore(5)  # Limit concurrent persist operations to 5
        
        logger.info(f"SessionCache initialized: TTL={ttl_minutes}min, max_entries={max_entries}, max_mb={max_mb}")
    
    def get(self, session_id: str, accession_number: str) -> Optional[Tuple[List[Dict], List[List[float]]]]:
        """
        Get cached chunks and embeddings if not expired.
        
        Args:
            session_id: Session identifier
            accession_number: SEC filing accession number
            
        Returns:
            Tuple of (chunks, embeddings) if found and not expired, None otherwise
        """
        # Clean up expired entries periodically
        if len(self._lru) > 0 and len(self._lru) % 10 == 0:
            self._cleanup_expired()
        
        # Check if session exists
        if session_id not in self._cache:
            self._miss_count += 1
            return None
        
        # Check if filing exists in session
        if accession_number not in self._cache[session_id]:
            self._miss_count += 1
            return None
        
        entry = self._cache[session_id][accession_number]
        
        # Check expiration
        if entry.is_expired(self._ttl_seconds):
            self._remove_entry(session_id, accession_number)
            self._miss_count += 1
            return None
        
        # Update LRU order
        key = (session_id, accession_number)
        self._lru.move_to_end(key)
        
        self._hit_count += 1
        logger.debug(f"Cache HIT: session={session_id[:8]}..., accession={accession_number}")
        return (entry.chunks, entry.embeddings)
    
    def put(self, session_id: str, accession_number: str, 
            chunks: List[Dict], embeddings: List[List[float]]) -> bool:
        """
        Store chunks and embeddings with TTL.
        
        Args:
            session_id: Session identifier
            accession_number: SEC filing accession number
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors
            
        Returns:
            True if stored successfully, False if too large
        """
        # Calculate size (rough estimate)
        size_bytes = self._estimate_size(chunks, embeddings)
        
        # Check if single entry is too large
        if size_bytes > self._max_bytes:
            logger.warning(f"Entry too large ({size_bytes / 1024 / 1024:.1f}MB), skipping cache")
            return False
        
        # Evict entries if needed to make space
        while self._current_bytes + size_bytes > self._max_bytes or len(self._lru) >= self._max_entries:
            if not self._evict_lru():
                break  # Nothing left to evict
        
        # Create entry
        entry = CacheEntry(
            chunks=chunks,
            embeddings=embeddings,
            timestamp=time.time(),
            size_bytes=size_bytes
        )
        
        # Store in cache - ensure session dict exists
        if session_id not in self._cache:
            self._cache[session_id] = {}
        
        # Remove old entry if exists (this might remove the session dict)
        if accession_number in self._cache.get(session_id, {}):
            self._remove_entry(session_id, accession_number)
        
        # Re-ensure session dict exists after removal (it may have been deleted)
        if session_id not in self._cache:
            self._cache[session_id] = {}
            
        self._cache[session_id][accession_number] = entry
        self._lru[(session_id, accession_number)] = time.time()
        self._current_bytes += size_bytes
        
        logger.debug(f"Cache PUT: session={session_id[:8]}..., accession={accession_number}, "
                    f"size={size_bytes / 1024:.1f}KB, total={self._current_bytes / 1024 / 1024:.1f}MB")
        return True
    
    def clear_session(self, session_id: str) -> int:
        """
        Clear all entries for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of entries removed
        """
        if session_id not in self._cache:
            return 0
        
        count = 0
        accessions = list(self._cache[session_id].keys())
        for accession in accessions:
            self._remove_entry(session_id, accession)
            count += 1
        
        logger.info(f"Cleared {count} entries for session {session_id[:8]}...")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = sum(len(filings) for filings in self._cache.values())
        return {
            'sessions': len(self._cache),
            'total_entries': total_entries,
            'memory_mb': self._current_bytes / 1024 / 1024,
            'max_entries': self._max_entries,
            'max_mb': self._max_bytes / 1024 / 1024,
            'ttl_minutes': self._ttl_seconds / 60,
            'active_locks': len(self._locks),
            'persist_queue': 5 - self._persist_semaphore._value if hasattr(self._persist_semaphore, '_value') else 0
        }
    
    async def get_lock(self, user_id: str, session_id: str, accession_number: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific cache key.
        
        Args:
            user_id: User identifier  
            session_id: Session identifier
            accession_number: SEC filing accession number
            
        Returns:
            Async lock for the cache key
        """
        key = (user_id or 'system', session_id, accession_number)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    async def acquire_persist_slot(self):
        """
        Acquire a slot for persist operation (max 5 concurrent).
        
        Returns:
            Context manager for the persist semaphore
        """
        return self._persist_semaphore
    
    def _estimate_size(self, chunks: List[Dict], embeddings: List[List[float]]) -> int:
        """Estimate memory size of entry"""
        # Rough estimation:
        # - Each chunk dict: ~500 bytes for text + metadata
        # - Each embedding: 4 bytes per float * dimension
        chunk_size = sum(len(str(chunk)) for chunk in chunks)
        embedding_size = sum(len(emb) * 4 for emb in embeddings)
        overhead = sys.getsizeof({}) * 2  # Dict overhead
        
        return chunk_size + embedding_size + overhead
    
    def _remove_entry(self, session_id: str, accession_number: str):
        """Remove a single entry from cache"""
        if session_id in self._cache and accession_number in self._cache[session_id]:
            entry = self._cache[session_id][accession_number]
            self._current_bytes -= entry.size_bytes
            del self._cache[session_id][accession_number]
            
            # Clean up empty session
            if not self._cache[session_id]:
                del self._cache[session_id]
        
        key = (session_id, accession_number)
        if key in self._lru:
            del self._lru[key]
    
    def _evict_lru(self) -> bool:
        """Evict least recently used entry"""
        if not self._lru:
            return False
        
        # Get oldest entry
        (session_id, accession_number), _ = self._lru.popitem(last=False)
        self._remove_entry(session_id, accession_number)
        self._eviction_count += 1
        
        logger.debug(f"Evicted LRU: session={session_id[:8]}..., accession={accession_number}")
        return True
    
    def _cleanup_expired(self):
        """Remove all expired entries"""
        current_time = time.time()
        expired = []
        
        for (session_id, accession_number), timestamp in self._lru.items():
            if session_id in self._cache and accession_number in self._cache[session_id]:
                entry = self._cache[session_id][accession_number]
                if entry.is_expired(self._ttl_seconds):
                    expired.append((session_id, accession_number))
        
        for session_id, accession_number in expired:
            self._remove_entry(session_id, accession_number)
        
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        total_entries = sum(len(session) for session in self._cache.values())
        hit_rate = self._hit_count / max(self._hit_count + self._miss_count, 1) if (self._hit_count + self._miss_count) > 0 else 0
        
        stats = {
            'hit_count': self._hit_count,
            'miss_count': self._miss_count,
            'hit_rate': round(hit_rate * 100, 2),
            'eviction_count': self._eviction_count,
            'total_entries': total_entries,
            'total_sessions': len(self._cache),
            'current_size_mb': round(self._current_bytes / 1024 / 1024, 2),
            'max_size_mb': round(self._max_bytes / 1024 / 1024, 2),
            'ttl_seconds': self._ttl_seconds,
            'max_entries': self._max_entries
        }
        
        return stats
    
    def log_stats(self):
        """Log cache statistics"""
        stats = self.get_stats()
        logger.info(f"SEC Cache Stats: Hit rate={stats['hit_rate']}%, "
                   f"Entries={stats['total_entries']}/{stats['max_entries']}, "
                   f"Size={stats['current_size_mb']}/{stats['max_size_mb']}MB, "
                   f"Hits={stats['hit_count']}, Misses={stats['miss_count']}, "
                   f"Evictions={stats['eviction_count']}")