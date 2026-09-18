# Gurubodh CMS PostgreSQL Scripts

This directory contains PostgreSQL provisioning, role, privilege, and environment-specific database scripts for the Gurubodh CMS.

These scripts are separate from Strapi application migrations.

- `localhost/` contains scripts intended for a self-managed local PostgreSQL server.
- `aws-rds/` is reserved for scripts adapted to Amazon RDS for PostgreSQL.

Do not place these raw PostgreSQL scripts in `apps/gurubodh-cms/database/migrations`. That directory is reserved for Strapi JS/TS migrations that Strapi runs during application startup.

These scripts are intentionally manual DBA references. For the ordered local
application path, use the [CMS setup recipe](../../../apps/gurubodh-cms/README.md#setup).
The DBA provisions roles and a database before the existing Strapi application
starts and creates its tables; no new application scaffolding is needed.

- `localhost/init/` contains role and optional extension references.
- `localhost/migrations/` contains post-creation privilege guidance.
- `localhost/migrations/004-lock-down-databse.sql` contains active revocations;
  only its function revocations are deliberately commented. Lockdown is optional
  DBA work, not a prerequisite for local onboarding.

