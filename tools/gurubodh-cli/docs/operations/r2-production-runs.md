# R2 production runs

Docker is the supported runner for production R2-to-R2 batch jobs. Native Python is for development and debugging. Use the published CPU-only image `ghcr.io/team-gurubodh/gurubodh-cli` pinned to an immutable digest or `sha-<full-git-sha>` tag—never a mutable reference.

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

## Before a production run

Complete [Environment setup](../environment-setup.md) for R2 credentials, Gemini scope, named-volume creation, `HF_HUB_OFFLINE=1`, and secret-handling rules. Use a maintained `.r2.json` job and an immutable image reference.

`prep-subject` has one writer per destination. Its R2 advisory lease is only a guardrail and does not provide reliable distributed mutual exclusion. Do not overlap runners for the same subject and locale: they can duplicate Gemini requests and overwrite checkpoint/workspace artifacts.

## Bootstrap the model cache

Only R2 chunk generation needs the BGE-M3 cache. After creating `gurubodh-bge-m3-cache` as described in [Environment setup](../environment-setup.md), prepare or repair it explicitly using the exact snapshot required by maintained jobs:

Prepare or repair the named volume explicitly using the exact snapshot required by maintained jobs:

```bash
docker run --rm \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  --entrypoint hf \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  download BAAI/bge-m3 1_Pooling/config.json config.json \
  config_sentence_transformers.json modules.json pytorch_model.bin \
  sentence_bert_config.json sentencepiece.bpe.model special_tokens_map.json \
  tokenizer.json tokenizer_config.json \
  --revision 5617a9f61b028005a4858fdac845db406aefb181 \
  --cache-dir /var/cache/gurubodh/models
```

Maintained chunk jobs use `local_files_only: true`. Supply the same volume and `HF_HUB_OFFLINE=1` to `generate-chunks`; they do not download or repair the cache. A bind mount may be used for an existing compatible host cache, but do not bind-mount a checkout over `/opt/gurubodh-cli` in production because that defeats baked-image audit identity.

## Run maintained jobs

```bash
docker run --rm --env PYTHONUNBUFFERED=1 --env GEMINI_API_KEY \
  --env CLOUDFLARE_R2_ACCOUNT_ID --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  prep-subject --config jobs/subjects/sub039_aacharan_shastra/hi-IN/prep-subject.r2.json
```

Run the matching chunk-generation job with the pre-provisioned cache:

```bash
docker run --rm --env PYTHONUNBUFFERED=1 --env HF_HUB_OFFLINE=1 \
  --env CLOUDFLARE_R2_ACCOUNT_ID --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  generate-chunks --config jobs/subjects/sub039_aacharan_shastra/hi-IN/generate-chunks.r2.json
```

Generate DOCX exports after preparation when they are needed:

```bash
docker run --rm \
  --env CLOUDFLARE_R2_ACCOUNT_ID --env CLOUDFLARE_R2_ACCESS_KEY_ID \
  --env CLOUDFLARE_R2_SECRET_ACCESS_KEY \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  generate-docx --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.r2.json
```

DOCX generation needs R2 credentials but neither Gemini nor model cache. All commands download inputs to temporary container storage and upload their owned outputs to R2.

## Derived-output readiness and failed retries

`generate-chunks` and `generate-docx` share one staged lifecycle. Both validate all staged objects and revalidate the canonical source before R2 publication begins. Their readiness markers are `semantic_chunks_manifest.json` and `docx_manifest.json` respectively.

An overwrite removes the old command readiness manifest first, replaces only the command-owned prefix, uploads the validated readiness manifest last, and publishes non-readiness success audits afterward. If an artifact upload fails, the command attempts to remove the readiness manifest and upload a failure audit under `run_reports/<command>/`. Treat a prefix without its readiness manifest as incomplete and rerun with `--overwrite` only after reviewing the failure audit.

This multi-object sequence is not atomic: readers may observe object deletion or replacement while an overwrite is in progress, and concurrent writers are unsupported. A versioned-release/current-pointer protocol is not implemented. Schedule one derived writer per command, subject, and locale, and rely on the readiness marker—not prefix contents alone—before consumption.

Audit reports identify the baked source revision and provenance source. After a maintained configuration change, build and publish a new image, then use its new immutable tag or digest. Review [Artifact lifecycle](../concepts/artifact-lifecycle.md) and the relevant workflow before any `--overwrite` retry.
