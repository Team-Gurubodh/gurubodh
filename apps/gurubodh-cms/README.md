# Gurubodh CMS

Strapi 5 application for managing Gurubodh content and metadata.

The CMS is the system of record for published content. Any future tooling that
writes content into the CMS must use the Strapi API instead of modifying the CMS
database directly.

## Setup

This recipe starts the existing checkout against a **disposable local development
database**. Seed ingestion is optional. Do not scaffold a new Strapi application.

### 1. Prerequisites and database provisioning

Use Node.js and npm within the [checked-in engine ranges](package.json)
(Node `>=20.0.0 <=26.x.x`, npm `>=6.0.0`), plus a reachable local PostgreSQL
server and DBA access to provision an isolated database. The application pins
Strapi 5.50.1 and the `pg` driver; it does not pin a PostgreSQL server version.
Seed ingestion additionally needs Python 3.12 and approved CSVs or reviewed JSON
artifacts; neither source-data access nor another developer's local paths are
provided by cloning the repository.

Have the local DBA review the [PostgreSQL guide](../../database/postgres/gurubodh-cms/README.md)
and provision in this order:

1. Review `localhost/init/001`–`003` for admin, owner, and optional additional
   roles. These are manual SQL references with environment-supplied passwords,
   not an automatic installer. Use a database owner with schema-creation rights
   for local Strapi development, not the DML-only `strapi_app` role.
2. Explicitly create the disposable database owned by that role (the init files
   create roles, not the database), and ensure the owner can create objects in
   `public`. For example, in a DBA `psql` session after creating `strapi`:

   ```sql
   CREATE DATABASE gurubodh_dev OWNER strapi;
   \connect gurubodh_dev
   ALTER SCHEMA public OWNER TO strapi;
   ```

3. Start Strapi in step 3 below to create its tables. **After** object creation,
   the DBA may apply the relevant `localhost/migrations/001`–`003` grants for
   any additional roles. Review and adapt their hard-coded `gurubodh_db` target
   to the disposable database first. Keep the owner connection for development
   schema updates. `004` lockdown is optional DBA work, not a setup prerequisite;
   it contains active revocations, although its function revocations are commented.

Extension SQL is also DBA-reviewed optional infrastructure. These raw SQL files
are separate from Strapi JS/TS startup migrations under `database/migrations/`.
Do not execute the infrastructure directory blindly or use a shared database.

### 2. Install and configure

From the **monorepo root**:

```bash
make cms-install
cd apps/gurubodh-cms
cp .env.example .env
```

Copy only when creating a new local `.env`; preserve an existing configuration.
In `apps/gurubodh-cms/.env`, replace every placeholder secret with independently
generated local values. Keep the comma-separated `APP_KEYS` format and keep
secrets out of Git. Add the PostgreSQL settings below, replacing the example
user/password with the DBA-provided local credentials:

```dotenv
DATABASE_CLIENT=postgres
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_NAME=gurubodh_dev
DATABASE_USERNAME=strapi
DATABASE_PASSWORD=<local-owner-password>
DATABASE_SCHEMA=public
DATABASE_SSL=false
```

These settings come from [database.ts](config/database.ts). The example env file
omits them and the config defaults to SQLite, whose driver is not installed;
`DATABASE_CLIENT=postgres` is essential. Leave `DATABASE_URL` unset when using
these individual connection settings. Set `HOST=127.0.0.1` for local-only access
and retain `PORT=1337` unless that port is occupied.

### 3. Start and confirm the CMS is running

From `apps/gurubodh-cms` (the directory reached above):

```bash
npm run develop
```

Open [local admin](http://localhost:1337/admin), create the first local admin
account, and check that Content Manager lists Category, Subject, Sanatan Glossary,
and Prabodhan Glossary. In Settings → Internationalization, confirm English
(`en`) is the default locale; add Hindi (`hi-IN`) before seed ingestion.
This is the **running-CMS milestone**: the server/admin respond, you can sign in,
and the expected content types and locales are visible. No seed data is required.

For connection/authentication errors, check the host, port, database, and owner
credentials. For schema permission errors, ask the DBA to confirm ownership and
creation rights from step 1. A SQLite-driver error usually means the PostgreSQL
settings were omitted. Do not repair setup by scaffolding over the checkout.

### 4. Optional: ingest approved seed data

Use a second shell, starting at the monorepo root. Follow the
[seed-data CLI setup](../../tools/seed-data-cli/README.md#setup), which leaves you
in `tools/seed-data-cli` with its virtual environment active.

Obtain approved CSV exports from the maintainer, or use available reviewed
artifacts for your selected targets. The [source configuration and validation
instructions](../../tools/seed-data-cli/README.md#local-inputs-and-reviewed-artifacts)
own path setup and generation. Ingestion reads JSON artifacts, so reviewed
artifacts do not require access to the original CSVs.

Create a local API token in Settings → API Tokens with the
[Category/Subject permissions](../../tools/seed-data-cli/README.md#strapi-requirements)
and, if needed, [glossary permissions](../../tools/seed-data-cli/README.md#glossary-strapi-requirements).
The former includes reading locales and draft/published records; both require
read/create/update/publish access for their targets. Keep the token in the
local ingestion shell using `GURUBODH_STRAPI_API_TOKEN`; set
`GURUBODH_STRAPI_URL=http://localhost:1337` there too. Follow the linked guide's
environment-variable setup without putting tokens in tracked files.

From that `tools/seed-data-cli` shell, run the read-only checks and inspect the
plan before explicitly applying writes:

```bash
gurubodh-seed-data ingest preflight category
gurubodh-seed-data ingest plan category
# Only after reviewing a plan with zero conflicts and blocked records:
gurubodh-seed-data ingest apply category

gurubodh-seed-data ingest preflight subject
gurubodh-seed-data ingest plan subject
# Only after Categories exist and this plan is clear:
gurubodh-seed-data ingest apply subject
```

Apply writes only to the disposable local database configured above.
Category/Subject ingestion **publishes** created/updated records regardless of
artifact `desired_status`. Categories must exist before dependent Subjects;
applying one target does not apply another. Glossaries are independent: use
[their preflight → plan → explicit apply sequence](../../tools/seed-data-cli/README.md#glossary-preflight-and-reports)
for `sanatan-glossary` or `prabodhan-glossary` as needed.

Success means preflight passes and a repeat `ingest plan <target>` reports zero
creates, updates, conflicts, blocked records, and publish actions. In Admin,
confirm published records, Category–Subject relations, and English/Hindi
localizations; glossary records are non-localized. Use the seed guide's
[recovery instructions](../../tools/seed-data-cli/README.md#recovery-guidance)
for missing locales, inaccessible endpoints, duplicate codes, or partial applies;
resolve failed checks before proceeding.

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
- `prabodhan-glossary`
- `sanatan-glossary`
- `subject`

Content type schemas live under:

```text
src/api/**/content-types/**/schema.json
```

## Related Documentation

- [Repository onboarding](../../docs/README.md) - orientation and contribution routes.
- [Architecture](../../docs/architecture.md) - system boundaries and domain vocabulary.
- [Strapi decision](../../docs/adr/0001-use-strapi-as-headless-cms.md).
- [PostgreSQL guide](../../database/postgres/gurubodh-cms/README.md) - manual DBA boundary.
