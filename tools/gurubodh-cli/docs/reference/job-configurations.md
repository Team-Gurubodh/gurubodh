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

The [component verification guide](../concepts/internal-workflow-contracts.md#component-contract-verification)
describes fixtures and verification commands. The
[profile decision](https://github.com/Team-Gurubodh/gurubodh/issues/292#issuecomment-5571635810)
maps all 29 fields to the assembled job configuration and defines identity and
whole-profile precedence. Used IDs are immutable; policy changes require a new
ID and explicit selection.

All seven component validators are implemented; S3's contract remains in
[#296](https://github.com/Team-Gurubodh/gurubodh/issues/296). The
[S4 field mapping](https://github.com/Team-Gurubodh/gurubodh/issues/298#issuecomment-5571636607)
accounts for every assembled field, omission rule, and legacy allowance.
The shared catalog now lives under `config/job-components/`: `commands/`,
`environments/`, `storage-profiles/`, `locales/`, `profiles/proofreading/`, and
`profiles/chunking/`. Prep and lab command JSON both select
`gemini-3.6-flash-v1` (Gemini 3.6 Flash, 16,384 output tokens). Chunking selects
`bge-m3-semantic-window-v1`, preserving the pinned BGE-M3 revision and existing
78th-percentile, 550-character, three-sentence-window settings.

### Compose through the Python API

`ComponentCatalog(cli_root)` in `gurubodh.job_components` loads fixed resource
IDs. `resolve_job()` in `gurubodh.job_composition` takes that catalog and explicit
keyword selectors: `command`, `manifest_id`, `locale`, `environment_id`, and
`storage_profile_id`. It returns `ResolvedJob`: `.job` is the existing typed
prepared job, and `.inputs` retains immutable resolution inputs for subsequent
audit integration. `.job.to_payload()` contains only assembled job fields.

Manifests load from `jobs/subjects/<manifest-id>/manifest.json`. Shared IDs load
from their fixed catalog directories. Lookup rejects unsafe IDs, symlink escapes,
missing or wrong-kind resources, duplicate JSON properties, ID mismatches,
unsupported versions, and malformed declarations before execution. All seven
component kinds validate with their own schemas independently of job schemas;
the assembled job then passes the existing job-schema and semantic checks.

Optional `proofreading_profile_id` and `chunking_profile_id` arguments select
complete applicable profiles. Precedence is command JSON → manifest → edition →
invocation. Only the winning profile supplies settings; missing fields fail.
Manifest/edition selections for other commands are ignored; irrelevant invocation
selections fail. Only `generate-chunks` accepts `chapters`, a nonempty unique list
of exact three-ASCII-digit strings; omission leaves selection unspecified.
Other field overrides, interpolation, includes, and deep merging are unsupported.

The development environment declares four stores. The `local`, `r2-output`,
and `r2` storage profiles select their roles. Local bindings use
`{"$env": "GURUBODH_SOURCE_LIBRARY_ROOT"}` and
`{"$env": "GURUBODH_CMS_LIBRARY_ROOT"}`. Used values must be nonempty absolute
paths; resolution performs no tilde or embedded-variable expansion and does not
require directories to exist. It reads only used root names, never enumerates
the environment, and rejects credential/model-cache variables as library roots.
An R2-only job needs neither local root. Derived commands using `r2-output` read
the **local destination library** and write R2; prep on that route reads the
local source library and writes R2. Unused declarations still validate structurally.

Composition reads configuration only: it does not access source content, load
models, create provider/storage clients, update checkpoints, or write outputs.
Component bytes, selections, chapters, and used non-secret root bindings are
captured when the job is assembled, so later file changes cannot alter its
recorded inputs. Model-cache location and credentials remain existing runtime
environment inputs outside the job payload.

Canonical composition is currently a Python API. CLI execution/inspection is
owned by #286, broader resource packaging/discovery by #287, and maintained
subject-manifest migration by #288. The 26 complete jobs and their `--config`
execution path remain supported until the maintainer accepts the comparison
results under #288. Historical optional-field interpretations are isolated in
`complete_job_compat.py`; checkpoint-reading compatibility is retained separately.

### Subject and locale component contracts

`validate_component()` also accepts `subject-manifest` and `locale-definition`.
Both require `component_schema_version: "1.0.0"` and reject unknown or missing
properties. Optional `expected_id` matches `manifest_id` or `locale`; the display
filename never supplies identity. Representative declarations live in the
[component fixtures](../../tests/fixtures/job-components/).

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

[Decision-0010](https://github.com/Team-Gurubodh/gurubodh/issues/294#issuecomment-5571636132)
defines the exact identity/path grammar, conditional shapes, and complete field
mapping. These contracts do not activate composition or replace maintained jobs.

### Jobs and artifacts

Use the schemas in `config/jobs/` for required fields and validation. Generated artifact schemas are in `config/artifacts/`; their lifecycle and ownership are explained in [Artifact lifecycle](../concepts/artifact-lifecycle.md).

The package includes job, artifact, and component schema directories. New job
or artifact schemas require registration in the shared validator mapping,
producer use of the validate-before-write helper, and runtime tests for valid
payloads and rejection before writing.
