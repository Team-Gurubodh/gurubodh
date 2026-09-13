# Reference

- [Command reference](command-reference.md) — current command families and how to obtain exact installed help.
- [Legacy DOCX conversion](legacy-docx-conversion.md) — supported Unicode and legacy-font source handling.
- [Semantic chunking](semantic-chunking.md) — model-cache and supported command boundary.
- [Legacy font mapping status](legacy-font-mapping-status-and-future-work.md) — mapping risks and future-work record.

Schemas are the machine-validated source of truth:

```text
config/jobs/prep_subject_job.schema.json
config/jobs/generate_chunks_job.schema.json
config/jobs/generate_docx_job.schema.json
config/artifacts/
config/policies/source-fonts.schema.json
```

The package installs `jsonschema` and bundles these files for native, wheel,
and container execution. In-memory validators validate assembled job configurations before converting them to
typed prepared-job records; schema-governed artifact writers validate payloads before
serialization or publication. When maintaining a schema boundary, update the
shared mapping and runtime enforcement tests together with the schema.
