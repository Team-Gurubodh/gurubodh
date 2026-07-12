-- =============================================================================
-- Grant strapi ownership and full privileges
-- (Run after Strapi/npx has created the database and tables)
-- =============================================================================
 
-- Connect to gurubodh_db as postgres user
\c gurubodh_db

-- Grant all privileges on the database to strapi
GRANT ALL PRIVILEGES ON DATABASE gurubodh_db TO strapi;

-- Grant all privileges on all existing tables, sequences and functions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO strapi;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO strapi;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO strapi;

-- Ensure strapi owns the public schema
ALTER SCHEMA public OWNER TO strapi;

-- Set default privileges for objects created by strapi in the public schema.
-- These grants do not change object ownership; future objects are owned by
-- the role that creates them. Run schema migrations as strapi, or SET ROLE
-- strapi before creating objects, if strapi should own those objects.
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT ALL PRIVILEGES ON TABLES TO strapi;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT ALL PRIVILEGES ON SEQUENCES TO strapi;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT ALL PRIVILEGES ON FUNCTIONS TO strapi;