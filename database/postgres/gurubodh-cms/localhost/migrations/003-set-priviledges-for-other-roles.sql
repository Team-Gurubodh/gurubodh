-- ------------------------------------------------------
-- Connect to gurubodh_db as postgres
-- ------------------------------------------------------
\c gurubodh_db

-- ------------------------------------------------------
-- set up role strapi_readonly
-- ------------------------------------------------------

-- Allow the role to connect to gurubodh_db
GRANT CONNECT ON DATABASE gurubodh_db TO strapi_readonly;

-- Allow the role to see objects in the public schema
GRANT USAGE ON SCHEMA public TO strapi_readonly;

-- Grant read-only access on all existing tables and views
GRANT SELECT ON ALL TABLES IN SCHEMA public TO strapi_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO strapi_readonly;

-- Ensure future tables and sequences are also readable
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT SELECT ON TABLES TO strapi_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO strapi_readonly;


-- ------------------------------------------------------
-- set up role strapi_data_editor
-- ------------------------------------------------------

-- Allow the role to connect to gurubodh_db
GRANT CONNECT ON DATABASE gurubodh_db TO strapi_data_editor;

-- Allow the role to see objects in the public schema
GRANT USAGE ON SCHEMA public TO strapi_data_editor;

-- Grant full data manipulation on all existing tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO strapi_data_editor;

-- Grant usage on sequences (needed for auto-increment / serial columns)
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO strapi_data_editor;

-- Ensure future tables and sequences are also accessible
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO strapi_data_editor;
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO strapi_data_editor;

-- ------------------------------------------------------
-- set up role strapi_schema_editor
-- ------------------------------------------------------
-- Allow the role to connect to gurubodh_db
GRANT CONNECT ON DATABASE gurubodh_db TO strapi_schema_editor;

-- Allow the role to see and create objects in the public schema
GRANT USAGE, CREATE ON SCHEMA public TO strapi_schema_editor;

-- Grant full data manipulation on all existing tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO strapi_schema_editor;

-- Grant full access on all existing sequences
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO strapi_schema_editor;

-- Grant execute on all existing functions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO strapi_schema_editor;

-- Ensure future tables are also accessible
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO strapi_schema_editor;

-- Ensure future sequences are also accessible
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO strapi_schema_editor;

-- Ensure future functions are also accessible
ALTER DEFAULT PRIVILEGES FOR ROLE strapi IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO strapi_schema_editor;
