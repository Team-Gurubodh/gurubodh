# Job configurations

Maintained jobs live below `jobs/subjects/<subject-group>/<language>/`. Read a job and its matching schema before changing it. Job JSON may contain paths and operational settings, but never credentials.

Each command validates the parsed job against its declared Draft 2020-12 schema
before it derives runtime settings or reads a source. Structural failures list
the job path and exact JSON location, for example
`$.chunking.model_revision`. Unknown properties are rejected wherever the
schema declares `additionalProperties: false`; `metadata_defaults` retains its
documented schema-1.5.0 extension point.

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

## Proofreading operational settings

The `proofreading` object is strict: every prep-subject job must provide all 18
properties, including `enabled: true` and `continue_on_error: false`. In
particular, it must explicitly provide the positive request deadline and
progress interval (`request_timeout_seconds` and
`request_progress_interval_seconds`) plus the 503-capacity recovery values
`unavailable_max_retries`, `unavailable_first_retry_delay_seconds`,
`unavailable_second_retry_delay_seconds`, and `unavailable_cooldown_seconds`.
The maintained jobs use `120`, `15`, `2`, `30`, `90`, and `120` respectively.
The interval cannot exceed the deadline. These are operational settings and do
not affect canonical proofreading output or resume compatibility.

## Schema and artifact references

### Execution-profile component contracts

`gurubodh.schema_validation.validate_component()` validates profiles independently.
Each requires `component_schema_version: "1.0.0"`, a versioned `profile_id`
such as `gemini-3.6-flash-v1` or `bge-m3-v1`, and complete `proofreading` or
`chunking` settings. Each job component schema owns its specifications without
references to other schemas. Unknown or missing fields fail without defaults;
a supplied `expected_id` must match `profile_id`.

The [fixtures](../../tests/fixtures/job-components/README.md) include examples
and verification commands. The
[profile decision](../../../../docs/decisions/0009-cli-execution-profile-contracts.md)
maps all 29 fields to the assembled job configuration and defines identity and
whole-profile precedence. Used IDs are immutable; policy changes require a new
ID and explicit selection.

Profile and subject/locale component validation are implemented. The future catalog uses
`config/job-components/profiles/proofreading/` and
`config/job-components/profiles/chunking/`. Production declarations, lookup,
command/manifest/edition/invocation selection, and canonical/lab binding remain
pending. Complete jobs and `--config` remain supported until the maintainer
accepts comparison results under #288.

### Subject and locale component contracts

`validate_component()` also accepts `subject-manifest` and `locale-definition`.
Both require `component_schema_version: "1.0.0"` and reject unknown or missing
properties. Optional `expected_id` matches `manifest_id` or `locale`; the display
filename never supplies identity. Representative declarations live in the
[component fixtures](../../tests/fixtures/job-components/README.md).

A manifest declares its identity, explicit artifact root, and one or both
`hi-IN`/`mr-IN` editions. Each edition owns its two-digit string release,
DOCX source declaration, and chapter splitting. Disabled splitting is exactly
`{"enabled": false}`; enabled literal splitting requires a pattern and forbids
flags; enabled regex splitting requires a pattern and explicit flags (`[]`
means none). Manifest/edition overrides contain only whole proofreading or
chunking profile IDs. Nothing is inherited from another language edition.

Locale JSON explicitly declares Devanagari, UTF-8, and summary markers. The
selected locale supplies assembled metadata language; instruction templates
remain in `locales.py`. Artifact `subject_dir` is the declared root plus `/` and
locale. No value is inferred from a manifest ID or directory.

[Decision-0010](../../../../docs/decisions/0010-cli-manifest-locale-contracts.md)
defines the exact identity/path grammar, conditional shapes, and complete field
mapping. These contracts do not activate composition or replace maintained jobs.

### Jobs and artifacts

Use the schemas in `config/jobs/` for required fields and validation. Generated artifact schemas are in `config/artifacts/`; their lifecycle and ownership are explained in [Artifact lifecycle](../concepts/artifact-lifecycle.md).

The package includes job, artifact, and component schema directories. New job
or artifact schemas require registration in the shared validator mapping,
producer use of the validate-before-write helper, and runtime tests for valid
payloads and rejection before writing.
