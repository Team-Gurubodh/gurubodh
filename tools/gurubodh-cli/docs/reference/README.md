# Reference

- [Composed configuration](configuration.md) — selectors, setting ownership, storage routing, and resource discovery.
- [Command reference](command-reference.md) — current command families and how to obtain exact installed help.
- [Legacy DOCX conversion](legacy-docx-conversion.md) — supported Unicode and legacy-font source handling.
- [Semantic chunking](semantic-chunking.md) — model-cache and supported command boundary.
- [Legacy font mapping status](legacy-font-mapping-status-and-future-work.md) — mapping risks and future-work record.

## Schema boundaries

- [Component schemas](../../config/job-components/schemas/) validate manifests,
  locales, command definitions, environments, storage profiles, and execution profiles.
- [Retained assembled-job schemas](../../config/jobs/) validate the in-memory
  result of composition before conversion to typed jobs. They do not restore
  complete-job file execution.
- [Artifact schemas](../../config/artifacts/) validate governed output payloads
  before serialization or publication.
- [Source-font policy schema](../../config/policies/source-fonts.schema.json)
  validates the shared [font policy](legacy-docx-conversion.md#source-font-safety-boundary).

These resources ship with the package for native, wheel, and container use.
The shared [validator](../../gurubodh/schema_validation.py) owns the schema
mapping and diagnostics; its [runtime enforcement tests](../../tests/test_schema_validation.py)
cover the executable boundaries.
