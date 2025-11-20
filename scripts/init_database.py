#!/usr/bin/env python3
"""
Database initialization script for HP_TI.

Creates tables and sets up initial schema in PostgreSQL and Elasticsearch.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from honeypot.config.config_loader import get_config
from pipeline.storage.postgres_client import PostgreSQLClient
from pipeline.storage.elasticsearch_client import ElasticsearchClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def init_postgres(config):
    """
    Initialize PostgreSQL database.

    Args:
        config: Application configuration
    """
    logger.info("Initializing PostgreSQL database...")

    try:
        client = PostgreSQLClient(
            database_url=config.database.postgres_url,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_timeout=config.database.pool_timeout,
        )

        # Create all tables
        client.create_tables()
        logger.info("✓ PostgreSQL tables created successfully")

        # Close connection
        client.close()

    except Exception as e:
        logger.error(f"✗ Error initializing PostgreSQL: {e}")
        raise


def init_elasticsearch(config):
    """
    Initialize Elasticsearch indices.

    Args:
        config: Application configuration
    """
    logger.info("Initializing Elasticsearch...")

    try:
        client = ElasticsearchClient(
            url=config.elasticsearch.url,
            index_prefix=config.elasticsearch.index_prefix,
            username=config.elasticsearch.username,
            password=config.elasticsearch.password,
        )

        # Create index templates
        client.create_index_templates()
        logger.info("✓ Elasticsearch index templates created successfully")

        # Close connection
        client.close()

    except Exception as e:
        logger.error(f"✗ Error initializing Elasticsearch: {e}")
        raise


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("HP_TI Database Initialization")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = get_config()

        # Initialize PostgreSQL
        init_postgres(config)

        # Initialize Elasticsearch
        init_elasticsearch(config)

        logger.info("=" * 60)
        logger.info("✓ Database initialization completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ Database initialization failed: {e}")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
