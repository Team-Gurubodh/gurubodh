-- -------------------------------------------------------------------------
-- Create the db_admin role with superuser privileges
-- login as user postgres to create roles
-- -------------------------------------------------------------------------
\set db_admin_password `echo "$PWD_db_admin"`

CREATE ROLE db_admin WITH
  SUPERUSER        -- Full superuser access (bypasses all permission checks)
  CREATEDB         -- Can create new databases
  CREATEROLE       -- Can create and manage other roles
  INHERIT          -- Inherits privileges of roles it's a member of
  LOGIN            -- Can log in (makes it a user, not just a role)
  REPLICATION      -- Can initiate streaming replication / use pg_basebackup
  BYPASSRLS        -- Bypasses Row-Level Security policies
  CONNECTION LIMIT -1  -- Unlimited connections (-1 = no limit)
  PASSWORD :'db_admin_password';  -- Set a strong password

-- -------------------------------------------------------------------------
-- Optional: Grant membership in the postgres role (for full equivalence)
-- -------------------------------------------------------------------------
GRANT postgres TO db_admin;

-- -------------------------------------------------------------------------
-- Optional: Allow db_admin to set the search_path and other session parameters
-- It sets the `search_path` configuration parameter for the role `db_admin`.
-- However, there's an important nuance:
-- `"$user"` in PostgreSQL is a __special placeholder__
-- it's replaced at runtime with the name of the current user (the role that logs in). 
-- It is __not__ a shell variable, so it should be a __single-quoted string__, 
-- not double-quoted:
-- Both forms actually work in PostgreSQL because PostgreSQL's `SET` 
-- syntax is lenient with string quoting here
-- -------------------------------------------------------------------------
ALTER ROLE db_admin SET search_path TO "$user", public;


