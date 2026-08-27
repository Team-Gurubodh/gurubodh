# Gurubodh

Gurubodh is a monorepo for preserving and making Gurubodh content available
through a CMS, content-preparation workflows, and future reading and chat
experiences.

## Project status

| Component | Status | Start here |
| --- | --- | --- |
| CMS | Active | [Gurubodh CMS](apps/gurubodh-cms/README.md) |
| Content preparation | Active | [Gurubodh CLI](tools/gurubodh-cli/README.md) |
| Seed data | Active | [Seed-data CLI](tools/seed-data-cli/README.md) |
| PostgreSQL infrastructure | Active | [Database scripts](database/postgres/gurubodh-cms/README.md) |
| Web reading experience | Planned | [Gurubodh Web](apps/gurubodh-web/README.md) |
| Chat experience | Planned | [Gurubodh Chat](apps/gurubodh-chat/README.md) |

The CMS is the system of record for published content and metadata. Content
preparation and seed-data tools produce or ingest supporting material through
their documented workflows; they are not end-user applications.

## Find the right guide

- **Work on the CMS:** start with the [CMS README](apps/gurubodh-cms/README.md)
  for setup, local development, content types, and its PostgreSQL boundary.
- **Prepare subject content:** use the [Gurubodh CLI README](tools/gurubodh-cli/README.md).
  It routes new contributors to environment setup, normal preparation, chunk
  generation, DOCX exports, and production operations.
- **Manage category, subject, or glossary seed data:** use the
  [seed-data CLI README](tools/seed-data-cli/README.md) for CSV validation,
  reviewable artifacts, and Strapi ingestion workflows.
- **Provision or maintain PostgreSQL:** read the
  [database scripts README](database/postgres/gurubodh-cms/README.md). These
  scripts are infrastructure guidance and are separate from Strapi migrations.
- **Understand the system or repository decisions:** begin with the
  [documentation index](docs/README.md), then use the
  [architecture overview](docs/architecture.md), [project goals](docs/goals.md),
  and [decision records](docs/adr/README.md) as needed.

## Repository commands

Run commands from the repository root.

| Task | Command | Details |
| --- | --- | --- |
| Install CMS dependencies | `make cms-install` | [CMS setup](apps/gurubodh-cms/README.md#setup) |
| Run the CMS locally | `make cms-dev` | [CMS commands](apps/gurubodh-cms/README.md#common-commands) |
| Build the CMS | `make cms-build` | [CMS commands](apps/gurubodh-cms/README.md#common-commands) |
| Create the CLI virtual environment | `make cli-venv` | [CLI environment setup](tools/gurubodh-cli/docs/environment-setup.md) |
| Install the CLI | `make cli-install` | [CLI getting started](tools/gurubodh-cli/docs/getting-started.md) |
| View CLI help | `make cli-help` | [CLI command reference](tools/gurubodh-cli/docs/reference/command-reference.md) |

`make cli-run-sample` runs a maintained local content-preparation job. It is
not a safe quick-start command on an unprepared clone: it requires local source
library paths and Gemini credentials, and writes preparation artifacts. Follow
the [CLI getting-started guide](tools/gurubodh-cli/docs/getting-started.md)
before running it.

## Contributing and governance

Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing. Repository work
uses an issue-first GitHub workflow; the detailed process is in the
[development guides](docs/development/README.md). See [SECURITY.md](SECURITY.md)
for vulnerability reporting and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for
community expectations.

For agent-specific repository guidance, see [AGENTS.md](AGENTS.md).
