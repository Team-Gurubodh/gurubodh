# Gurubodh

Gurubodh is a monorepo for the CMS application, content preparation tools, future ingestion utilities, and ML research workspace.

## Structure

- `apps/gurubodh-cms` - Strapi 5 CMS application.
- `tools/content-preparation` - Python utility for preparing DOCX content and metadata artifacts.
- `tools/content-ingestion` - Placeholder for future content ingestion tooling.
- `tools/metadata-generation` - Placeholder for future metadata generation tooling.
- `tools/metadata-ingestion` - Placeholder for future metadata ingestion tooling.
- `database/postgres/gurubodh-cms` - PostgreSQL infrastructure scripts for the CMS.
- `labs/gurubodh-ml` - Placeholder for ML research and experiments.
- `docs` - Project documentation, architecture notes, decisions, templates, and agent-facing guidance.

## Project Documentation

- `AGENTS.md` - Canonical instruction contract for AI agents working in this repository.
- `docs/README.md` - Documentation index and routing guide.
- `docs/architecture.md` - Current architecture overview and boundaries.
- `docs/agents/` - Expanded guidance for AI agents working in this repository.
- `docs/goals.md` - Project goals and non-goals.
- `docs/adr/` - Architectural Decision Records.
- `docs/decisions/` - Operational and process decisions.
- `docs/tasks/` - Task briefs and execution history.
- `docs/templates/` - Templates for ADRs, decisions, and task records.

## Common Commands

```bash
make cms-install
make cms-dev
make cms-build
make content-prep-venv
make content-prep-install
make content-prep-help
```

Each project can also be run directly from its own directory.
