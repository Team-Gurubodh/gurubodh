# Docker and R2 operations

Docker is the supported runner for production R2-to-R2 batch jobs. Native Python is for development and debugging. Use the published CPU-only image `ghcr.io/team-gurubodh/gurubodh-cli` pinned to an immutable digest or `sha-<full-git-sha>` tag—never a mutable reference.

The examples below explicitly select `development`. See [environment and storage
routing](../reference/configuration.md#storage-and-library-roots) for its bucket
and why Docker/R2 does not select a production environment.

## Choose a route

Use the [authoritative routing table](../reference/configuration.md#storage-and-library-roots)
for exact stores and required root variables. All examples here use the maintained
`development` environment and its `gurubodh-library-dev` bucket; no maintained
staging or production environment is implied.

| Intended operation | Route | Prerequisite input | Destination |
| --- | --- | --- | --- |
| Prepare and derive on disk | `local` | Local source DOCX for prep; completed local canonical release for derivations | Local CMS library |
| Publish from local inputs | `r2-output` | Local source DOCX for prep; **completed local canonical release** for derivations | R2 `cms_library/` |
| Prepare and derive within R2 | `r2` | R2 `source_library/` DOCX for prep; completed R2 canonical release for derivations | R2 `cms_library/` |

For a native development/debugging `r2-output` preparation, set the source root,
Gemini key, and all three R2 variables through [Environment setup](../environment-setup.md),
then inspect and execute:

```bash
gurubodh config resolve --command prep-subject \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile r2-output --provenance
gurubodh prep-subject \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile r2-output
```

This reads the [Spand Rahasya source path](../reference/configuration.md#storage-and-library-roots)
below `GURUBODH_SOURCE_LIBRARY_ROOT` and publishes under
`gurubodh-library-dev/cms_library/123_spand_rahasya/hi-IN/`. Verify the outcome,
state, manifest, and reports at that destination as described below.

To publish DOCX from an independently completed **local** release, set
`GURUBODH_CMS_LIBRARY_ROOT` and the R2 variables, then:

```bash
gurubodh config resolve --command generate-docx \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile r2-output --provenance
gurubodh generate-docx \
  --subject sub123_spand_rahasya --language hi-IN \
  --environment development --storage-profile r2-output
```

Verify the R2 DOCX readiness manifest and audit. `generate-chunks` uses the same
route with the additional pinned model-cache prerequisite. The preceding
`r2-output` prep creates no local canonical release: use `r2` for derivations
from that R2 result, or first complete the [local workflow](../getting-started.md).
For existing output/failure, use [recovery](recovery.md) before adding overwrite.

## Select and inspect an immutable image

Replace the placeholder with the full SHA tag of a successfully published image,
or use its immutable `@sha256:...` digest:

```bash
export GURUBODH_CLI_IMAGE='ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha>'
docker pull "$GURUBODH_CLI_IMAGE"
docker image inspect "$GURUBODH_CLI_IMAGE" --format '{{json .RepoDigests}}'
docker run --rm "$GURUBODH_CLI_IMAGE" config resolve --command prep-subject \
  --subject sub039_aacharan_shastra --language hi-IN \
  --environment development --storage-profile r2 --provenance
```

Inspect source object key, bucket, destination prefix, release, and profile
provenance. Repeat inspection with `--command generate-chunks` and
`--command generate-docx` for their source/destination and model selections.
Resolution requires no credentials and cannot prove object access, source fonts,
provider availability, or downloaded cache readiness. A pull/inspection failure
must be corrected before running the commands below.

## Build and inspect locally

From the monorepo root:

```bash
docker build --build-arg SOURCE_REVISION="$(git rev-parse HEAD)" \
  --build-arg IMAGE_VERSION=local \
  --build-arg IMAGE_CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t gurubodh-cli:local tools/gurubodh-cli
docker run --rm gurubodh-cli:local --help
docker run --rm --entrypoint node gurubodh-cli:local --version
```

The image runs as a non-root user and contains Python 3.12, Node for the APS converter, no credentials, no content artifacts, and no BGE-M3 weights. `/work` is temporary; `/var/cache/gurubodh/models` is the model cache path.

## Automated image verification

The container workflow checks wheels and source distributions, then builds and
tests both `linux/amd64` and `linux/arm64` on native runners. Publication waits for
both architectures and the distribution check. It transfers the tested images
to the publish job and assembles their multi-platform manifest without rebuilding.

Alongside the full CLI unit suite and configuration/maintained-selector checks,
the installed-runtime gate runs as the normal non-root user, from `/work`, with
network access disabled and a read-only container filesystem. Only `/tmp` is
writable; tests and synthetic fixtures are mounted separately from application
code. Python isolated mode and install-origin assertions prevent checkout
imports from masking missing installed resources.

The gate checks the installed APS vendor mapping against its pinned hash and
nonempty golden cases, executes APS/Hindi and Unicode/Marathi preparation, then
generates semantic chunks and Word exports from the resulting canonical release.
It verifies text preservation, checkpoint completion, lab proofreading, lab DOCX
assembly/append, tokenizer output, overwrite rejection, and installed CLI help entry points.
The image build itself also requires a real installed APS conversion to pass.

Gemini SDK responses and model/tokenizer loading use deterministic test substitutes;
the pipelines, conversion, schemas, semantic chunker and artifact writers remain
real. R2 routing and failure/lifecycle behavior have offline unit coverage.
These checks do not validate live Gemini/Sarvam availability, R2 permissions,
downloaded BGE-M3 weights, or every source document's font mappings. Credentials,
model-cache setup and supported source fonts remain runtime requirements.

To run the installed-runtime gate against a local build from the monorepo root:

```bash
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,mode=1777 \
  --volume "$PWD/tools/gurubodh-cli/tests:/checks/tests:ro" \
  --entrypoint python gurubodh-cli:local \
  -I -B /checks/tests/check_installed_runtime.py
```

## Before a production run

Complete [Environment setup](../environment-setup.md) for R2 credentials, Gemini scope, named-volume creation, `HF_HUB_OFFLINE=1`, and secret-handling rules. Use a maintained subject with the `r2` storage profile and an immutable image reference.

`prep-subject` has one writer per destination. Its R2 advisory lease is only a guardrail and does not provide reliable distributed mutual exclusion. Do not overlap runners for the same subject and locale: they can duplicate Gemini requests and overwrite checkpoint/workspace artifacts.

## Bootstrap the model cache

Among the canonical commands, only chunk generation needs the BGE-M3 cache, for both local and R2 routes. After creating `gurubodh-bge-m3-cache` as described in [Environment setup](../environment-setup.md), prepare or repair the exact allowlisted files selected by the maintained profile. Do not set `HF_HUB_OFFLINE=1` on this networked preparation invocation:

```bash
docker run --rm \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  "$GURUBODH_CLI_IMAGE" \
  models prepare --profile bge-m3-semantic-window-v1

docker run --rm \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  --env HF_HUB_OFFLINE=1 \
  "$GURUBODH_CLI_IMAGE" \
  models verify --profile bge-m3-semantic-window-v1
```

Preparation prints the exact model, immutable revision, selected files, revision-derived
artifact bytes, and remaining download bytes before it transfers artifact content.
It downloads or repairs only those files and succeeds only after the same offline
runtime check used by `models verify`. Repeating successful preparation performs no
artifact download, although it still reads upstream metadata to validate the pinned contract.

Maintained chunk jobs use `local_files_only: true`. Supply the same volume and `HF_HUB_OFFLINE=1` to `generate-chunks`; they do not download or repair the cache. A bind mount may be used for an existing compatible host cache, but do not bind-mount a checkout over `/opt/gurubodh-cli` in production because that defeats baked-image audit identity. See [Manage the model cache](../workflows/manage-model-cache.md) for integrity failures and repair behavior.

## Mount guidance

Pure `r2` preparation and DOCX derivation need no library bind mounts. The image
sets `GURUBODH_MODEL_CACHE_DIR=/var/cache/gurubodh/models`; chunking needs the
populated cache volume shown above. Verify the bootstrap command succeeds and
use that same volume for execution; cached-only model initialization is the
actual readiness check, not volume existence.

For a container `local` or `r2-output` route, bind each used local library at an
absolute container path and pass that path as the corresponding root variable.
For example, add these Docker arguments for a local source:

```bash
--mount "type=bind,src=$GURUBODH_SOURCE_LIBRARY_ROOT,dst=/libraries/source,readonly" \
--env GURUBODH_SOURCE_LIBRARY_ROOT=/libraries/source
```

For a local CMS destination use a writable bind and
`--env GURUBODH_CMS_LIBRARY_ROOT=/libraries/cms`; for downstream `r2-output`,
the local CMS input can be mounted read-only at that path. Host directories must
exist and allow access by the image's non-root user. A custom manifest project
can be mounted read-only at `/project` and selected with `--project-root /project`;
follow [resource discovery](../reference/configuration.md#project-and-resource-discovery)
and keep the installed runtime intact. Correct mount/path permissions before
retrying; do not replace image-owned application files to fix input access.

## Run maintained jobs

Add `-t` to `docker run` when an operator is watching an interactive run and
wants terminal color detection, for example `docker run --rm -t ...`. Without
`-t`, redirected output, and whenever `NO_COLOR` is set, the CLI emits the same
explicit outcomes as plain text. Color is limited to the whole-command outcome
line and immediate failures; counts and locations remain uncolored.

```bash
docker run --rm --env PYTHONUNBUFFERED=1 --env GEMINI_API_KEY \
  --env CLOUDFLARE_R2_ACCOUNT_ID --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  "$GURUBODH_CLI_IMAGE" \
  prep-subject --subject sub039_aacharan_shastra --language hi-IN --environment development --storage-profile r2
```

During final R2 publication, `prep-subject` reports the destination and chapter/file
counts, then prints a line after all five files for each chapter upload successfully.
For example, a three-chapter run includes the following line, with the actual
chapter filename stem in place of the placeholder:

```text
  [01/03] <chapter-filename-stem> (canonical text, canonical metadata, unmodified source, diff, proofreading details)
```

These lines describe final publication after proofreading. The content manifest
uploads last; the final outcome then distinguishes proofreading results, Gemini
request completion, checkpoint upload operations, canonical-publication upload
operations, and final publication readiness.
A failed chapter upload produces no success line for that chapter. A resumed job
that publishes its retained workspace reports the chapters again; resuming an
already-complete job does not publish them again.

Run the matching chunk-generation job with the pre-provisioned cache:

```bash
docker run --rm --env PYTHONUNBUFFERED=1 --env HF_HUB_OFFLINE=1 \
  --env CLOUDFLARE_R2_ACCOUNT_ID --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  "$GURUBODH_CLI_IMAGE" \
  generate-chunks --subject sub039_aacharan_shastra --language hi-IN --environment development --storage-profile r2
```

Generate DOCX exports after preparation when they are needed:

```bash
docker run --rm \
  --env CLOUDFLARE_R2_ACCOUNT_ID --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  "$GURUBODH_CLI_IMAGE" \
  generate-docx --subject sub039_aacharan_shastra --language hi-IN --environment development --storage-profile r2
```

DOCX generation needs R2 credentials but neither Gemini nor model cache. All commands download inputs to temporary container storage and upload their owned outputs to R2.

## Verify the R2 result

Require a `succeeded` outcome and publication readiness before deriving or
consuming outputs. Use your authorized R2 object browser to inspect the exact
bucket and release prefix printed by inspection/execution. For the matching
Aacharan Shastra examples this is
`gurubodh-library-dev/cms_library/39_aacharan_shastra/hi-IN/`.

Read `run_state/prep-subject/job-state.json` and
`chapters/chapter_content_manifest.json` for succeeded state bound to the
manifest. After derivation, inspect
`chapters/semantic_chunks/semantic_chunks_manifest.json` or
`chapters/msword/docx_manifest.json`, matching source bindings and chapter coverage,
and the objects they list. Read the printed JSON/Markdown audits below
`run_reports/<command>/`. Listing objects or observing completed uploads alone
is not readiness evidence. Reports are attempted remotely on failure; retain
terminal diagnostics if R2 access also prevents audit upload.

For incomplete prep, repair the cause and repeat the same container invocation
with `--resume` only when compatible. For changed preparation inputs or existing
derived output, follow [recovery decisions](recovery.md) and the rules below.

## Derived-output readiness and failed retries

`generate-chunks` and `generate-docx` share one staged lifecycle. Both validate all staged objects and revalidate the canonical source before R2 publication begins. Their readiness markers are `semantic_chunks_manifest.json` and `docx_manifest.json` respectively.

An overwrite removes the old command readiness manifest first, replaces only the command-owned prefix, uploads the validated readiness manifest last, and publishes non-readiness success audits afterward. If an artifact upload fails, the command attempts to remove the readiness manifest and upload a failure audit under `run_reports/<command>/`. Treat a prefix without its readiness manifest as incomplete and rerun with `--overwrite` only after reviewing the failure audit.

This multi-object sequence is not atomic: readers may observe object deletion or replacement while an overwrite is in progress, and concurrent writers are unsupported. A versioned-release/current-pointer protocol is not implemented. Schedule one derived writer per command, subject, and locale, and rely on the readiness marker—not prefix contents alone—before consumption.

Audit reports identify the baked source revision and provenance source. After a maintained configuration change, build and publish a new image, then use its new immutable tag or digest. Review [Artifact lifecycle](../concepts/artifact-lifecycle.md) and the relevant workflow before any `--overwrite` retry.
