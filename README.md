# Gurubodh

Gurubodh is a monorepo for the CMS application, content preparation tools, future ingestion utilities, and ML research workspace.

## Structure

- `apps/gurubodh-cms` - Strapi 5 CMS application.
- `tools/content-preparation` - Python utility for preparing DOCX content and metadata artifacts.
- `tools/content-ingestion` - Placeholder for future content ingestion tooling.
- `tools/metadata-generation` - Placeholder for future metadata generation tooling.
- `tools/metadata-ingestion` - Placeholder for future metadata ingestion tooling.
- `labs/gurubodh-ml` - Placeholder for ML research and experiments.

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
