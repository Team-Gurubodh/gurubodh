# Task-000: PostgreSQL DB Script Placement

<record_type>task_history</record_type>
<status>completed</status>
<date>2026-06-21</date>
<owners>Gurubodh maintainers</owners>

## Goal

Place existing PostgreSQL database scripts within the new Gurubodh monorepo.

## Context

The monorepo has these working areas:

- `apps/gurubodh-cms` - Strapi 5 CMS application.
- `tools/content-preparation` - Python content preparation scripts.

The Strapi 5 application uses a local PostgreSQL 18 database.

Existing PostgreSQL scripts had been created outside the monorepo:

- `/Users/rajeev/Code/gurubodh/database/init`
- `/Users/rajeev/Code/gurubodh/database/migrations`
- `/Users/rajeev/Code/gurubodh/database/run-init.sh`

The Strapi generator also created an application migration directory at:

```text
apps/gurubodh-cms/database/migrations/
```

That Strapi directory was empty at the time of the task.

## Decisions

- Keep PostgreSQL infrastructure scripts separate from Strapi application migrations.
- Use a root-level `database/postgres/gurubodh-cms/` area for raw PostgreSQL bootstrap, role, privilege, local database, and future AWS RDS scripts.
- Keep `apps/gurubodh-cms/database/migrations/` reserved for Strapi JS/TS migrations.
- Create AWS RDS directories as placeholders only; do not copy localhost SQL scripts into the AWS RDS tree yet.

## Approved Plan

Create this root-level PostgreSQL script area:

```text
database/
  postgres/
    gurubodh-cms/
      README.md
      localhost/
        README.md
        init/
        migrations/
        scripts/
      aws-rds/
        README.md
        init/
        migrations/
        scripts/
```

Copy the existing local PostgreSQL scripts into:

```text
database/postgres/gurubodh-cms/localhost/init/
database/postgres/gurubodh-cms/localhost/migrations/
database/postgres/gurubodh-cms/localhost/scripts/
```

Create a clarifying README in:

```text
apps/gurubodh-cms/database/migrations/README.md
```

## Execution Results

Created the root-level PostgreSQL script structure:

```text
database/postgres/gurubodh-cms/
database/postgres/gurubodh-cms/localhost/
database/postgres/gurubodh-cms/localhost/init/
database/postgres/gurubodh-cms/localhost/migrations/
database/postgres/gurubodh-cms/localhost/scripts/
database/postgres/gurubodh-cms/aws-rds/
database/postgres/gurubodh-cms/aws-rds/init/
database/postgres/gurubodh-cms/aws-rds/migrations/
database/postgres/gurubodh-cms/aws-rds/scripts/
```

Copied localhost PostgreSQL scripts into the monorepo:

```text
database/postgres/gurubodh-cms/localhost/init/000-PostgreSQL role hierarchy.md
database/postgres/gurubodh-cms/localhost/init/001-create-user-db-admin.sql
database/postgres/gurubodh-cms/localhost/init/002-create-database-owner.sql
database/postgres/gurubodh-cms/localhost/init/003-create-other-roles.sql
database/postgres/gurubodh-cms/localhost/init/004-create-extensions-cline-suggestion.sql

database/postgres/gurubodh-cms/localhost/migrations/001-set-database-owner-priviledges.sql
database/postgres/gurubodh-cms/localhost/migrations/002-set-db-admin-priviledges.sql
database/postgres/gurubodh-cms/localhost/migrations/003-set-priviledges-for-other-roles.sql
database/postgres/gurubodh-cms/localhost/migrations/004-lock-down-databse.sql

database/postgres/gurubodh-cms/localhost/scripts/run-init.sh
```

Adjusted the copied `run-init.sh` only for its new location:

- It finds init SQL files under `database/postgres/gurubodh-cms/localhost/init/`.
- It resolves the monorepo root as the `.env` location.
- Its executable bit is preserved.

Created README documentation:

```text
database/postgres/gurubodh-cms/README.md
database/postgres/gurubodh-cms/localhost/README.md
database/postgres/gurubodh-cms/aws-rds/README.md
database/postgres/gurubodh-cms/aws-rds/init/README.md
database/postgres/gurubodh-cms/aws-rds/migrations/README.md
database/postgres/gurubodh-cms/aws-rds/scripts/README.md
apps/gurubodh-cms/database/migrations/README.md
```

The `aws-rds/` tree was created with README placeholders only.

## Follow-Up

- Adapt and verify AWS RDS versions of the PostgreSQL scripts before production use.
- Leave `/Users/rajeev/Code/gurubodh/database/seed_data`, `apps/gurubodh-cms/database/migrations/.gitkeep`, and `.gitignore` untouched for this task.
