# Gurubodh

Gurubodh is a monorepo for the CMS application, content preparation tools, future ingestion utilities, and ML research workspace.

## Structure

- `apps/gurubodh-cms` - Strapi 5 CMS application.
- `tools/content-preparation` - Python utility for preprocessing and preparing MS Word 2007 content and metadata artifacts.
- `tools/content-ingestion` - Placeholder for future content ingestion tooling.
- `tools/metadata-generation` - Placeholder for future metadata generation tooling.
- `tools/metadata-ingestion` - Placeholder for future metadata ingestion tooling.
- `database/postgres/gurubodh-cms` - PostgreSQL infrastructure scripts for the CMS.
- `labs/gurubodh-ml` - Placeholder for ML research and experiments.
- `docs` - Project documentation, architecture notes, decisions, templates, and AI agent-facing guidance.

## Project Documentation

- `AGENTS.md` - Canonical instruction contract for AI agents working in this repository.
- `docs/README.md` - Documentation index and routing guide.
- `docs/architecture.md` - Current architecture overview and boundaries.
- `docs/agents/` - Expanded guidance for AI agents working in this repository.
- `docs/goals.md` - Project goals and non-goals.
- `docs/adr/` - Architectural Decision Records.
- `docs/decisions/` - Operational and process decisions.
- `docs/tasks/` - Task briefs and execution history.

## Common Commands

Use the following commands from the monorepo root to work more efficiently with the monorepo.

### CMS

`make cms-install`

Installs the Strapi CMS dependencies by running `npm ci` in `apps/gurubodh-cms`.
Use this after cloning the repository or when `package-lock.json` changes.

`make cms-dev`

Starts the Strapi CMS development server from `apps/gurubodh-cms` using
`npm run develop`.

`make cms-build`

Builds the Strapi CMS from `apps/gurubodh-cms` using `npm run build`.
Use this to check that the CMS can compile for production.

### Content Preparation

`make content-prep-venv`

Creates a Python virtual environment at `tools/content-preparation/.venv`.

Before installing or running the content-preparation CLI, activate the virtual
environment:

```bash
. tools/content-preparation/.venv/bin/activate
```

`make content-prep-install`

Installs the content-preparation Python package in editable mode by running
`pip install -e .` in `tools/content-preparation`. This exposes the
`gurubodh-utils` command while keeping it linked to the source files in this
repository. After the virtual environment is activated and this install has
completed, `gurubodh-utils` is available from any directory in that shell.

For commands that read content-preparation project files, the CLI still needs
to locate `tools/content-preparation`. It does this by walking upward from the
current directory until it finds `config/conversion_job.schema.json` and
`jobs/`. If you run it from the monorepo root instead of from
`tools/content-preparation`, pass the root explicitly:

```bash
gurubodh-utils run \
  --project-root tools/content-preparation \
  --config jobs/002_spand_rahasya.json
```

`make content-prep-help`

Shows the command-line help for `gurubodh-utils`, the content-preparation CLI.

`make content-prep-run-sample`

Runs the sample content-preparation job using
`tools/content-preparation/jobs/002_spand_rahasya.json`.

