# Job configurations

Maintained jobs live below `jobs/subjects/<subject-group>/<language>/`. Read a job and its matching schema before changing it. Job JSON may contain paths and operational settings, but never credentials.

Each command validates the parsed job against its declared Draft 2020-12 schema
before it derives runtime settings or reads a source. Structural failures list
the job path and exact JSON location, for example
`$.chunking.model_revision`. Unknown properties are rejected wherever the
schema declares `additionalProperties: false`; `metadata_defaults` retains its
documented schema-1.4.0 extension point.

## Select a backend

| Filename convention | Source | Destination |
| --- | --- | --- |
| `*.local.json` | local | local |
| `*.r2-output.json` | local | Cloudflare R2 |
| `*.r2.json` | Cloudflare R2 | Cloudflare R2 |

Local source configuration combines `root_dir` and `relative_path`; local destination configuration combines `root_dir` and `subject_dir`. An R2 source uses `bucket` and object `key`. An R2 destination uses `bucket`, optional prefix, and `subject_dir`; R2 has object keys, not real folders.

All output layouts preserve the language-qualified subject root:

```text
cms_library/<subject-group>/<language>/
```

`subject_dir` must be a safe POSIX-relative nested path, retain a subject grouping, and end with the configured language. Absolute paths, empty segments, `.`, `..`, and backslashes are rejected. In a chunk job, source and destination must name the same language-qualified subject directory and `naming.language` must match the prepared manifest.

## Credentials

Credentials are environment-only: preparation and lab proofreading use Gemini, while R2 jobs use the Cloudflare R2 variables. Their names, scopes, and secret-handling rules are defined in [Environment setup](../environment-setup.md). Do not put a credential in a job file.

## Schema and artifact references

Use the schemas in `config/jobs/` for required fields and validation. Generated artifact schemas are in `config/artifacts/`; their lifecycle and ownership are explained in [Artifact lifecycle](../concepts/artifact-lifecycle.md).

The installed package includes both schema directories. Maintainers adding a
job or artifact schema must add it to the shared validator mapping, route its
producer through the validate-before-write helper, and add runtime tests for a
valid payload and a rejected pre-write payload.
