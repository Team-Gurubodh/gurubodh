-- =============================================================================
-- Grant db_admin full DDL privileges
-- =============================================================================

-- Connect to gurubodh_db as postgres user
\c gurubodh_db

-- Allow db_admin to connect to the database
GRANT CONNECT ON DATABASE gurubodh_db TO db_admin;

-- Allow db_admin to see, use and create objects in the public schema
GRANT USAGE, CREATE ON SCHEMA public TO db_admin;

-- Allow db_admin to read/write all existing tables and sequences
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public TO db_admin;
GRANT SELECT, USAGE, UPDATE ON ALL SEQUENCES IN SCHEMA public TO db_admin;

-- Allow db_admin to use all existing functions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO db_admin;

-- Ensure db_admin gets the same on future tables/sequences/functions created by strapi
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLES TO db_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT SELECT, USAGE, UPDATE ON SEQUENCES TO db_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO db_admin;