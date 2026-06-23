# Gurubodh CMS

Strapi 5 application for managing Gurubodh content and metadata.

The CMS is the system of record for published content. Any future tooling that
writes content into the CMS must use the Strapi API instead of modifying the CMS
database directly.

## Setup

Install dependencies from the monorepo root:

```bash
make cms-install
```

Or run npm directly from this directory:

```bash
npm ci
```

Create a local environment file from the example:

```bash
cp .env.example .env
```

Replace all placeholder secrets in `.env` before running the CMS. Do not commit
real secret values.

## Local Database

The CMS is intended to use PostgreSQL. Local PostgreSQL bootstrap, role,
privilege, and environment-specific scripts live outside the Strapi app at:

```text
database/postgres/gurubodh-cms/
```

Raw PostgreSQL infrastructure scripts must not be placed in
`apps/gurubodh-cms/database/migrations/`. That directory is reserved for Strapi
JS/TS migrations that run during application startup.

## Common Commands

From the monorepo root:

```bash
make cms-dev
make cms-build
```

From this directory:

```bash
npm run develop
npm run build
npm run start
```

`npm run develop` starts Strapi with auto-reload for local development.
`npm run build` builds the Strapi admin panel and is the preferred quick
verification command for CMS changes.
`npm run start` starts Strapi without auto-reload.

## Current Content Types

The current CMS scaffold includes:

- `category`
- `subject`

Content type schemas live under:

```text
src/api/**/content-types/**/schema.json
```

Update `docs/schemas.md` when schema locations or schema ownership rules
change.

## Related Documentation

- `../../README.md` - monorepo structure and common commands.
- `../../docs/architecture.md` - system boundaries and data flow.
- `../../docs/adr/0001-use-strapi-as-headless-cms.md` - Strapi decision record.
- `../../database/postgres/gurubodh-cms/README.md` - PostgreSQL script layout.
