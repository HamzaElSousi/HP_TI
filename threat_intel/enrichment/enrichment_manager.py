"""
Enrichment manager for HP_TI.

Coordinates multiple enrichment sources and provides a unified interface
for enriching IP addresses with threat intelligence.
"""

import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

from threat_intel.enrichment.cache_manager import CacheManager
from threat_intel.enrichment.base_enricher import BaseEnricher, EnrichmentResult
from threat_intel.enrichment.geoip_enricher import GeoIPEnricher
from threat_intel.enrichment.abuseipdb_enricher import AbuseIPDBEnricher
from threat_intel.enrichment.whois_enricher import WHOISEnricher

logger = logging.getLogger(__name__)


class EnrichmentManager:
    """
    Manages multiple enrichment sources and coordinates enrichment operations.

    Provides both synchronous and asynchronous enrichment with configurable
    enrichers and parallel execution.
    """

    def __init__(
        self,
        cache_manager: CacheManager,
        geoip_db_path: Optional[str] = None,
        abuseipdb_api_key: Optional[str] = None,
        max_workers: int = 5,
    ):
        """
        Initialize enrichment manager.

        Args:
            cache_manager: Cache manager instance
            geoip_db_path: Path to MaxMind GeoLite2 database
            abuseipdb_api_key: AbuseIPDB API key
            max_workers: Maximum parallel workers for enrichment
        """
        self.cache_manager = cache_manager
        self.max_workers = max_workers
        self.enrichers: Dict[str, BaseEnricher] = {}
        self.logger = logging.getLogger(__name__)

        # Initialize enrichers
        self._init_enrichers(geoip_db_path, abuseipdb_api_key)

    def _init_enrichers(
        self, geoip_db_path: Optional[str], abuseipdb_api_key: Optional[str]
    ) -> None:
        """
        Initialize all enrichers.

        Args:
            geoip_db_path: Path to GeoIP database
            abuseipdb_api_key: AbuseIPDB API key
        """
        # GeoIP enricher
        self.enrichers["geoip"] = GeoIPEnricher(
            cache_manager=self.cache_manager,
            database_path=geoip_db_path,
            enabled=bool(geoip_db_path),
        )

        # AbuseIPDB enricher
        self.enrichers["abuseipdb"] = AbuseIPDBEnricher(
            cache_manager=self.cache_manager,
            api_key=abuseipdb_api_key,
            enabled=bool(abuseipdb_api_key),
        )

        # WHOIS enricher
        self.enrichers["whois"] = WHOISEnricher(
            cache_manager=self.cache_manager,
            enabled=True,
        )

        # Log enabled enrichers
        enabled = [name for name, e in self.enrichers.items() if e.enabled]
        self.logger.info(f"Enrichment manager initialized with: {', '.join(enabled)}")

    def enrich_ip(
        self,
        ip_address: str,
        sources: Optional[List[str]] = None,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        Enrich IP address with threat intelligence from multiple sources.

        Args:
            ip_address: IP address to enrich
            sources: Optional list of specific sources to use (default: all enabled)
            parallel: Whether to run enrichers in parallel

        Returns:
            Dictionary with enrichment results from all sources
        """
        # Determine which enrichers to use
        if sources:
            enrichers_to_use = {
                name: e for name, e in self.enrichers.items()
                if name in sources and e.enabled
            }
        else:
            enrichers_to_use = {
                name: e for name, e in self.enrichers.items() if e.enabled
            }

        if not enrichers_to_use:
            self.logger.warning("No enrichers available")
            return {}

        results = {}

        if parallel and len(enrichers_to_use) > 1:
            # Run enrichers in parallel
            results = self._enrich_parallel(ip_address, enrichers_to_use)
        else:
            # Run enrichers sequentially
            for name, enricher in enrichers_to_use.items():
                try:
                    result = enricher.enrich(ip_address)
                    results[name] = result.to_dict()
                except Exception as e:
                    self.logger.error(f"Enrichment error for {name}: {e}")
                    results[name] = {"error": str(e)}

        # Calculate overall confidence score
        confidence = self._calculate_confidence(results)

        return {
            "ip_address": ip_address,
            "enrichments": results,
            "confidence_score": confidence,
            "timestamp": self._get_timestamp(),
        }

    def _enrich_parallel(
        self, ip_address: str, enrichers: Dict[str, BaseEnricher]
    ) -> Dict[str, Any]:
        """
        Run enrichers in parallel using thread pool.

        Args:
            ip_address: IP address to enrich
            enrichers: Dictionary of enrichers to run

        Returns:
            Dictionary of results
        """
        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all enrichment tasks
            future_to_name = {
                executor.submit(enricher.enrich, ip_address): name
                for name, enricher in enrichers.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result(timeout=30)
                    results[name] = result.to_dict()
                except Exception as e:
                    self.logger.error(f"Parallel enrichment error for {name}: {e}")
                    results[name] = {"error": str(e)}

        return results

    async def enrich_ip_async(
        self, ip_address: str, sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously enrich IP address.

        Args:
            ip_address: IP address to enrich
            sources: Optional list of specific sources

        Returns:
            Dictionary with enrichment results
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.enrich_ip, ip_address, sources, True
        )

    def enrich_batch(
        self, ip_addresses: List[str], parallel: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Enrich multiple IP addresses.

        Args:
            ip_addresses: List of IP addresses to enrich
            parallel: Whether to process IPs in parallel

        Returns:
            Dictionary mapping IP to enrichment results
        """
        results = {}

        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_ip = {
                    executor.submit(self.enrich_ip, ip, None, True): ip
                    for ip in ip_addresses
                }

                for future in as_completed(future_to_ip):
                    ip = future_to_ip[future]
                    try:
                        results[ip] = future.result(timeout=60)
                    except Exception as e:
                        self.logger.error(f"Batch enrichment error for {ip}: {e}")
                        results[ip] = {"error": str(e)}
        else:
            for ip in ip_addresses:
                results[ip] = self.enrich_ip(ip, parallel=False)

        return results

    def _calculate_confidence(self, results: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score based on enrichment results.

        Args:
            results: Enrichment results dictionary

        Returns:
            Confidence score (0-100)
        """
        total_score = 0.0
        total_weight = 0.0

        # Weight factors for each source
        weights = {
            "geoip": 0.2,
            "whois": 0.3,
            "abuseipdb": 0.5,  # Highest weight for abuse data
        }

        for source, result in results.items():
            if "error" in result or not result.get("data"):
                continue

            weight = weights.get(source, 0.1)
            data = result.get("data", {})

            # Score based on available data
            score = 0.0

            if source == "abuseipdb":
                # Use abuse confidence score directly
                score = data.get("abuse_confidence_score", 0)
            elif source == "geoip":
                # Score based on data completeness
                if data.get("country_code"):
                    score += 50
                if data.get("city"):
                    score += 50
            elif source == "whois":
                # Score based on ASN availability
                if data.get("asn"):
                    score += 100

            total_score += score * weight
            total_weight += weight

        if total_weight > 0:
            return min(100.0, total_score / total_weight)
        return 0.0

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    def get_enricher_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all enrichers.

        Returns:
            Dictionary with enricher statistics
        """
        stats = {}

        for name, enricher in self.enrichers.items():
            stats[name] = enricher.get_cache_stats()

        # Add overall cache stats
        stats["overall_cache"] = self.cache_manager.get_stats()

        return stats

    def clear_all_caches(self) -> Dict[str, int]:
        """
        Clear caches for all enrichers.

        Returns:
            Dictionary with counts of cleared entries per enricher
        """
        results = {}

        for name, enricher in self.enrichers.items():
            try:
                count = enricher.clear_cache()
                results[name] = count
            except Exception as e:
                self.logger.error(f"Error clearing cache for {name}: {e}")
                results[name] = 0

        return results

    def add_enricher(self, name: str, enricher: BaseEnricher) -> None:
        """
        Add a custom enricher.

        Args:
            name: Enricher name
            enricher: Enricher instance
        """
        self.enrichers[name] = enricher
        self.logger.info(f"Added custom enricher: {name}")

    def remove_enricher(self, name: str) -> bool:
        """
        Remove an enricher.

        Args:
            name: Enricher name

        Returns:
            True if removed, False if not found
        """
        if name in self.enrichers:
            del self.enrichers[name]
            self.logger.info(f"Removed enricher: {name}")
            return True
        return False

    def close(self) -> None:
        """Close all enrichers and cache manager."""
        for name, enricher in self.enrichers.items():
            try:
                if hasattr(enricher, "close"):
                    enricher.close()
            except Exception as e:
                self.logger.error(f"Error closing enricher {name}: {e}")

        self.cache_manager.close()
        self.logger.info("Enrichment manager closed")
