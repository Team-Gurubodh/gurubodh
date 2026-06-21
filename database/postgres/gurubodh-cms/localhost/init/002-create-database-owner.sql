-- -------------------------------------------------------------------------
-- Create the strapi role with limited but sufficient privileges
-- login as user postgres to create roles
-- This user will own the database gurubodh_db
-- -------------------------------------------------------------------------
\set strapi_password `echo "$PWD_strapi"`

CREATE ROLE strapi WITH
  NOSUPERUSER      -- Not a superuser (restricted access)
  CREATEDB         -- Can create new databases
  NOCREATEROLE     -- Cannot create or manage other roles
  INHERIT          -- Inherits privileges of roles it's a member of
  LOGIN            -- Can log in
  NOREPLICATION    -- Cannot initiate replication
  NOBYPASSRLS      -- Must obey Row-Level Security policies
  CONNECTION LIMIT -1  -- Unlimited connections
  PASSWORD :'strapi_password';


