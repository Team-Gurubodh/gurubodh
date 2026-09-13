# Composed configuration

Canonical commands assemble a job from explicit selectors and validated JSON
components. Edit the owning component, then inspect the assembled result with
[`config resolve`](command-reference.md#config-resolve). Complete-job files and
`--config` execution are retired; exported JSON cannot be passed back as an
executable configuration. [#288](https://github.com/Team-Gurubodh/gurubodh/issues/288)
contains the historical migration evidence.

## Selectors and ownership

`prep-subject`, `generate-chunks`, and `generate-docx` require `--subject`,
`--language`, `--environment`, and `--storage-profile`. `config resolve` also
requires `--command` naming one of those three commands. There are no implicit
subject, edition, environment, or storage selections.

```text
command definition ───────────────→ pipeline, roles, default profiles
subject manifest + language edition → identity, source, split, release
locale definition ────────────────→ metadata defaults
storage profile → environment stores → source/destination locations
selected execution profiles ──────→ proofreading or chunking settings
                         ↓
                validated assembled job
                         ↓
          config resolve (inspect) / command (execute)
```

The manifest ID is a lookup key, not the subject code: `--subject
sub123_spand_rahasya` loads `jobs/subjects/sub123_spand_rahasya/manifest.json`,
whose `identity.subject_code` is `SUB123`. `--language hi-IN` selects its
`editions.hi-IN`; the edition must exist. Only `hi-IN` and `mr-IN` are supported.

| Setting to change | Representative resource | Owning schema |
| --- | --- | --- |
| Subject identity, artifact root, edition source DOCX, release version, chapter split, profile overrides | [Subject manifest](../../jobs/subjects/sub123_spand_rahasya/manifest.json) | [Subject manifest](../../config/job-components/schemas/subject_manifest.schema.json) |
| Locale metadata defaults (script, encoding, summary markers) | [Hindi locale](../../config/job-components/locales/hi-IN.json) | [Locale definition](../../config/job-components/schemas/locale_definition.schema.json) |
| Pipeline, source/destination roles, naming fields, profile defaults | [Preparation command](../../config/job-components/commands/prep-subject.json) | [Command definition](../../config/job-components/schemas/command_definition.schema.json) |
| Named local/R2 stores, library-root bindings, bucket and prefixes | [Development environment](../../config/job-components/environments/development.json) | [Environment](../../config/job-components/schemas/environment.schema.json) |
| Which store serves each command role | [R2-output storage profile](../../config/job-components/storage-profiles/r2-output.json) | [Storage profile](../../config/job-components/schemas/storage_profile.schema.json) |
| Complete proofreading settings | [Default proofreading profile](../../config/job-components/profiles/proofreading/gemini-3.6-flash-v1.json) | [Proofreading profile](../../config/job-components/schemas/proofreading_profile.schema.json) |
| Complete chunking/model settings | [Chunking profile](../../config/job-components/profiles/chunking/bge-m3-semantic-window-v1.json) | [Chunking profile](../../config/job-components/schemas/chunking_profile.schema.json) |

Profiles are selected in increasing precedence: **command → manifest → edition
→ invocation**. Manifest and edition `profile_overrides` map `proofreading` or
`chunking` to a complete profile ID. A later selection replaces the entire
profile; fields are never deep-merged. Only profiles applicable to the command
are loaded.

Invocation overrides are limited to `--proofreading-profile` for `prep-subject`,
`--chunking-profile` and `--chapters` for `generate-chunks`. `generate-docx` has
no execution profile. There are no scalar model, path, bucket, split, or release
version overrides. Execution flags `--overwrite` and preparation's `--resume`
control the workflow, not composition. Lab proofreading uses its
[command default](../../config/job-components/commands/lab-proofread.json) or
`--proofreading-profile`, without a subject manifest. See the
[optional larger-input profile](command-reference.md#optional-larger-input-proofreading)
and [source-font policy](legacy-docx-conversion.md#source-font-safety-boundary).

## Storage and library roots

An environment defines stores; a storage profile routes command roles to those
stores. Docker is a runtime, not an environment selector. The only maintained
environment, `development`, currently uses R2 bucket `gurubodh-library-dev`,
with `source_library` and `cms_library` prefixes. Selecting Docker or `r2` does
not select a production environment.

| Storage profile | `prep-subject` source → destination | Chunks/DOCX source → destination | Required library-root variables |
| --- | --- | --- | --- |
| [`local`](../../config/job-components/storage-profiles/local.json) | Local source library → local CMS library | Local CMS library → local CMS library | Prep: both; downstream: CMS only |
| [`r2-output`](../../config/job-components/storage-profiles/r2-output.json) | Local source library → R2 CMS prefix | Local CMS library → R2 CMS prefix | Prep: source only; downstream: CMS only |
| [`r2`](../../config/job-components/storage-profiles/r2.json) | R2 source prefix → R2 CMS prefix | R2 CMS prefix → R2 CMS prefix | Neither |

The variables are `GURUBODH_SOURCE_LIBRARY_ROOT` and
`GURUBODH_CMS_LIBRARY_ROOT`. Each used variable must contain a nonempty absolute
path, without embedded variable interpolation. Only roots used by the selected
command route are required, including during inspection. Composition does not
create or check those directories. Credentials and `GURUBODH_MODEL_CACHE_DIR`
are separate runtime requirements: see [Environment setup](../environment-setup.md).

In particular, `r2-output` reads downstream canonical artifacts **locally**;
it does not read back the R2 artifacts produced by an earlier preparation run.

For `sub123_spand_rahasya` / `hi-IN`, the manifest's source relative path is
`123_spand_rahasya/unicode_fonts/ms_word/sub123_spand_rahasya_hi-IN.docx`.
Local preparation joins it to the source library root; R2 preparation prepends
`source_library/` as the object key. Artifact locations use
`artifact_root/language`, here `123_spand_rahasya/hi-IN`, below the local CMS
root or R2 `cms_library/` prefix. Derived commands read the same subject path
from their routed source store. See [Artifact lifecycle](../concepts/artifact-lifecycle.md)
for paths within that release.

## Project and resource discovery

Project-root precedence is `--project-root`, then `GURUBODH_CLI_ROOT`, then an
upward search from the working directory. A project root needs `jobs/subjects/`;
no schema file is a discovery marker. An invalid explicit or environment root
fails instead of falling back. From the monorepo root, pass
`--project-root tools/gurubodh-cli`, or change into that directory first.

Manifests always come from the selected project. If its
`config/job-components/` directory exists, all reusable components come from
that catalog; a missing entry fails rather than falling back per file. Otherwise
they come from the CLI's bundled catalog. Schemas, the converter, and the font
policy remain package-owned resources, resolved relative to the source package
in a checkout or through installed distribution metadata. A project catalog
cannot override the source-font policy.

Code entry points: [project selection](../../gurubodh/project.py),
[catalog loading](../../gurubodh/job_components.py),
[field assembly and profile selection](../../gurubodh/job_composition.py),
[bundled resources](../../gurubodh/resource_discovery.py), and
[schema validation](../../gurubodh/schema_validation.py). The
[reference index](README.md) distinguishes component, assembled-job, and artifact
schemas.
