"""
AbuseIPDB enricher for IP reputation data.

Provides abuse confidence scores and report data from AbuseIPDB.
"""

import logging
from typing import Dict, Any, Optional
import requests
from requests.exceptions import RequestException

from threat_intel.enrichment.base_enricher import BaseEnricher
from threat_intel.enrichment.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class AbuseIPDBEnricher(BaseEnricher):
    """
    AbuseIPDB enricher for IP reputation.

    Queries AbuseIPDB API for abuse confidence scores and report history.
    Free tier: 1000 requests/day, max 4 requests/minute
    """

    API_URL = "https://api.abuseipdb.com/api/v2/check"

    def __init__(
        self,
        cache_manager: CacheManager,
        api_key: Optional[str] = None,
        rate_limit: int = 1000,  # requests per day
        enabled: bool = True,
    ):
        """
        Initialize AbuseIPDB enricher.

        Args:
            cache_manager: Cache manager instance
            api_key: AbuseIPDB API key
            rate_limit: Rate limit (requests per day)
            enabled: Whether enricher is enabled
        """
        # Convert daily limit to per-minute for rate limiter
        # 1000 per day = ~0.7 per minute, use 1 per minute to be safe
        super().__init__(
            name="abuseipdb",
            cache_manager=cache_manager,
            rate_limit=4,  # 4 requests per minute (free tier limit)
            enabled=enabled and bool(api_key),
        )

        self.api_key = api_key
        self.daily_limit = rate_limit

        if not api_key and enabled:
            self.logger.warning("AbuseIPDB API key not provided, enricher disabled")
            self.enabled = False

    def _enrich_impl(self, ip_address: str, **kwargs) -> Dict[str, Any]:
        """
        Enrich IP address with AbuseIPDB data.

        Args:
            ip_address: IP address to check
            **kwargs: Additional parameters
                - max_age_days: Maximum age of reports (default: 90)

        Returns:
            Dictionary with abuse data
        """
        max_age_days = kwargs.get("max_age_days", 90)

        headers = {
            "Key": self.api_key,
            "Accept": "application/json",
        }

        params = {
            "ipAddress": ip_address,
            "maxAgeInDays": max_age_days,
            "verbose": True,  # Include report details
        }

        try:
            response = requests.get(
                self.API_URL,
                headers=headers,
                params=params,
                timeout=10,
            )

            # Check for rate limiting
            if response.status_code == 429:
                self.logger.warning("AbuseIPDB rate limit exceeded")
                return {"error": "Rate limit exceeded"}

            response.raise_for_status()
            result = response.json()

            if "data" not in result:
                self.logger.warning(f"Unexpected AbuseIPDB response format")
                return {"error": "Invalid response format"}

            data = result["data"]

            # Extract relevant fields
            enriched_data = {
                "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                "country_code": data.get("countryCode"),
                "usage_type": data.get("usageType"),
                "isp": data.get("isp"),
                "domain": data.get("domain"),
                "hostnames": data.get("hostnames", []),
                "is_public": data.get("isPublic", True),
                "is_whitelisted": data.get("isWhitelisted", False),
                "total_reports": data.get("totalReports", 0),
                "num_distinct_users": data.get("numDistinctUsers", 0),
                "last_reported_at": data.get("lastReportedAt"),
            }

            # Add threat level based on confidence score
            score = enriched_data["abuse_confidence_score"]
            if score >= 75:
                enriched_data["threat_level"] = "critical"
            elif score >= 50:
                enriched_data["threat_level"] = "high"
            elif score >= 25:
                enriched_data["threat_level"] = "medium"
            else:
                enriched_data["threat_level"] = "low"

            # Include reports if available
            if "reports" in data and data["reports"]:
                enriched_data["recent_reports"] = [
                    {
                        "reported_at": report.get("reportedAt"),
                        "comment": report.get("comment", "")[:200],  # Truncate
                        "categories": report.get("categories", []),
                    }
                    for report in data["reports"][:5]  # Keep only 5 most recent
                ]

            return enriched_data

        except RequestException as e:
            self.logger.error(f"AbuseIPDB API request failed: {e}")
            return {"error": f"API request failed: {str(e)}"}
        except Exception as e:
            self.logger.error(f"AbuseIPDB enrichment error: {e}")
            return {"error": str(e)}

    def report_ip(
        self, ip_address: str, categories: list, comment: str
    ) -> Dict[str, Any]:
        """
        Report an IP address to AbuseIPDB.

        Args:
            ip_address: IP address to report
            categories: List of category IDs
            comment: Report comment

        Returns:
            API response data

        Note:
            Category IDs: https://www.abuseipdb.com/categories
            Common: 18 (Brute Force), 22 (SSH), 15 (Hacking)
        """
        if not self.enabled:
            return {"error": "Enricher not enabled"}

        headers = {
            "Key": self.api_key,
            "Accept": "application/json",
        }

        data = {
            "ip": ip_address,
            "categories": ",".join(map(str, categories)),
            "comment": comment[:1024],  # Max 1024 chars
        }

        try:
            response = requests.post(
                "https://api.abuseipdb.com/api/v2/report",
                headers=headers,
                data=data,
                timeout=10,
            )

            response.raise_for_status()
            result = response.json()

            self.logger.info(f"Reported IP {ip_address} to AbuseIPDB")
            return result

        except RequestException as e:
            self.logger.error(f"Failed to report IP to AbuseIPDB: {e}")
            return {"error": str(e)}
