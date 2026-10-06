# Prepared Content Artifact Interface

<record_type>interface_contract</record_type>
<status>accepted</status>
<date>2026-07-08</date>
<owners>Gurubodh maintainers</owners>

## Boundary and authority

Source DOCX → preparation → local/private R2 artifacts → derived commands and
future chapter/metadata ingestion. Preparation does not publish CMS entries.

Canonical prepared content is the proofread versioned text/metadata pair.
Unmodified extracted text and proofreading records are provenance. Semantic
chunks and chapter DOCX exports are rebuildable derivatives. Retrieval
embeddings are future retrieval data, not canonical preparation outputs.
Source or transient Unicode DOCX is not a published canonical artifact; lab
proofreading output is non-canonical.

Schemas in [config/artifacts](../../tools/gurubodh-cli/config/artifacts/) own
structural fields. The [shared validator](../../tools/gurubodh-cli/gurubodh/schema_validation.py)
validates governed payloads before serialization/publication. The
[configuration reference](../../tools/gurubodh-cli/docs/reference/configuration.md#storage-and-library-roots)
owns library roots, stores, and routing; credentials belong to operator setup.

## Command ownership and locale roots

A release root is `cms_library/{subject-group}/{language}/`, where the final
`subject_dir` segment matches the configured locale (`hi-IN` or `mr-IN`).
Source/destination roots, naming, manifest, and metadata must agree on locale.
Hindi and Marathi releases have independent state, provenance, outputs, and
overwrite effects. Paths must be safe relative paths confined to their release.
No command owns the entire subject root.

| Owner | Paths relative to the release root | Role |
| --- | --- | --- |
| `prep-subject` | `chapters/text_and_metadata/`, `chapters/chapter_content_manifest.json` | Canonical proofread text/metadata and current candidate set |
| `prep-subject` | `chapters/unmodified_source_text/`, `chapters/proofreading/` | Exact extracted/converted proofreading input, diffs, safe provenance |
| `prep-subject` | `run_state/prep-subject/`, `.work/prep-subject/` | Operational checkpoint and non-canonical staging |
| `generate-chunks` | `chapters/semantic_chunks/` | Chunk-only artifacts and `semantic_chunks_manifest.json` readiness marker |
| `generate-docx` | `chapters/msword/` | Human-readable DOCX and `docx_manifest.json` readiness marker |
| Each command | `run_reports/<command>/` | Independently retained JSON/Markdown audits |

Provenance records bind source and corrected artifacts, locale/template identity,
and checksums without embedding full texts, prompts, credentials, or raw provider
responses. Staging and unmodified-source paths are never canonical candidates.
R2 references use private bucket/key addressing; local references use paths.
URLs may be null and cannot be required for consumption. Temporary processing
paths must not appear in generated metadata for R2-backed jobs.

## Content identity and manifest

`content_key` identifies normalized chapter content state within Category code,
Subject code, and language. Normalized text edits change it; unchanged text
reordered among chapters retains it. It is not permanent editorial chapter
identity, a registry, or revision history. Normalization and key construction
are defined in [content_identity.py](../../tools/gurubodh-cli/gurubodh/content_identity.py).

`normalized_content_sha256` checks normalized text. The metadata's
`integrity.artifacts.text` checks exact emitted UTF-8 artifact bytes. These
checksums have different purposes and are not interchangeable. New canonical
text has LF internal line endings, no carriage returns, and one final LF;
identity normalization additionally handles Unicode and whitespace equivalence.

`chapter_content_manifest.json` is the sole chapter-selection authority.
Derived commands use only its selected metadata/text pairs, validate safe
references, subject/locale identity, filenames, content keys, and exact text
checksums, and bind outputs to the exact source-manifest bytes. DOCX uses the
manifest order. Loose files and provenance do not authorize selection.

## Canonical-consumption gate

Consumers must require a succeeded prep job and succeeded publication bound to
the candidate manifest, including matching chapter membership and identities.
Missing, malformed, incomplete, or publishing state does not authorize derived
consumption, even if prior canonical files remain. Implemented validation is in
[canonical_release.py](../../tools/gurubodh-cli/gurubodh/canonical_release.py) and
[canonical_source.py](../../tools/gurubodh-cli/gurubodh/canonical_source.py).
Both derived commands revalidate state and manifest immediately before publishing.

Valid succeeded legacy releases remain consumable subject to these checks;
current readers accept metadata versions `1.3.0` and `1.4.0` and succeeded legacy
checkpoint version 1. Age alone does not require regeneration. Incompatible
incomplete checkpoints require intentional replacement. Missing/invalid content
identity or malformed canonical text, including any carriage return, requires
repair through intentional `prep-subject --overwrite`; derived commands do not
repair canonical artifacts. See [recovery](../../tools/gurubodh-cli/docs/operations/recovery.md).

## Derived readiness

Chunks contain text, spans, checksums, token estimates, and chunking provenance.
Temporary boundary-selection vectors are not persisted retrieval embeddings.
The legacy combined chunks/embeddings path is unsupported for new ingestion.

DOCX remains a human-readable export. Its generator validates OOXML and
round-trips the body to canonical text before publication. Formatting and title
details belong to [docx/export.py](../../tools/gurubodh-cli/gurubodh/docx/export.py).
Consumers of either derived set must require and validate its readiness marker,
source binding, selected chapter coverage, and artifact checksums.

## Replacement, audit, and recovery obligations

A compatible `--resume` continues the persisted prep job; `--overwrite` starts a
replacement. Replacement authorization persists in job state across resume;
resume does not grant it to an ordinary job. An unfinished replacement preserves
prior canonical and derived files, but the latest prep state still gates use.
Only successful canonical replacement invalidates same-locale chunks and DOCX
and removes retired `full_subject/`. Regenerate required derived outputs afterward.

Derived overwrite replaces only that command's output set. Staged validation and
source revalidation precede publication. Local replacement preserves prior output
until promotion and restores it if the directory swap fails. Chunk overwrite
cleans legacy combined output only after successful v2 publication. Audits and
other locales/commands remain outside output replacement.

R2 multi-object publication is non-atomic. Prep publishes its canonical manifest
last and requires succeeded, manifest-bound state. Derived overwrite removes the
old readiness marker before replacing objects, then uploads the validated new
marker last. A derived prefix without its marker is incomplete; readers must not
infer readiness from object presence. Review failure audits before rerunning with
`--overwrite`. No versioned-release/current-pointer protocol is implemented.

Use one writer per release; locks and R2 leases are advisory guardrails, not
reliable distributed mutual exclusion. Audits are retained independently and
must not be removed by output cleanup. Detailed lifecycle and operator procedures
are owned by [prep publication](../../tools/gurubodh-cli/gurubodh/prep_publication.py),
[derived lifecycle](../../tools/gurubodh-cli/gurubodh/derived_artifact_lifecycle.py),
[prep recovery](../../tools/gurubodh-cli/docs/workflows/prepare-a-subject.md#resume-and-replacement),
and [R2 recovery](../../tools/gurubodh-cli/docs/operations/r2-production-runs.md#derived-output-readiness-and-failed-retries).
