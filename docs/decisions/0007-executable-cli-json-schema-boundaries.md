# Decision-0007: Executable Gurubodh CLI JSON Schema Boundaries

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-29</date>
<owners>Gurubodh maintainers</owners>

## Context

Gurubodh CLI job and artifact structures were defined in Draft 2020-12 JSON
Schemas, but loaders and producers repeated only selected constraints in Python.
That allowed the documented contract and runtime behavior to diverge.

## Decision

Treat the JSON Schemas under `tools/gurubodh-cli/config/jobs/` and
`tools/gurubodh-cli/config/artifacts/` as executable structural authorities.
Raw jobs validate before conversion to typed prepared-job records; runtime-only
values do not become job payload keys. Every schema-governed artifact
payload validates before serialization, checksum calculation, staging, local
publication, or R2 upload. One shared cached Draft 2020-12 validator owns schema
discovery and safe diagnostics in local, installed-package, and container
execution.

Retain Python checks only for runtime semantics not authoritatively modeled in
the schemas, including safe path behavior, regex compilation, derived locale
relationships, release-root identity, content/checksum binding, and model-cache
behavior.

The prep-subject schema `1.4.0` keeps its existing explicit
`metadata_defaults.additionalProperties: true` extension point. Undeclared
values there have no defined runtime effect. Other job objects retain their
strict existing `additionalProperties: false` behavior.

Reconcile `source.file_format` with the implemented boundary by declaring it
as `const: "docx"`. The CLI has never supported another prep source format, so
this makes the schema express the existing operational constraint rather than
introducing a new format or artifact version.

## Rationale

A single executable structural definition prevents loaders and writers from
silently accepting data that downstream tooling cannot trust. Validating before
serialization preserves existing atomic/staged and readiness-manifest-last
publication semantics because invalid payloads never become visible outputs.

## Impact

- CLI installation includes the maintained schemas and the `jsonschema`
  dependency.
- Unknown fields at strict boundaries, invalid conditionals, duplicate chapter
  selections, and other schema violations now fail at load time.
- Artifact-construction regressions fail before a governed JSON file is written
  or uploaded.
- Future schemas and producers must be registered in the shared validator and
  covered by runtime enforcement tests.

## Review Trigger

Review when adding another job/artifact schema location, changing packaging,
removing the `metadata_defaults` extension point, or supporting a prep source
format other than DOCX.
