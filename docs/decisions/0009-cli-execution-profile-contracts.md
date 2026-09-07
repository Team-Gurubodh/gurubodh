# Decision-0009: CLI Execution Profile Contracts

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-09-06</date>
<owners>Gurubodh maintainers</owners>

## Context

S1 implements the proofreading and chunking profile contracts in
[#283](https://github.com/Team-Gurubodh/gurubodh/issues/283) under the provisional
[slice workflow](../development/slice-workflow.md). Component lookup, composition,
command defaults, and migration remain outside S1.

## Decision

Each profile requires exactly three properties: `component_schema_version`
(`"1.0.0"`), `profile_id`, and `proofreading` or `chunking`. The settings key
identifies the kind. All settings are explicit, including booleans and nullable
`chunking.device`.

Profile IDs contain lowercase ASCII alphanumeric segments separated by single
hyphens or dots, ending in `-v` and a positive decimal integer without leading
zeros, such as `gemini-3.6-flash-v1` or `bge-m3-v1`. Whitespace, slashes,
backslashes, URIs, interpolation, and traversal are forbidden. Schema versions
identify format; ID suffixes identify immutable policy content. Changing a used
policy requires a new ID and explicit selection. Later audits hash exact inputs;
validation alone cannot prove historical immutability.

The job component schemas in `config/job-components/schemas/` own all required
settings, types, constants, bounds, and unknown-property rules. They reference
no other schema and work with a plain Draft 2020-12 validator. The shared
validator disables remote retrieval and does not load `config/jobs/` for
component validation. `$schema` identifies the dialect and `$id` the document;
neither imports properties.

This ownership follows the maintainer's correction of S1's initial reference-based
design. Constraints preserve current policy compatibility, and existing job
definition schemas remain unchanged.

`validate_component(instance, component_name, path=None, *, expected_id=None)`
validates parsed JSON without mutation and returns `None`. It accepts
`proofreading-profile` and `chunking-profile`. `path` supplies display context
only. A supplied `expected_id` must match the validated `profile_id`; errors
echo neither ID. Invalid declarations, unknown kinds, and broken bundled schemas
raise `ConfigurationError`; existing job and artifact error domains remain.
Diagnostics identify the kind, available origin, JSON location, and violated
rule without echoing rejected values.

After structural validation, proofreading rejects progress intervals greater
than the request timeout. Validation runs no provider or settings constructor,
supplies no policy values, and uses no schema `default` annotations.

The future loader validates references before constructing the fixed path
`config/job-components/profiles/<proofreading|chunking>/<profile_id>.json`,
checks the expected kind, and passes the selected ID as `expected_id`.
In-memory validation neither reads component files nor infers identity from
diagnostic filenames.

## Profile ownership and downstream obligations

This table maps every S1 policy field to the same-named property in the assembled
job configuration. Envelope properties identify components, not policy settings.

| Profile owner | Properties | Assembled job configuration destination |
| --- | --- | --- |
| Proofreading | `enabled`, `provider`, `model`, `max_output_tokens`, `max_input_characters`, `max_retries`, `initial_retry_delay_seconds`, `max_retry_delay_seconds`, `min_request_interval_seconds`, `max_requests_per_minute`, `max_estimated_input_tokens_per_minute`, `request_timeout_seconds`, `request_progress_interval_seconds`, `unavailable_max_retries`, `unavailable_first_retry_delay_seconds`, `unavailable_second_retry_delay_seconds`, `unavailable_cooldown_seconds`, `continue_on_error` | prep-subject `proofreading` |
| Chunking | `provider`, `model`, `model_revision`, `threshold_percentile`, `min_chars`, `window_size`, `batch_size`, `normalize_contextual_vectors`, `device`, `local_files_only`, `strategy_version` | generate-chunks `chunking` |

The proofreading fixture declares `gemini-3.6-flash-v1`, model
`gemini-3.6-flash`, and 16,384 output tokens. The BGE-M3 fixture preserves the
pinned revision, threshold 78, minimum 550 characters, window 3, batch 16,
normalization enabled, nullable device, local-only loading, and
`semantic-window-v1`. These fixture values are neither schema constants nor
runtime defaults.

Whole-profile selection follows command definition → manifest → edition →
invocation, from least to most specific. Omission inherits the less-specific
selection. Settings merges, arbitrary scalar overrides, includes, interpolation,
and inheritance graphs are forbidden. Canonical prep and non-canonical lab will
select the same proofreading profile through command JSON. S3 owns that
representation; #284 owns composition and #286 CLI integration. S1 fixtures
are not a production catalog.

S1 preserves all 26 complete jobs, `--config`, policy constructors, and historical
checkpoint semantics. Later work must isolate legacy-only interpretation from
assembled job configuration and lab settings. Retirement requires explicit
maintainer comparison acceptance in #288; S1 does not decide retirement of job
definition schemas. S2–S4 own the remaining components and complete field mapping.

## Rationale and impact

Local property ownership permits independent validation, while `expected_id`
makes resource matching testable before the loader exists. Package checks use a
non-editable installation outside the checkout, including with job definition
schemas temporarily absent.

Installed discovery uses distribution `RECORD` entries and
`distribution.locate_file(entry)` because setuptools data files can install
under the environment prefix. S1's first installed probe exposed the incorrect
`site-packages/config` assumption. The fix covers component, job, and artifact
schemas and preserves source-tree precedence. #287 owns broader catalog discovery.

## Review trigger

Review when policy fields, profile identity rules, compatibility requirements,
or fixed-directory lookup change. Extending the other five component
contracts must preserve S1's validation/error boundary and requirement mapping.
