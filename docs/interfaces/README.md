# Interface Contracts

<record_collection>interface_contracts</record_collection>

This directory contains lightweight interface contracts for data and workflow
boundaries between Gurubodh subsystems.

Use interface contracts when a workflow crosses ownership or runtime
boundaries, such as external source files, repository tooling, generated
artifacts, CMS APIs, or downstream ingestion.

Current records:

- `seed-data-artifacts.md` - external seed-data CSV files, generated JSON
  artifacts, and future Strapi 5 ingestion.
