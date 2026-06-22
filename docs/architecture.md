# Architecture

<record_type>architecture_overview</record_type>
<status>living</status>

## System Map

```text
gurubodh/
  apps/
    gurubodh-cms/              Strapi 5 CMS application
  tools/
    content-preparation/       Python DOCX and metadata preparation tooling
    content-ingestion/         Future ingestion tooling
    metadata-generation/       Future metadata generation tooling
    metadata-ingestion/        Future metadata ingestion tooling
  database/
    postgres/gurubodh-cms/     PostgreSQL infrastructure scripts
  labs/
    gurubodh-ml/               ML research workspace
  docs/                        Project documentation and templates
```

## Current Boundaries

- The CMS application owns Strapi runtime code, Strapi content types, CMS configuration, and Strapi migrations.
- `database/postgres/gurubodh-cms/` owns raw PostgreSQL bootstrap, roles, privileges, local database scripts, and future AWS RDS scripts.
- `tools/content-preparation/` owns content preparation utilities and schemas used by those utilities.
- `docs/` owns durable project knowledge that should be discoverable by humans and AI agents.
- `docs/tasks/` owns task briefs and execution history.

## Architecture Decision Records

Durable architecture changes should be recorded in `docs/adr/` using `docs/templates/adr-template.md`.

## Update Rules

<update_rules>
Update this file when a module, boundary, runtime dependency, deployment shape, or data ownership rule changes.
</update_rules>
