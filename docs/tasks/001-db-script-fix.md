# Task-001: Retest DB Scripts After Placement

<record_type>task_history</record_type>
<status>abandoned</status>
<date>2026-06-21</date>
<owners>Gurubodh maintainers</owners>

## Goal

Retest database role creation, migration scripts, and `run-init.sh` after moving the scripts into the new monorepo directory structure.

## Context

Rerunning the scripts showed stale path references after the script placement task.

A branch named `fix-db-scripts` had already been created before this task was recorded.

Manual repository changes noted at the time:

- `.env` had been added.
- `.env_example` had been added.

## Decisions

- Ignore `.env_example` for this task.
- Evaluate relative path references before making script changes.
- Use test role and database names to avoid colliding with roles and databases already created in the local PostgreSQL cluster.

## Approved Plan

Assess these directories:

```text
database/postgres/gurubodh-cms/localhost/init/
database/postgres/gurubodh-cms/localhost/migrations/
database/postgres/gurubodh-cms/localhost/scripts/
```

Planned changes:

- Note the relative position of `.env` against the scripts.
- Fix relative paths so referenced resources can be found at runtime.
- Append `_test` to each PostgreSQL role/user name being created.
- Change database references from `gurubodh_db` to `gurubodh_db_test` where applicable.
- Present the exact planned script changes before modifying scripts.
- Wait for user confirmation after presenting the impact.

## Execution Results

This task was abandoned before implementation.

## Follow-Up

Reopen this task only if the local PostgreSQL scripts need a dedicated test-mode variant.
