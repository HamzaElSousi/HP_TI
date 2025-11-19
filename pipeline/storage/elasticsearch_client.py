"""
Elasticsearch client for HP_TI.

Manages connections to Elasticsearch and provides methods for
indexing and searching honeypot logs.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ElasticsearchException

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """
    Elasticsearch client for log storage and full-text search.

    Handles document indexing, searching, and index management.
    """

    def __init__(
        self,
        url: str,
        index_prefix: str = "hp_ti",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize Elasticsearch client.

        Args:
            url: Elasticsearch URL
            index_prefix: Prefix for index names
            username: Optional username for authentication
            password: Optional password for authentication
        """
        self.url = url
        self.index_prefix = index_prefix

        # Initialize Elasticsearch client
        if username and password:
            self.client = Elasticsearch(
                [url], basic_auth=(username, password), verify_certs=False
            )
        else:
            self.client = Elasticsearch([url], verify_certs=False)

        # Test connection
        if not self.client.ping():
            raise ConnectionError(f"Could not connect to Elasticsearch at {url}")

        logger.info(f"Elasticsearch client initialized (URL: {url})")

    def create_index_templates(self) -> None:
        """
        Create index templates for honeypot logs.

        Templates define mappings and settings for time-series indices.
        """
        # Honeypot logs template
        honeypot_logs_template = {
            "index_patterns": [f"{self.index_prefix}-logs-*"],
            "template": {
                "settings": {
                    "number_of_shards": 3,
                    "number_of_replicas": 1,
                    "index.lifecycle.name": "hp_ti_lifecycle",
                },
                "mappings": {
                    "properties": {
                        "timestamp": {"type": "date"},
                        "level": {"type": "keyword"},
                        "logger": {"type": "keyword"},
                        "component": {"type": "keyword"},
                        "event_type": {"type": "keyword"},
                        "message": {"type": "text"},
                        "session_id": {"type": "keyword"},
                        "source_ip": {"type": "ip"},
                        "source_port": {"type": "integer"},
                        "username": {"type": "keyword"},
                        "password": {"type": "keyword"},
                        "command": {"type": "text"},
                        "auth_method": {"type": "keyword"},
                        "success": {"type": "boolean"},
                        "honeypot_service": {"type": "keyword"},
                    }
                },
            },
        }

        # Threat events template
        threat_events_template = {
            "index_patterns": [f"{self.index_prefix}-events-*"],
            "template": {
                "settings": {
                    "number_of_shards": 3,
                    "number_of_replicas": 1,
                },
                "mappings": {
                    "properties": {
                        "timestamp": {"type": "date"},
                        "event_type": {"type": "keyword"},
                        "severity": {"type": "keyword"},
                        "source_ip": {"type": "ip"},
                        "destination_ip": {"type": "ip"},
                        "session_id": {"type": "keyword"},
                        "service": {"type": "keyword"},
                        "description": {"type": "text"},
                        "indicators": {"type": "object"},
                        "enrichment": {
                            "properties": {
                                "country": {"type": "keyword"},
                                "city": {"type": "keyword"},
                                "asn": {"type": "integer"},
                                "abuse_score": {"type": "integer"},
                                "is_vpn": {"type": "boolean"},
                                "is_tor": {"type": "boolean"},
                            }
                        },
                    }
                },
            },
        }

        try:
            # Create templates (ES 8.x uses _index_template API)
            self.client.indices.put_index_template(
                name=f"{self.index_prefix}_logs_template",
                body=honeypot_logs_template,
            )

            self.client.indices.put_index_template(
                name=f"{self.index_prefix}_events_template",
                body=threat_events_template,
            )

            logger.info("Created Elasticsearch index templates")
        except ElasticsearchException as e:
            logger.error(f"Error creating index templates: {e}")
            raise

    def get_index_name(self, index_type: str = "logs") -> str:
        """
        Get index name with date suffix for time-series data.

        Args:
            index_type: Type of index ('logs' or 'events')

        Returns:
            Index name with date suffix (e.g., 'hp_ti-logs-2025-11-19')
        """
        date_suffix = datetime.utcnow().strftime("%Y-%m-%d")
        return f"{self.index_prefix}-{index_type}-{date_suffix}"

    def index_document(
        self, document: Dict[str, Any], index_type: str = "logs", doc_id: Optional[str] = None
    ) -> str:
        """
        Index a single document.

        Args:
            document: Document to index
            index_type: Type of index ('logs' or 'events')
            doc_id: Optional document ID

        Returns:
            Document ID
        """
        index_name = self.get_index_name(index_type)

        try:
            # Ensure timestamp is present
            if "timestamp" not in document:
                document["timestamp"] = datetime.utcnow().isoformat()

            result = self.client.index(
                index=index_name, id=doc_id, document=document
            )
            logger.debug(f"Indexed document {result['_id']} to {index_name}")
            return result["_id"]
        except ElasticsearchException as e:
            logger.error(f"Error indexing document: {e}")
            raise

    def bulk_index(
        self, documents: List[Dict[str, Any]], index_type: str = "logs"
    ) -> Dict[str, int]:
        """
        Bulk index multiple documents for better performance.

        Args:
            documents: List of documents to index
            index_type: Type of index ('logs' or 'events')

        Returns:
            Dictionary with success and error counts
        """
        index_name = self.get_index_name(index_type)

        # Prepare bulk actions
        actions = []
        for doc in documents:
            if "timestamp" not in doc:
                doc["timestamp"] = datetime.utcnow().isoformat()

            actions.append(
                {
                    "_index": index_name,
                    "_source": doc,
                }
            )

        try:
            success, errors = helpers.bulk(
                self.client, actions, stats_only=True, raise_on_error=False
            )

            logger.info(
                f"Bulk indexed {success} documents to {index_name}, {len(errors)} errors"
            )
            return {"success": success, "errors": len(errors) if errors else 0}
        except ElasticsearchException as e:
            logger.error(f"Error in bulk indexing: {e}")
            raise

    def search(
        self,
        query: Dict[str, Any],
        index_type: str = "logs",
        size: int = 100,
        from_: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search documents.

        Args:
            query: Elasticsearch query DSL
            index_type: Type of index to search
            size: Number of results to return
            from_: Offset for pagination

        Returns:
            List of matching documents
        """
        index_pattern = f"{self.index_prefix}-{index_type}-*"

        try:
            result = self.client.search(
                index=index_pattern, body={"query": query, "size": size, "from": from_}
            )

            hits = result["hits"]["hits"]
            return [hit["_source"] for hit in hits]
        except ElasticsearchException as e:
            logger.error(f"Error searching: {e}")
            raise

    def search_by_ip(
        self, source_ip: str, index_type: str = "logs", size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search documents by source IP.

        Args:
            source_ip: IP address to search for
            index_type: Type of index to search
            size: Number of results to return

        Returns:
            List of matching documents
        """
        query = {"term": {"source_ip": source_ip}}
        return self.search(query, index_type, size)

    def search_by_session(
        self, session_id: str, index_type: str = "logs", size: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Search documents by session ID.

        Args:
            session_id: Session identifier
            index_type: Type of index to search
            size: Number of results to return

        Returns:
            List of matching documents
        """
        query = {"term": {"session_id": session_id}}
        return self.search(query, index_type, size)

    def search_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        index_type: str = "logs",
        size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Search documents within a date range.

        Args:
            start_time: Start of date range
            end_time: End of date range
            index_type: Type of index to search
            size: Number of results to return

        Returns:
            List of matching documents
        """
        query = {
            "range": {
                "timestamp": {
                    "gte": start_time.isoformat(),
                    "lte": end_time.isoformat(),
                }
            }
        }
        return self.search(query, index_type, size)

    def count(self, query: Optional[Dict[str, Any]] = None, index_type: str = "logs") -> int:
        """
        Count documents matching a query.

        Args:
            query: Elasticsearch query DSL (None for count all)
            index_type: Type of index to search

        Returns:
            Document count
        """
        index_pattern = f"{self.index_prefix}-{index_type}-*"

        try:
            if query:
                result = self.client.count(index=index_pattern, body={"query": query})
            else:
                result = self.client.count(index=index_pattern)

            return result["count"]
        except ElasticsearchException as e:
            logger.error(f"Error counting documents: {e}")
            raise

    def delete_old_indices(self, days_to_keep: int = 30) -> List[str]:
        """
        Delete indices older than specified days.

        Args:
            days_to_keep: Number of days to retain

        Returns:
            List of deleted index names
        """
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        deleted_indices = []

        try:
            # Get all indices matching pattern
            indices = self.client.indices.get(index=f"{self.index_prefix}-*")

            for index_name in indices.keys():
                # Extract date from index name (e.g., hp_ti-logs-2025-11-19)
                parts = index_name.split("-")
                if len(parts) >= 5:
                    try:
                        index_date = datetime.strptime(
                            f"{parts[-3]}-{parts[-2]}-{parts[-1]}", "%Y-%m-%d"
                        )

                        if index_date < cutoff_date:
                            self.client.indices.delete(index=index_name)
                            deleted_indices.append(index_name)
                            logger.info(f"Deleted old index: {index_name}")
                    except ValueError:
                        # Skip indices that don't match date format
                        continue

            return deleted_indices
        except ElasticsearchException as e:
            logger.error(f"Error deleting old indices: {e}")
            raise

    def close(self) -> None:
        """Close Elasticsearch client connection."""
        self.client.close()
        logger.info("Elasticsearch client closed")
