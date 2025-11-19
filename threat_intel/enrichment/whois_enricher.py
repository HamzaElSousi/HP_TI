"""
WHOIS enricher for ASN and organization data.

Provides ASN, organization, and ISP information for IP addresses.
"""

import logging
from typing import Dict, Any, Optional
import socket
import re

try:
    import whois as python_whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

from threat_intel.enrichment.base_enricher import BaseEnricher
from threat_intel.enrichment.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class WHOISEnricher(BaseEnricher):
    """
    WHOIS enricher for ASN and organization data.

    Queries WHOIS servers for IP address ownership information.
    """

    # Team Cymru IP to ASN lookup service
    CYMRU_SERVER = "whois.cymru.com"
    CYMRU_PORT = 43

    def __init__(
        self,
        cache_manager: CacheManager,
        enabled: bool = True,
    ):
        """
        Initialize WHOIS enricher.

        Args:
            cache_manager: Cache manager instance
            enabled: Whether enricher is enabled
        """
        super().__init__(
            name="whois",
            cache_manager=cache_manager,
            rate_limit=30,  # 30 requests per minute to be respectful
            enabled=enabled,
        )

    def _enrich_impl(self, ip_address: str, **kwargs) -> Dict[str, Any]:
        """
        Enrich IP address with WHOIS data.

        Args:
            ip_address: IP address to query
            **kwargs: Additional parameters

        Returns:
            Dictionary with WHOIS data
        """
        # Get ASN data from Team Cymru
        asn_data = self._query_cymru_asn(ip_address)

        # Optionally get full WHOIS data (can be slow)
        include_full_whois = kwargs.get("include_full_whois", False)
        if include_full_whois and WHOIS_AVAILABLE:
            try:
                full_data = self._query_full_whois(ip_address)
                asn_data.update(full_data)
            except Exception as e:
                self.logger.debug(f"Full WHOIS query failed: {e}")

        return asn_data

    def _query_cymru_asn(self, ip_address: str) -> Dict[str, Any]:
        """
        Query Team Cymru for ASN data.

        Team Cymru provides a fast, reliable IP to ASN mapping service.

        Args:
            ip_address: IP address to query

        Returns:
            Dictionary with ASN data
        """
        try:
            # Connect to Cymru whois server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(10)
                sock.connect((self.CYMRU_SERVER, self.CYMRU_PORT))

                # Send query
                query = f" -v {ip_address}\r\n"
                sock.sendall(query.encode("ascii"))

                # Receive response
                response = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk

                response_text = response.decode("utf-8", errors="ignore")

                # Parse response
                return self._parse_cymru_response(response_text, ip_address)

        except socket.timeout:
            self.logger.warning(f"Cymru WHOIS timeout for {ip_address}")
            return {"error": "Query timeout"}
        except Exception as e:
            self.logger.error(f"Cymru WHOIS query failed: {e}")
            return {"error": str(e)}

    def _parse_cymru_response(
        self, response: str, ip_address: str
    ) -> Dict[str, Any]:
        """
        Parse Team Cymru WHOIS response.

        Response format:
        AS | IP | BGP Prefix | CC | Registry | Allocated | AS Name

        Args:
            response: Raw response text
            ip_address: Queried IP address

        Returns:
            Parsed data dictionary
        """
        lines = response.strip().split("\n")

        # Skip header and empty lines
        data_lines = [line for line in lines if line and not line.startswith("#")]

        if not data_lines:
            return {"error": "No data in response"}

        # Parse data line
        try:
            # Split on | character
            parts = [p.strip() for p in data_lines[0].split("|")]

            if len(parts) >= 7:
                return {
                    "asn": int(parts[0]) if parts[0].isdigit() else None,
                    "ip": parts[1],
                    "bgp_prefix": parts[2],
                    "country_code": parts[3] if parts[3] else None,
                    "registry": parts[4],
                    "allocated": parts[5],
                    "asn_name": parts[6],
                }
            else:
                self.logger.warning(f"Unexpected Cymru response format: {parts}")
                return {"error": "Unexpected response format"}

        except Exception as e:
            self.logger.error(f"Error parsing Cymru response: {e}")
            return {"error": f"Parse error: {str(e)}"}

    def _query_full_whois(self, ip_address: str) -> Dict[str, Any]:
        """
        Query full WHOIS data (optional, can be slow).

        Args:
            ip_address: IP address to query

        Returns:
            Dictionary with additional WHOIS data
        """
        if not WHOIS_AVAILABLE:
            return {}

        try:
            # Query WHOIS
            w = python_whois.whois(ip_address)

            data = {}

            # Extract relevant fields if available
            if hasattr(w, "org") and w.org:
                data["organization"] = w.org

            if hasattr(w, "registrar") and w.registrar:
                data["registrar"] = w.registrar

            if hasattr(w, "creation_date") and w.creation_date:
                data["creation_date"] = str(w.creation_date)

            # Some WHOIS responses include netname
            if hasattr(w, "text"):
                # Try to extract NetName from raw text
                netname_match = re.search(r"NetName:\s+(.+)", w.text)
                if netname_match:
                    data["netname"] = netname_match.group(1).strip()

                # Try to extract OrgName
                orgname_match = re.search(r"OrgName:\s+(.+)", w.text)
                if orgname_match:
                    data["org_name"] = orgname_match.group(1).strip()

            return data

        except Exception as e:
            self.logger.debug(f"Full WHOIS query error: {e}")
            return {}

    def validate_identifier(self, identifier: str) -> bool:
        """
        Validate IP address format.

        Args:
            identifier: IP address string

        Returns:
            True if valid IP, False otherwise
        """
        try:
            import ipaddress
            ipaddress.ip_address(identifier)
            return True
        except ValueError:
            return False
