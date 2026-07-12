-- -------------------------------------------------------
-- Create other roles (no login)
-- Run as postgres or db_admin at server level
-- -------------------------------------------------------
\set strapi_app_password `echo "$PWD_strapi_app"`
\set strapi_schema_migrator_password `echo "$PWD_strapi_schema_migrator"`

-- Create the read-only role (no login)
CREATE ROLE strapi_readonly WITH
  NOSUPERUSER      -- Not a superuser
  NOCREATEDB       -- Cannot create databases
  NOCREATEROLE     -- Cannot create or manage other roles
  NOINHERIT        -- Does not inherit privileges automatically
  NOLOGIN          -- Cannot log in directly (group role only)
  NOREPLICATION    -- Cannot initiate replication
  NOBYPASSRLS;     -- Must obey Row-Level Security policies

-- Create the data editor role (DML permissions, NO DDL permissions, NO Login)
CREATE ROLE strapi_data_editor WITH
  NOSUPERUSER      -- Not a superuser
  NOCREATEDB       -- Cannot create databases
  NOCREATEROLE     -- Cannot create or manage other roles
  NOINHERIT        -- Does not inherit privileges automatically
  NOLOGIN          -- Cannot log in directly (group role only)
  NOREPLICATION    -- Cannot initiate replication
  NOBYPASSRLS;     -- Must obey Row-Level Security policies

-- Create the data editor user that will be used by the strapi app 
CREATE ROLE strapi_app WITH
  NOSUPERUSER      -- Not a superuser
  NOCREATEDB       -- Cannot create databases
  NOCREATEROLE     -- Cannot create or manage other roles
  INHERIT          -- Inherits privileges from assigned roles
  LOGIN            -- Can log in
  NOREPLICATION    -- Cannot initiate replication
  NOBYPASSRLS      -- Must obey Row-Level Security policies
  CONNECTION LIMIT 20  -- Limit concurrent connections from the app
  PASSWORD :'strapi_app_password';

-- Grant the data editor role to strapi_app
GRANT strapi_data_editor TO strapi_app;

-- Create the role designed for schema migrations  (DDL permissions, NO Login)
CREATE ROLE strapi_schema_editor WITH
  NOSUPERUSER      -- Not a superuser
  NOCREATEDB       -- Cannot create databases
  NOCREATEROLE     -- Cannot create or manage other roles
  NOINHERIT        -- Does not inherit privileges automatically
  NOLOGIN          -- Cannot log in directly (group role only)
  NOREPLICATION    -- Cannot initiate replication
  NOBYPASSRLS;     -- Must obey Row-Level Security policies

-- Create the migration_runner login user
-- CONNECTION LIMIT 5 — migration_runner is only used during deployments, 
-- so a low connection limit is appropriate and safer.
CREATE ROLE strapi_schema_migrator WITH
  NOSUPERUSER      -- Not a superuser
  NOCREATEDB       -- Cannot create databases
  NOCREATEROLE     -- Cannot create or manage other roles
  INHERIT          -- Inherits privileges from assigned roles
  LOGIN            -- Can log in
  NOREPLICATION    -- Cannot initiate replication
  NOBYPASSRLS      -- Must obey Row-Level Security policies
  CONNECTION LIMIT 5   -- Low limit; only used during deployments
  PASSWORD :'strapi_schema_migrator_password';

--
-- Grant the schema editor role to migration_runner
GRANT strapi_schema_editor TO strapi_schema_migrator;

-- -------------------------------------------------------
-- DDL privileges via schema ownership delegation
-- strapi (the owner) grants schema editor the ability
-- to create and manage objects on its behalf.
-- GRANT strapi TO migration_runner — this is the critical line. 
-- In PostgreSQL, only the owner of an object can ALTER or DROP it. 
-- Since strapi owns all objects in gurubodh_db, migration_runner 
-- needs to be able to SET ROLE strapi to perform DDL operations like 
-- ALTER TABLE or DROP INDEX.  Without this, CREATE TABLE would work 
-- but ALTER TABLE and DROP TABLE would fail.
-- What migration_runner still cannot do:
--    Drop gurubodh_db itself
--    Create other databases
--    Modify other roles or users
--    Access any other database on the server
-- -------------------------------------------------------
-- 
-- Allow migration_runner to act on behalf of strapi
GRANT strapi TO strapi_schema_migrator;

-- How to use migration_runner for schema migrations:
-- 1. Connect to gurubodh_db as strapi_schema_migrator
--    \c gurubodh_db strapi_schema_migrator
-- 2. Set the role to strapi (the owner of the schema)
--    SET ROLE strapi;
--    SET search_path TO public;
-- 3. Perform the schema migration (CREATE TABLE, ALTER TABLE, etc.)
--    CREATE TABLE ...
--    ALTER TABLE ...
-- 4. Reset the role back to strapi_schema_migrator
--    RESET ROLE;
