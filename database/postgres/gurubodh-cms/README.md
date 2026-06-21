# Gurubodh CMS PostgreSQL Scripts

This directory contains PostgreSQL provisioning, role, privilege, and environment-specific database scripts for the Gurubodh CMS.

These scripts are separate from Strapi application migrations.

- `localhost/` contains scripts intended for a self-managed local PostgreSQL server.
- `aws-rds/` is reserved for scripts adapted to Amazon RDS for PostgreSQL.

Do not place these raw PostgreSQL scripts in `apps/gurubodh-cms/database/migrations`. That directory is reserved for Strapi JS/TS migrations that Strapi runs during application startup.

