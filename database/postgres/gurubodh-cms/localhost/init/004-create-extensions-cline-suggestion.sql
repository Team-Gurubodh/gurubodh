-- ============================================================
-- PostgreSQL Initialization Script — Extensions
-- Run automatically on first container start via Docker's
-- /docker-entrypoint-initdb.d/
-- ============================================================

-- Enable UUID generation (useful for Strapi 5 primary keys)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for encryption/hashing functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enable full-text search enhancements (if needed beyond default)
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Enable fuzzy string matching (useful for search features)
CREATE EXTENSION IF NOT EXISTS "fuzzystrmatch";