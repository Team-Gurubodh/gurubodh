# Localhost PostgreSQL Scripts

This directory contains PostgreSQL scripts for a self-managed PostgreSQL server on localhost or self managed virtual machine on a cloud.

Localhost scripts may use privileges that are appropriate for a developer-owned PostgreSQL instance, including local superuser-oriented setup. They should not be assumed to run unchanged on Amazon RDS.

Directory guide:

- `init/` contains one-time role, owner, and extension bootstrap scripts.
- `migrations/` contains database-specific privilege and lockdown scripts.
- `scripts/` contains localhost helper scripts for DBA workflows, such as
  cloning a CMS database for local testing.
