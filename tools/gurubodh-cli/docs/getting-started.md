# Getting started with Gurubodh CLI

Use this local inspect → prepare → derive → verify recipe with source material
supplied by your content maintainer. The checkout includes manifests, not the
subject DOCX library.

## Prerequisites

Complete [Environment setup](environment-setup.md), then from the monorepo root:

```bash
make cli-venv
. tools/gurubodh-cli/.venv/bin/activate
make cli-install
cd tools/gurubodh-cli
gurubodh --help
export GURUBODH_SOURCE_LIBRARY_ROOT="$HOME/gurubodh-libraries/source_library"
export GURUBODH_CMS_LIBRARY_ROOT="$HOME/gurubodh-libraries/cms_library"
mkdir -p "$GURUBODH_CMS_LIBRARY_ROOT"
```

Choose absolute roots appropriate to your machine; use an empty CMS destination
for a first run. Place the supplied Hindi Unicode DOCX at the relative path in the
[maintained manifest](../jobs/subjects/sub123_spand_rahasya/manifest.json).
Check that the file is readable:

```bash
test -r "$GURUBODH_SOURCE_LIBRARY_ROOT/123_spand_rahasya/unicode_fonts/ms_word/sub123_spand_rahasya_hi-IN.docx"
```

A nonzero result means fix the file placement before continuing. Obtain Gemini
credentials through [Environment setup](environment-setup.md#credentials-and-secret-handling).
Review the [approved source fonts](reference/legacy-docx-conversion.md#source-font-safety-boundary);
file readability alone does not establish font support.

## Inspect

```bash
gurubodh config resolve --command prep-subject \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local --provenance \
  > /tmp/gurubodh-prep.json 2> /tmp/gurubodh-prep-provenance.json
cat /tmp/gurubodh-prep.json /tmp/gurubodh-prep-provenance.json
```

On exit zero, check the source path, destination, chapter split, release naming,
and complete selected proofreading profile. The JSON streams and their limits
are defined in [configuration inspection](reference/command-reference.md#config-resolve):
this does not check actual files, credentials, fonts, or cache readiness. If it
fails, read stderr and correct selectors/components or library roots first.

## Prepare and verify

```bash
gurubodh prep-subject \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local
export GURUBODH_RECIPE_RELEASE="$GURUBODH_CMS_LIBRARY_ROOT/123_spand_rahasya/hi-IN"
cat "$GURUBODH_RECIPE_RELEASE/run_state/prep-subject/job-state.json"
cat "$GURUBODH_RECIPE_RELEASE/chapters/chapter_content_manifest.json"
ls "$GURUBODH_RECIPE_RELEASE/run_reports/prep-subject"
```

Continue only after a `succeeded` outcome and publication readiness. Read the
printed audit report and confirm the state is succeeded and bound to the current
manifest; review chapter titles, count, and canonical text. File presence alone
is insufficient. [Recovery](operations/recovery.md) covers failed/incomplete
runs and existing destinations; do not add `--overwrite` just to bypass an error.

## Derive matching outputs

Provision the pinned [model cache](environment-setup.md#bge-m3-model-cache)
before chunk execution. DOCX generation needs no model cache or provider key.
Use the same subject, language, environment, and local route:

```bash
for command in generate-chunks generate-docx; do
  gurubodh config resolve --command "$command" \
    --subject sub123_spand_rahasya --language hi-IN \
    --environment development --storage-profile local --provenance || break
done
gurubodh generate-chunks \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local
gurubodh generate-docx \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile local
cat "$GURUBODH_RECIPE_RELEASE/chapters/semantic_chunks/semantic_chunks_manifest.json"
cat "$GURUBODH_RECIPE_RELEASE/chapters/msword/docx_manifest.json"
```

Inspect both configurations successfully before executing. Each derivation must
report success and a ready output set. Check the manifest's chapter coverage and
source binding, the printed JSON/Markdown audit, and a representative chunk or
DOCX. See [chunk selection and replacement](workflows/generate-chunks.md) and
[DOCX regeneration](workflows/generate-docx.md) before rerunning.

## Next recipes

- [Add a subject or edition](workflows/add-a-subject.md).
- [Choose a storage route and run Docker/R2](operations/r2-production-runs.md).
- [Local lab tools and tokenizer comparison](workflows/local-tools.md).
- From another working directory, use `--project-root /path/to/gurubodh/tools/gurubodh-cli`;
  see [project discovery](reference/configuration.md#project-and-resource-discovery).
