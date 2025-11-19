"""
Cache manager for HP_TI threat intelligence enrichment.

Manages Redis-based caching to reduce API calls and improve performance.
"""

import json
import logging
from typing import Optional, Any, Dict
from datetime import timedelta
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis-based cache manager for threat intelligence data.

    Provides TTL-based caching with configurable expiration times
    per enrichment source.
    """

    def __init__(
        self,
        redis_url: str,
        default_ttl: int = 86400,  # 24 hours
        max_connections: int = 50,
    ):
        """
        Initialize cache manager.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            max_connections: Maximum Redis connections
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl

        # Initialize Redis connection pool
        try:
            self.client = redis.from_url(
                redis_url,
                max_connections=max_connections,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            self.client.ping()
            logger.info(f"Cache manager initialized (Redis: {redis_url})")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

        # TTL configurations for different enrichment types
        self.ttl_config = {
            "geoip": 604800,  # 7 days (rarely changes)
            "whois": 604800,  # 7 days
            "abuseipdb": 21600,  # 6 hours (changes frequently)
            "virustotal": 86400,  # 24 hours
            "vpn_detection": 86400,  # 24 hours
            "default": default_ttl,
        }

    def _make_key(self, prefix: str, identifier: str) -> str:
        """
        Create cache key.

        Args:
            prefix: Key prefix (enrichment type)
            identifier: Unique identifier (e.g., IP address)

        Returns:
            Cache key string
        """
        return f"hp_ti:{prefix}:{identifier}"

    def get(self, prefix: str, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data.

        Args:
            prefix: Key prefix (enrichment type)
            identifier: Unique identifier

        Returns:
            Cached data or None if not found/expired
        """
        key = self._make_key(prefix, identifier)

        try:
            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit: {key}")
                return json.loads(data)
            else:
                logger.debug(f"Cache miss: {key}")
                return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Error getting cache key {key}: {e}")
            return None

    def set(
        self,
        prefix: str,
        identifier: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set cached data with TTL.

        Args:
            prefix: Key prefix (enrichment type)
            identifier: Unique identifier
            data: Data to cache
            ttl: Optional TTL override in seconds

        Returns:
            True if successful, False otherwise
        """
        key = self._make_key(prefix, identifier)

        # Determine TTL
        if ttl is None:
            ttl = self.ttl_config.get(prefix, self.default_ttl)

        try:
            json_data = json.dumps(data)
            self.client.setex(key, ttl, json_data)
            logger.debug(f"Cached: {key} (TTL: {ttl}s)")
            return True
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    def delete(self, prefix: str, identifier: str) -> bool:
        """
        Delete cached data.

        Args:
            prefix: Key prefix
            identifier: Unique identifier

        Returns:
            True if deleted, False otherwise
        """
        key = self._make_key(prefix, identifier)

        try:
            result = self.client.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return result > 0
        except RedisError as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    def exists(self, prefix: str, identifier: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            prefix: Key prefix
            identifier: Unique identifier

        Returns:
            True if exists, False otherwise
        """
        key = self._make_key(prefix, identifier)

        try:
            return bool(self.client.exists(key))
        except RedisError as e:
            logger.warning(f"Error checking cache key {key}: {e}")
            return False

    def get_ttl(self, prefix: str, identifier: str) -> int:
        """
        Get remaining TTL for cached data.

        Args:
            prefix: Key prefix
            identifier: Unique identifier

        Returns:
            Remaining TTL in seconds, -1 if no TTL, -2 if not exists
        """
        key = self._make_key(prefix, identifier)

        try:
            return self.client.ttl(key)
        except RedisError as e:
            logger.warning(f"Error getting TTL for {key}: {e}")
            return -2

    def flush_prefix(self, prefix: str) -> int:
        """
        Delete all keys with given prefix.

        Args:
            prefix: Key prefix to flush

        Returns:
            Number of keys deleted
        """
        pattern = f"hp_ti:{prefix}:*"

        try:
            keys = self.client.keys(pattern)
            if keys:
                deleted = self.client.delete(*keys)
                logger.info(f"Flushed {deleted} keys with prefix {prefix}")
                return deleted
            return 0
        except RedisError as e:
            logger.error(f"Error flushing prefix {prefix}: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        try:
            info = self.client.info("stats")
            memory = self.client.info("memory")

            return {
                "total_keys": self.client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0), info.get("keyspace_misses", 0)
                ),
                "memory_used_mb": memory.get("used_memory", 0) / 1024 / 1024,
                "connected_clients": self.client.client_list().__len__(),
            }
        except RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """
        Calculate cache hit rate.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses

        Returns:
            Hit rate as percentage
        """
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100

    def warm_cache(self, prefix: str, data_dict: Dict[str, Dict[str, Any]]) -> int:
        """
        Warm cache with multiple entries.

        Args:
            prefix: Key prefix
            data_dict: Dictionary of {identifier: data}

        Returns:
            Number of entries cached
        """
        count = 0
        for identifier, data in data_dict.items():
            if self.set(prefix, identifier, data):
                count += 1

        logger.info(f"Warmed cache with {count} entries for prefix {prefix}")
        return count

    def close(self) -> None:
        """Close Redis connection."""
        try:
            self.client.close()
            logger.info("Cache manager closed")
        except RedisError as e:
            logger.error(f"Error closing cache manager: {e}")
