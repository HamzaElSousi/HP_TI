"""
Base enricher class for HP_TI threat intelligence.

Provides common functionality for all enrichment sources.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from threat_intel.enrichment.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class EnrichmentResult:
    """
    Container for enrichment results with metadata.
    """

    def __init__(
        self,
        source: str,
        data: Dict[str, Any],
        cached: bool = False,
        error: Optional[str] = None,
    ):
        """
        Initialize enrichment result.

        Args:
            source: Enrichment source name
            data: Enriched data dictionary
            cached: Whether result came from cache
            error: Error message if enrichment failed
        """
        self.source = source
        self.data = data
        self.cached = cached
        self.error = error
        self.timestamp = datetime.utcnow()

    def is_success(self) -> bool:
        """Check if enrichment was successful."""
        return self.error is None and bool(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "data": self.data,
            "cached": self.cached,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseEnricher(ABC):
    """
    Abstract base class for all enrichers.

    Provides caching, rate limiting, and error handling.
    """

    def __init__(
        self,
        name: str,
        cache_manager: CacheManager,
        rate_limit: Optional[int] = None,
        enabled: bool = True,
    ):
        """
        Initialize base enricher.

        Args:
            name: Enricher name (used for caching prefix)
            cache_manager: Cache manager instance
            rate_limit: Optional rate limit (requests per minute)
            enabled: Whether enricher is enabled
        """
        self.name = name
        self.cache_manager = cache_manager
        self.rate_limit = rate_limit
        self.enabled = enabled
        self.logger = logging.getLogger(f"{__name__}.{name}")

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0
        self._window_start = time.time()

    def enrich(self, identifier: str, **kwargs) -> EnrichmentResult:
        """
        Enrich identifier with threat intelligence.

        Args:
            identifier: Identifier to enrich (e.g., IP address)
            **kwargs: Additional parameters for enrichment

        Returns:
            EnrichmentResult object
        """
        if not self.enabled:
            return EnrichmentResult(
                source=self.name, data={}, error="Enricher disabled"
            )

        # Check cache first
        cached_data = self.cache_manager.get(self.name, identifier)
        if cached_data:
            self.logger.debug(f"Cache hit for {identifier}")
            return EnrichmentResult(source=self.name, data=cached_data, cached=True)

        # Apply rate limiting
        if not self._check_rate_limit():
            self.logger.warning(f"Rate limit exceeded for {self.name}")
            return EnrichmentResult(
                source=self.name, data={}, error="Rate limit exceeded"
            )

        # Perform enrichment
        try:
            self.logger.debug(f"Enriching {identifier}")
            data = self._enrich_impl(identifier, **kwargs)

            # Cache result
            if data:
                self.cache_manager.set(self.name, identifier, data)

            return EnrichmentResult(source=self.name, data=data, cached=False)

        except Exception as e:
            self.logger.error(f"Enrichment failed for {identifier}: {e}")
            return EnrichmentResult(source=self.name, data={}, error=str(e))

    @abstractmethod
    def _enrich_impl(self, identifier: str, **kwargs) -> Dict[str, Any]:
        """
        Implementation of enrichment logic.

        Must be implemented by subclasses.

        Args:
            identifier: Identifier to enrich
            **kwargs: Additional parameters

        Returns:
            Dictionary with enrichment data
        """
        pass

    def _check_rate_limit(self) -> bool:
        """
        Check if request is within rate limit.

        Returns:
            True if request allowed, False otherwise
        """
        if self.rate_limit is None:
            return True

        current_time = time.time()

        # Reset counter every minute
        if current_time - self._window_start >= 60:
            self._request_count = 0
            self._window_start = current_time

        # Check if we're within limit
        if self._request_count >= self.rate_limit:
            # Calculate wait time until next window
            wait_time = 60 - (current_time - self._window_start)
            self.logger.debug(f"Rate limit reached, wait {wait_time:.1f}s")
            return False

        # Increment counter and allow request
        self._request_count += 1
        self._last_request_time = current_time
        return True

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for this enricher.

        Returns:
            Dictionary with cache stats
        """
        # Count keys with this enricher's prefix
        pattern = f"hp_ti:{self.name}:*"
        try:
            keys = self.cache_manager.client.keys(pattern)
            return {
                "enricher": self.name,
                "cached_entries": len(keys),
                "enabled": self.enabled,
                "rate_limit": self.rate_limit,
            }
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {}

    def clear_cache(self) -> int:
        """
        Clear all cached entries for this enricher.

        Returns:
            Number of entries cleared
        """
        count = self.cache_manager.flush_prefix(self.name)
        self.logger.info(f"Cleared {count} cached entries for {self.name}")
        return count

    def validate_identifier(self, identifier: str) -> bool:
        """
        Validate identifier format.

        Can be overridden by subclasses for specific validation.

        Args:
            identifier: Identifier to validate

        Returns:
            True if valid, False otherwise
        """
        return bool(identifier and isinstance(identifier, str))
