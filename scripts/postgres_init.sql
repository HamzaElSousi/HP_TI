-- PostgreSQL Initialization Script for HP_TI
-- Creates database structure, extensions, and initial configuration

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- For GIN indexes
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- For encryption functions

-- Create database (if not exists - usually created by Docker)
-- CREATE DATABASE hp_ti_db;

-- Connect to the database
\c hp_ti_db

-- Create schemas
CREATE SCHEMA IF NOT EXISTS honeypot;
CREATE SCHEMA IF NOT EXISTS threat_intel;
CREATE SCHEMA IF NOT EXISTS pipeline;

-- Set search path
SET search_path TO honeypot, threat_intel, pipeline, public;

-- Grant permissions
GRANT ALL ON SCHEMA honeypot TO hp_ti_user;
GRANT ALL ON SCHEMA threat_intel TO hp_ti_user;
GRANT ALL ON SCHEMA pipeline TO hp_ti_user;

-- Create audit trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'HP_TI database initialized successfully at %', NOW();
END $$;

-- Create schema migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW()
);

-- Insert initial version
INSERT INTO schema_migrations (version) VALUES ('001_initial_setup')
ON CONFLICT (version) DO NOTHING;

COMMENT ON DATABASE hp_ti_db IS 'HP_TI Honeypot and Threat Intelligence Platform Database';
COMMENT ON SCHEMA honeypot IS 'Honeypot service data';
COMMENT ON SCHEMA threat_intel IS 'Threat intelligence enrichment data';
COMMENT ON SCHEMA pipeline IS 'Data pipeline processing metadata';
