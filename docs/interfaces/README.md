# Interface Contracts

<record_collection>interface_contracts</record_collection>

This directory contains lightweight interface contracts for data and workflow
boundaries between Gurubodh subsystems.

Use interface contracts when a workflow crosses ownership or runtime
boundaries, such as external source files, repository tooling, generated
artifacts, CMS APIs, or downstream ingestion.

Current records:

- `prepared-content-artifacts.md` - content-preparation outputs in local
  storage and Cloudflare R2 for future ingestion and metadata workflows.
- `seed-data-artifacts.md` - external seed-data CSV files, generated JSON
  artifacts, and future Strapi 5 ingestion.
