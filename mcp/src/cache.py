"""
Query Result Caching for Code Ingestion MCP Server

Simple in-memory cache to improve response times for repeated queries.
Caches semantic search results with automatic TTL expiration and size management.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class QueryCache:
    """
    In-memory cache for query results with TTL and automatic size management.
    
    Features:
    - Configurable TTL (default: 30 minutes)
    - MD5-based cache keys from query parameters
    - Automatic eviction of expired entries
    - Size-limited (max 1000 entries)
    - Cache hit/miss tracking for metrics
    """
    
    def __init__(self, ttl_minutes: int = 30, max_size: int = 1000):
        """
        Initialize the query cache.
        
        Args:
            ttl_minutes: Time-to-live for cached entries in minutes (default: 30)
            max_size: Maximum number of entries to keep in cache (default: 1000)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_size = max_size
        
        # Metrics
        self.hits = 0
        self.misses = 0
        
        logger.info(f"QueryCache initialized (TTL: {ttl_minutes}m, max_size: {max_size})")
    
    def get(self, query: str, collection: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available and not expired.
        
        Args:
            query: Search query string
            collection: Collection name
            params: Additional parameters (limit, threshold, etc.)
        
        Returns:
            Cached result dictionary or None if not found/expired
        """
        cache_key = self._generate_key(query, collection, params)
        
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            
            # Check if expired
            if datetime.now() - cached["timestamp"] < self.ttl:
                self.hits += 1
                logger.debug(f"Cache HIT for query: '{query[:50]}...' (key: {cache_key[:8]}...)")
                return cached["result"]
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
                logger.debug(f"Cache EXPIRED for query: '{query[:50]}...'")
        
        self.misses += 1
        logger.debug(f"Cache MISS for query: '{query[:50]}...'")
        return None
    
    def set(self, query: str, collection: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Cache a query result.
        
        Args:
            query: Search query string
            collection: Collection name
            params: Additional parameters
            result: Result dictionary to cache
        """
        cache_key = self._generate_key(query, collection, params)
        
        self.cache[cache_key] = {
            "result": result,
            "timestamp": datetime.now()
        }
        
        logger.debug(f"Cached result for query: '{query[:50]}...' (key: {cache_key[:8]}...)")
        
        # Size management - evict oldest entries if cache is too large
        if len(self.cache) > self.max_size:
            self._evict_oldest(num_to_evict=100)
    
    def _generate_key(self, query: str, collection: str, params: Dict[str, Any]) -> str:
        """
        Generate cache key from query parameters.
        
        Args:
            query: Search query
            collection: Collection name
            params: Additional parameters
        
        Returns:
            MD5 hash of the combined parameters
        """
        key_data = {
            "query": query.strip().lower(),  # Normalize query
            "collection": collection,
            "params": {k: v for k, v in sorted(params.items())}  # Sort for consistency
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _evict_oldest(self, num_to_evict: int = 100) -> None:
        """
        Evict oldest entries from cache.
        
        Args:
            num_to_evict: Number of entries to remove (default: 100)
        """
        if not self.cache:
            return
        
        # Sort by timestamp and remove oldest
        sorted_keys = sorted(
            self.cache.keys(),
            key=lambda k: self.cache[k]["timestamp"]
        )
        
        for key in sorted_keys[:num_to_evict]:
            del self.cache[key]
        
        logger.info(f"Evicted {num_to_evict} oldest cache entries (current size: {len(self.cache)})")
    
    def clear(self) -> None:
        """Clear entire cache."""
        cache_size = len(self.cache)
        self.cache = {}
        logger.info(f"Cache cleared ({cache_size} entries removed)")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "ttl_minutes": self.ttl.total_seconds() / 60
        }
    
    def remove_expired(self) -> int:
        """
        Manually remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        now = datetime.now()
        expired_keys = [
            key for key, value in self.cache.items()
            if now - value["timestamp"] >= self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)

