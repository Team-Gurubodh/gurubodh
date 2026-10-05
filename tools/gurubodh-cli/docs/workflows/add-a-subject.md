# Add a subject or language edition

Prerequisites: an assigned subject/category identity, supplied DOCX with supported
fonts, and a local CLI installation. Changes to a maintained manifest follow the
repository's [issue-first workflow](../../../../docs/development/github-workflow.md).
This recipe describes edits to make for your own subject; it does not onboard one.

## Edit and inspect

Use the bilingual [Spand Rahasya manifest](../../jobs/subjects/sub123_spand_rahasya/manifest.json)
as a structural example. For a new subject, copy it to
`jobs/subjects/<your-manifest-id>/manifest.json`, then edit the following fields.
For an additional edition, edit only the applicable edition in the existing
manifest. See [configuration ownership and schema links](../reference/configuration.md#selectors-and-ownership)
for field authority.

| Field | Operator choice |
| --- | --- |
| `manifest_id`, `identity` | Match the directory ID; use the assigned `CATnnn`/`SUBnnn` codes and title slug, not the example's identity |
| `artifact_root` | A safe source-independent relative subject path; composition adds the language directory |
| `editions` | Keep only supplied `hi-IN`/`mr-IN` editions; adding an edition needs that language's source material |
| `release.version`, `release.subversion` | Two-digit strings for the intended release, such as `"01"`; inspect resulting filenames |
| `source_document.relative_path` | DOCX path relative to the source library, with no absolute root or environment variables |
| `source_document.font_encoding`, `file_format` | `unicode` or supported `aps`, and `docx`; select the actual source encoding, not desired output encoding |
| `chapter_split` | Adapt the example's regex to actual chapter boundaries; regex requires `flags` (possibly `[]`). For a single chapter use only `{"enabled": false}` |

Do not keep the example's January 2026 heading pattern for unrelated material.
The [font policy](../reference/legacy-docx-conversion.md#source-font-safety-boundary)
still applies; manifest editing cannot make unsupported fonts valid. Locale
components supply UTF-8 canonical output settings.

Set the library roots through [Getting started](../getting-started.md). Replace
the illustrative ID below with your edited manifest's ID:

```bash
export GURUBODH_RECIPE_SUBJECT=your_manifest_id
gurubodh config resolve --command prep-subject \
  --subject "$GURUBODH_RECIPE_SUBJECT" --language hi-IN \
  --environment development --storage-profile local --provenance
```

For Marathi, select `mr-IN` and inspect that edition independently. Require exit
zero and review identity, source/destination paths, release naming, split, and
profile provenance. A rejected ID, edition, path, or component must be corrected
before execution. Resolution does not verify real chapter boundaries or fonts.

## Automated validation and testing responsibilities

Adding a valid subject or supported language edition using existing capabilities
requires configuration changes and maintainer testing. Automated test code,
synthetic fixtures, subject inventories, and CI configuration do not need an entry
for the addition. Supported languages and capabilities follow the
[configuration contract](../reference/configuration.md); new software
capabilities may require code and test changes.

From `tools/gurubodh-cli`, after the Python 3.12
[installation setup](../environment-setup.md#local-development-runtime), run:

```sh
.venv/bin/python -m unittest discover -s tests -p test_configuration_catalog.py -v
.venv/bin/python -m unittest discover -s tests -v
```

| Check | Responsibility |
| --- | --- |
| Automatic catalog validation | Discovers committed subject manifests, reusable components, and shared policies without fixed resource lists or counts. Applies real structural and semantic rules, including regex compilation and policy relationships. Validates unused components and every declared locale and command-default, manifest-level, and edition-level profile reference, including references hidden by overrides. |
| Storage references | Each storage role's store name must appear in at least one validated environment. This does not establish compatibility of every environment/storage-profile pair; maintainers inspect and test their selected combinations. |
| Shared behavior tests | Independent synthetic catalogs, jobs, and text cover all three commands, routing, profile precedence, output contracts, interruption/resume, overwrite, and failure behavior. Cases follow supported software behavior rather than the maintained subject inventory. |
| Installed/configured-value checks in CI | Verify shipped resource ownership and packaging, and correct use of current selected settings, without fixing configurable subject/profile values to historical expectations. |

A new valid manifest and supported edition are discovered automatically. A missing
manifest-level profile fails catalog validation even if an edition selects a
valid replacement. Runtime resolution loads only applicable selected components;
the repository catalog check separately validates every committed declaration.
Correct invalid configuration and rerun the check before subject execution.

Catalog validation does not execute maintained subject pipelines, bind library
roots, or verify real source files, fonts, credentials, model caches, chapter
boundaries, or content quality. A syntactically valid chapter regex can still
split the supplied document incorrectly; review actual source and output.

Shared automated checks use synthetic content and fake external collaborators.
They require no maintained source documents, live credentials or services, or
model-weight downloads. Installation and image builds may require dependency
downloads. Actual subject execution uses the prerequisites in
[Environment setup](../environment-setup.md) and the existing workflow guides.

## Execute and verify

Maintainers own subject-specific execution and content/output acceptance for
each added subject or edition. Inspect every applicable command with the selected
environment, storage profile, and processing profiles, then run preparation and
the required derivations on the supplied material.

With the source at the inspected path and Gemini credentials ready:

```bash
gurubodh prep-subject \
  --subject "$GURUBODH_RECIPE_SUBJECT" --language hi-IN \
  --environment development --storage-profile local
```

Follow [local release verification and derivation](../getting-started.md#prepare-and-verify)
using your inspected artifact root and language, repeating for each added edition.
Check chapter boundaries, count, titles, and canonical text against the supplied
document before deriving outputs. Follow [Generate chunks](generate-chunks.md)
and [Generate DOCX exports](generate-docx.md) for the outputs the subject requires;
accept their content, readiness and canonical-source binding, and audit outcomes.
If a split, source, or output-affecting setting was wrong, correct it and use the deliberate
[replacement procedure](prepare-a-subject.md#resume-and-replacement);
`--resume` cannot accept a changed preparation contract.
