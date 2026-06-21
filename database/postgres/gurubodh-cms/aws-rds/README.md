# AWS RDS PostgreSQL Scripts

This directory is reserved for Amazon RDS-compatible PostgreSQL scripts for the Gurubodh CMS.

No localhost SQL scripts have been copied here yet. The RDS versions should be created deliberately because Amazon RDS does not provide the same privileges as a self-managed local PostgreSQL server.

Expected adaptation themes:

- Avoid `SUPERUSER`.
- Avoid granting membership in the local `postgres` role.
- Avoid unsupported or unnecessary `REPLICATION` and `BYPASSRLS` role attributes.
- Run bootstrap tasks as the RDS master/admin user.
- Keep runtime app users separate from schema migration/admin users.

Directory guide:

- `init/` will contain RDS-compatible one-time role, owner, and extension bootstrap scripts.
- `migrations/` will contain RDS-compatible database-specific privilege and lockdown scripts.
- `scripts/` will contain helper shell scripts for running the RDS SQL files.

