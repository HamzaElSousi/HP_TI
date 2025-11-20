"""
GeoIP enricher using MaxMind GeoLite2 database.

Provides geolocation data for IP addresses.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import ipaddress

try:
    import geoip2.database
    import geoip2.errors
    GEOIP2_AVAILABLE = True
except ImportError:
    GEOIP2_AVAILABLE = False

from threat_intel.enrichment.base_enricher import BaseEnricher
from threat_intel.enrichment.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class GeoIPEnricher(BaseEnricher):
    """
    GeoIP enricher using MaxMind GeoLite2 database.

    Provides country, city, and coordinate data for IP addresses.
    """

    def __init__(
        self,
        cache_manager: CacheManager,
        database_path: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialize GeoIP enricher.

        Args:
            cache_manager: Cache manager instance
            database_path: Path to GeoLite2-City.mmdb file
            enabled: Whether enricher is enabled
        """
        super().__init__(
            name="geoip",
            cache_manager=cache_manager,
            rate_limit=None,  # No rate limit for local database
            enabled=enabled and GEOIP2_AVAILABLE,
        )

        self.database_path = database_path
        self.reader: Optional[geoip2.database.Reader] = None

        if not GEOIP2_AVAILABLE:
            self.logger.error("geoip2 library not available. Install with: pip install geoip2")
            self.enabled = False
            return

        # Initialize database reader
        if self.enabled and database_path:
            self._init_database(database_path)

    def _init_database(self, database_path: str) -> None:
        """
        Initialize MaxMind database reader.

        Args:
            database_path: Path to database file
        """
        db_path = Path(database_path)

        if not db_path.exists():
            self.logger.error(f"GeoIP database not found: {database_path}")
            self.logger.info(
                "Download from: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data"
            )
            self.enabled = False
            return

        try:
            self.reader = geoip2.database.Reader(str(db_path))
            self.logger.info(f"GeoIP database loaded: {database_path}")
        except Exception as e:
            self.logger.error(f"Error loading GeoIP database: {e}")
            self.enabled = False

    def _enrich_impl(self, ip_address: str, **kwargs) -> Dict[str, Any]:
        """
        Enrich IP address with geolocation data.

        Args:
            ip_address: IP address to enrich
            **kwargs: Additional parameters (unused)

        Returns:
            Dictionary with geolocation data
        """
        if not self.reader:
            return {}

        # Validate IP address
        if not self._is_valid_ip(ip_address):
            self.logger.warning(f"Invalid IP address: {ip_address}")
            return {}

        try:
            response = self.reader.city(ip_address)

            data = {
                "country_code": response.country.iso_code,
                "country_name": response.country.name,
                "city": response.city.name,
                "postal_code": response.postal.code,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "timezone": response.location.time_zone,
                "accuracy_radius": response.location.accuracy_radius,
            }

            # Add subdivision (state/province) if available
            if response.subdivisions:
                data["subdivision"] = response.subdivisions.most_specific.name
                data["subdivision_code"] = response.subdivisions.most_specific.iso_code

            # Filter out None values
            return {k: v for k, v in data.items() if v is not None}

        except geoip2.errors.AddressNotFoundError:
            self.logger.debug(f"IP not found in GeoIP database: {ip_address}")
            return {"error": "IP not found in database"}
        except Exception as e:
            self.logger.error(f"GeoIP lookup error for {ip_address}: {e}")
            return {"error": str(e)}

    def _is_valid_ip(self, ip_address: str) -> bool:
        """
        Validate IP address format.

        Args:
            ip_address: IP address string

        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse IP address
            ip = ipaddress.ip_address(ip_address)

            # Skip private/loopback addresses
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                self.logger.debug(f"Skipping non-public IP: {ip_address}")
                return False

            return True
        except ValueError:
            return False

    def close(self) -> None:
        """Close database reader."""
        if self.reader:
            self.reader.close()
            self.logger.info("GeoIP database closed")
