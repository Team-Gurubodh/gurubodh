-- =============================================================================
-- Lockdown - Revoke PUBLIC access
-- =============================================================================

-- Connect to gurubodh_db
\c gurubodh_db

-- Revoke default CONNECT and TEMP privileges from PUBLIC on the database
REVOKE CONNECT ON DATABASE gurubodh_db FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE gurubodh_db FROM PUBLIC;

-- Revoke default CREATE and USAGE on the public schema from PUBLIC
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE USAGE ON SCHEMA public FROM PUBLIC;

-- Revoke any privileges on existing tables, sequences and functions from PUBLIC
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

-- Ensure future objects created in this schema are not accessible by PUBLIC
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  REVOKE ALL ON FUNCTIONS FROM PUBLIC;
