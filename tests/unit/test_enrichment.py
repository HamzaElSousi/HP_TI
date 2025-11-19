"""
Unit tests for enrichment components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from threat_intel.enrichment.cache_manager import CacheManager
from threat_intel.enrichment.base_enricher import BaseEnricher, EnrichmentResult
from threat_intel.enrichment.enrichment_manager import EnrichmentManager


class TestCacheManager:
    """Tests for cache manager."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch("redis.from_url") as mock:
            redis_client = MagicMock()
            redis_client.ping.return_value = True
            redis_client.get.return_value = None
            redis_client.setex.return_value = True
            redis_client.exists.return_value = False
            redis_client.ttl.return_value = -2
            redis_client.dbsize.return_value = 0
            redis_client.info.return_value = {}
            redis_client.client_list.return_value = []
            mock.return_value = redis_client
            yield redis_client

    @pytest.fixture
    def cache_manager(self, mock_redis):
        """Create cache manager with mocked Redis."""
        return CacheManager(redis_url="redis://localhost:6379/0")

    def test_init(self, cache_manager):
        """Test cache manager initialization."""
        assert cache_manager is not None
        assert cache_manager.default_ttl == 86400

    def test_make_key(self, cache_manager):
        """Test cache key generation."""
        key = cache_manager._make_key("geoip", "192.168.1.1")
        assert key == "hp_ti:geoip:192.168.1.1"

    def test_get_miss(self, cache_manager):
        """Test cache miss."""
        result = cache_manager.get("geoip", "192.168.1.1")
        assert result is None

    def test_set_and_get(self, cache_manager, mock_redis):
        """Test setting and getting cache data."""
        import json

        # Mock get to return data after set
        test_data = {"country": "US", "city": "New York"}
        mock_redis.get.return_value = json.dumps(test_data)

        # Set data
        success = cache_manager.set("geoip", "192.168.1.1", test_data)
        assert success is True

        # Get data
        result = cache_manager.get("geoip", "192.168.1.1")
        assert result == test_data

    def test_ttl_config(self, cache_manager):
        """Test TTL configuration for different enrichment types."""
        assert cache_manager.ttl_config["geoip"] == 604800  # 7 days
        assert cache_manager.ttl_config["abuseipdb"] == 21600  # 6 hours
        assert cache_manager.ttl_config["whois"] == 604800  # 7 days


class MockEnricher(BaseEnricher):
    """Mock enricher for testing."""

    def _enrich_impl(self, identifier: str, **kwargs):
        """Mock implementation."""
        return {"data": f"enriched_{identifier}"}


class TestBaseEnricher:
    """Tests for base enricher."""

    @pytest.fixture
    def cache_manager(self):
        """Create mock cache manager."""
        mock = Mock(spec=CacheManager)
        mock.get.return_value = None
        mock.set.return_value = True
        return mock

    @pytest.fixture
    def enricher(self, cache_manager):
        """Create mock enricher."""
        return MockEnricher(
            name="test_enricher",
            cache_manager=cache_manager,
            rate_limit=10,
            enabled=True,
        )

    def test_enrich_no_cache(self, enricher):
        """Test enrichment without cache."""
        result = enricher.enrich("test_id")

        assert result.is_success()
        assert result.source == "test_enricher"
        assert result.data == {"data": "enriched_test_id"}
        assert result.cached is False

    def test_enrich_with_cache(self, enricher, cache_manager):
        """Test enrichment with cached data."""
        cached_data = {"data": "cached_value"}
        cache_manager.get.return_value = cached_data

        result = enricher.enrich("test_id")

        assert result.is_success()
        assert result.data == cached_data
        assert result.cached is True

    def test_enrich_disabled(self, cache_manager):
        """Test enrichment when disabled."""
        enricher = MockEnricher(
            name="test_enricher",
            cache_manager=cache_manager,
            enabled=False,
        )

        result = enricher.enrich("test_id")

        assert not result.is_success()
        assert result.error == "Enricher disabled"

    def test_rate_limiting(self, enricher):
        """Test rate limiting."""
        enricher.rate_limit = 2

        # First two requests should succeed
        result1 = enricher.enrich("id1")
        assert result1.is_success()

        result2 = enricher.enrich("id2")
        assert result2.is_success()

        # Third request should be rate limited
        result3 = enricher.enrich("id3")
        assert result3.error == "Rate limit exceeded"

    def test_enrichment_result(self):
        """Test enrichment result object."""
        result = EnrichmentResult(
            source="test",
            data={"key": "value"},
            cached=True,
        )

        assert result.is_success()
        assert result.source == "test"
        assert result.data == {"key": "value"}
        assert result.cached is True

        result_dict = result.to_dict()
        assert "timestamp" in result_dict
        assert result_dict["source"] == "test"


class TestEnrichmentManager:
    """Tests for enrichment manager."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager."""
        mock = Mock(spec=CacheManager)
        mock.get.return_value = None
        mock.set.return_value = True
        mock.get_stats.return_value = {}
        return mock

    @pytest.fixture
    def enrichment_manager(self, mock_cache_manager):
        """Create enrichment manager."""
        return EnrichmentManager(
            cache_manager=mock_cache_manager,
            geoip_db_path=None,  # Skip GeoIP for testing
            abuseipdb_api_key=None,  # Skip AbuseIPDB for testing
        )

    def test_init(self, enrichment_manager):
        """Test enrichment manager initialization."""
        assert enrichment_manager is not None
        assert "geoip" in enrichment_manager.enrichers
        assert "abuseipdb" in enrichment_manager.enrichers
        assert "whois" in enrichment_manager.enrichers

    def test_add_custom_enricher(self, enrichment_manager, mock_cache_manager):
        """Test adding a custom enricher."""
        custom_enricher = MockEnricher(
            name="custom",
            cache_manager=mock_cache_manager,
            enabled=True,
        )

        enrichment_manager.add_enricher("custom", custom_enricher)
        assert "custom" in enrichment_manager.enrichers

    def test_remove_enricher(self, enrichment_manager):
        """Test removing an enricher."""
        success = enrichment_manager.remove_enricher("whois")
        assert success is True
        assert "whois" not in enrichment_manager.enrichers

    def test_get_enricher_stats(self, enrichment_manager):
        """Test getting enricher statistics."""
        stats = enrichment_manager.get_enricher_stats()
        assert "overall_cache" in stats
