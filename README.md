# Gurubodh

Gurubodh is a monorepo for the CMS application, content preparation tools, future ingestion and metadata utilities, and ML research workspace.

## Structure

- `apps/gurubodh-cms` - Strapi 5 CMS application.
- `tools/content` - Python utility for preprocessing and preparing
  MS Word 2007 content and metadata artifacts. Future content ingestion and
  metadata workflow commands are expected to live in the `gurubodh`
  command structure here.
- `tools/seed-data` - Seed-data preparation and ingestion tooling, starting with glossary terms.
- `database/postgres/gurubodh-cms` - PostgreSQL infrastructure scripts for the CMS.
- `labs/gurubodh-ml` - Placeholder for ML research and experiments.
- `docs` - Project documentation, architecture notes, decisions, templates, and AI agent-facing guidance.

## Project Documentation

- `AGENTS.md` - Canonical instruction contract for AI agents working in this repository.
- `docs/README.md` - Documentation index and routing guide.
- `docs/architecture.md` - Current architecture overview and boundaries.
- `docs/agents/` - Expanded guidance for AI agents working in this repository.
- `docs/development/` - Contributor workflow guides for GitHub, pull requests, and commit standards.
- `docs/goals.md` - Project goals and non-goals.
- `docs/adr/` - Architectural Decision Records.
- `docs/decisions/` - Operational and process decisions.
- `docs/tasks/` - Task briefs and execution history.
- `CONTRIBUTING.md` - Contributor expectations and pull request workflow.
- `SECURITY.md` - Security reporting and secrets policy.
- `CODE_OF_CONDUCT.md` - Contributor conduct expectations.

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

`make content-venv`

Creates a Python 3.12 virtual environment at `tools/content/.venv`.

Before installing or running the content CLI, activate the virtual
environment:

```bash
. tools/content/.venv/bin/activate
```

`make content-install`

Installs the content Python package in editable mode by running
`pip install -e .` in `tools/content`. This exposes the
`gurubodh` command while keeping it linked to the source files in this
repository. The content package requires Python `>=3.12,<3.13` and
includes local semantic chunking dependencies for future paragraphing and RAG
preparation work. After the virtual environment is activated and this install
has completed, `gurubodh` is available from any directory in that shell.

For commands that read content project files, the CLI still needs
to locate `tools/content`. It does this by walking upward from the
current directory until it finds `config/conversion_job.schema.json` and
`jobs/`. If you run it from the monorepo root instead of from
`tools/content`, pass the root explicitly:

```bash
gurubodh prep-subject \
  --project-root tools/content \
  --config jobs/002_spand_rahasya.local.json
```

`make content-help`

Shows the command-line help for `gurubodh`, the content CLI.

`make content-run-sample`

Runs the sample content job using
`tools/content/jobs/002_spand_rahasya.local.json`.

### Repository Tooling

`npm ci`

Installs root repository governance tooling, including Commitlint and Husky.
Requires Node.js `>=22.12.0 <=26.x.x` and npm `>=10.0.0`.

`npm run commitlint`

Checks commits on the current branch against `origin/main` using the root
Commitlint configuration.
