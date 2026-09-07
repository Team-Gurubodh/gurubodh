# Decision-0010: CLI Manifest and Locale Contracts

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-09-07</date>
<owners>Gurubodh maintainers</owners>

## Context

The maintainer approved [S2 (#294)](https://github.com/Team-Gurubodh/gurubodh/issues/294)
under [#283](https://github.com/Team-Gurubodh/gurubodh/issues/283). S2 defines subject,
edition, and locale declarations for later composition. This records the concrete
interface choices within that scope; production lookup and composition remain #284.

## Decision

Both new component schemas use `component_schema_version: "1.0.0"`, own all
property specifications within their documents, and reject unknown properties
at every object boundary. In-document definitions may be reused; external
property-schema references and schema defaults are forbidden.

`subject-manifest` requires `manifest_id`, `identity`, `artifact_root`, and
nonempty `editions`. Manifest IDs are lowercase ASCII alphanumeric segments
separated by single underscores or hyphens, such as `sub123_spand_rahasya`.
They name `jobs/subjects/<manifest_id>/manifest.json`; they do not determine
the artifact root. Identity uses `CAT`/`SUB` plus three digits and the existing
alphanumeric/hyphen title-slug grammar. Editions are keyed by `hi-IN` or `mr-IN`.
Each owns a complete release, source document, and chapter-split declaration.
Release version/subversion are exactly two ASCII digits stored as strings.

Artifact roots and source paths use POSIX-relative segments. Empty, `.` and
`..` segments, backslashes, control characters, colons, dollar signs, and braces
are forbidden; this excludes absolute/drive paths, URIs, and interpolation.
Unicode, spaces, underscores, hyphens, and ordinary filename dots are allowed.
There is no path normalization or filesystem lookup during validation.
`source_document` declares `relative_path`, `font_encoding` (`aps` or `unicode`),
and `file_format: "docx"`. Validation does not inspect the source or bypass
the existing font allowlist.

Chapter splitting has three explicit shapes:

```json
{"enabled": false}
{"enabled": true, "pattern_type": "literal", "pattern": "प्रबोधन"}
{"enabled": true, "pattern_type": "regex", "pattern": "^प्रबोधन", "flags": ["MULTILINE"]}
```

Disabled splitting carries no inactive pattern settings. Literal patterns are
nonempty and forbid flags. Regex patterns are nonempty and require `flags`,
including `[]` for none, with unique values from `IGNORECASE`, `MULTILINE`,
`DOTALL`, and `VERBOSE`. The shared validator compiles declared regexes with
those flags to check Python syntax, then discards the compiled value. Structural
validation remains standalone Draft 2020-12; Python regex syntax is a separate
semantic check. Compilation failures identify the JSON location without echoing
the pattern or raw exception. Existing complete jobs keep their prior shapes
and flag behavior.

Optional manifest/edition `profile_overrides` contains only `proofreading` and/or
`chunking` versioned IDs following [Decision-0009](./0009-cli-execution-profile-contracts.md).
An empty object or omitted key inherits the less-specific selection; neither
supplies settings. The later resolver selects one whole applicable profile with
precedence command → manifest → edition → invocation. Proofreading applies to
prep and chunking to generate-chunks; DOCX consumes neither. References are
validated as IDs, never loaded here, and cannot contain inline settings.

`locale-definition` requires `locale` (`hi-IN` or `mr-IN`) and `metadata_defaults`
with explicit `source_script: "Devanagari"`, `output_text_encoding: "UTF-8"`,
and `summary_chapter_markers` (nonempty strings; an explicit empty array means
none). It names `config/job-components/locales/<locale>.json`. There is no
second language setting: the selected locale supplies assembled metadata
language. Instruction templates stay in `locales.py`; model/provider policies
stay in profiles. The existing complete-job metadata extension point remains.

Extend `validate_component(instance, component_name, path=None, *, expected_id=None)`
with `subject-manifest` and `locale-definition`. A supplied expected ID must
match `manifest_id` or `locale` respectively. `path` is display context only.
The API still returns `None`, never mutates declarations or supplies defaults,
uses cached validators, and raises safe deterministic `ConfigurationError`s.
No provider, storage, runtime policy constructor, or component loader is invoked.

## Field ownership and downstream mapping

Every S2 field is accounted for below. These are assembly obligations, not a
production resolver implemented by S2. Values are copied field by field; no
deep merge, includes, arbitrary overrides, or cross-language inheritance.

| Component field | Assembled destination or role |
| --- | --- |
| Both `component_schema_version` fields | Component format validation only; not the job's `schema_version` |
| Manifest `manifest_id` | Fixed-directory resource identity; not a naming or artifact-root fallback |
| Manifest `identity.category_code`, `subject_code`, `title_slug` | Same-named `naming` fields in prep, chunks, and DOCX |
| Manifest `artifact_root` plus selected edition/locale key | `subject_dir = artifact_root + "/" + locale`; prep destination, chunks/DOCX source and destination |
| Edition `release.version`, `release.subversion` | Same-named prep/chunks `naming` fields; omitted from DOCX naming |
| Edition `source_document.relative_path` | Prep local `source.relative_path`; R2 `source.key` joins the S3 source-store prefix with this path |
| Edition `source_document.font_encoding`, `file_format` | Same-named prep `source` fields; encoding also selects the S3 command's declared pipeline map |
| Edition `chapter_split.enabled`, `pattern_type`, `pattern`, `flags` | Same-named prep `chapter_split` fields where the selected shape permits them |
| Manifest/edition `profile_overrides.proofreading`, `.chunking` | Whole-profile selection inputs; no inline assembled settings |
| Locale `locale` / matching selected edition key | Prep `metadata_defaults.language`; chunks/DOCX `naming.language`; language-qualified artifact root |
| Locale `metadata_defaults.source_script`, `output_text_encoding`, `summary_chapter_markers` | Same-named prep `metadata_defaults` fields |

For example, explicit artifact root `library/spand` yields `library/spand/hi-IN`
and `library/spand/mr-IN`. Hindi release `"01"/"02"` and Marathi release
`"03"/"01"` remain independent. DOCX naming contains identity and language only.
APS and Unicode fixtures demonstrate the sources for the future JSON command map
(`legacy-docx-to-unicode` and `unicode-docx-ingest` respectively); S3 owns that map.

## Verification and compatibility

Independent fixtures cover APS/Hindi, Unicode/Hindi/Marathi, bilingual releases,
split shapes, optional selections, and both locale definitions. Deletion and
mutation cases check every required field and object boundary, paths, identity,
types, constants, conditional flags, semantic regex errors, and non-mutation.
Standalone and shared-validator tests forbid job-schema access; repeat through
a non-editable wheel outside the checkout with job schemas physically absent.
Separate mapping tests use real existing job validators/preparation boundaries.
Run focused tests, all 26 maintained jobs, full CLI tests, package inventories,
Markdown links, and whitespace checks.

S2 preserves existing schemas, jobs, `--config`, instruction templates, font
safety, and historical checkpoints. The schema data-files wildcard packages
both additions; broader resource discovery remains #287. Maintained catalog
and migration belong to #284–#288, with explicit retirement acceptance under
#288. S3 and the all-seven S4 review remain before #283 can close or #284 start.

## Review trigger

Review when changing locale support, identity/path grammar, split shapes,
metadata ownership, resource matching, or the downstream field mapping.
