# Gurubodh CMS PostgreSQL Scripts

This directory contains PostgreSQL provisioning, role, privilege, and environment-specific database scripts for the Gurubodh CMS.

These scripts are separate from Strapi application migrations.

- `localhost/` contains scripts intended for a self-managed local PostgreSQL server.
- `aws-rds/` is reserved for scripts adapted to Amazon RDS for PostgreSQL.

Do not place these raw PostgreSQL scripts in `apps/gurubodh-cms/database/migrations`. That directory is reserved for Strapi JS/TS migrations that Strapi runs during application startup.

Also, these scripts are intentionally not automated. Rather they are present to guide the DBA to create appropriate roles before Strapi Application creates tables and objects in the database created for the application.
- Scripts in the ```init``` directory can be used at the time of creating the Strapi application database.
- Scripts in the ```migrations``` directory can be used after Strapi is installed.
- Script  ```migrations/004-lock-down-databse.sql``` is deliberately commented.

