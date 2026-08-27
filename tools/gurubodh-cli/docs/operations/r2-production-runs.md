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

## Credentials and model cache

Export R2 credentials only in the calling environment or an untracked local environment file:

```bash
export CLOUDFLARE_R2_ACCOUNT_ID=...
export CLOUDFLARE_R2_ACCESS_KEY_ID=...
export CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
docker volume create gurubodh-bge-m3-cache
```

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
  --mount type=volume,src=gurubodh-bge-m3-cache,dst=/var/cache/gurubodh/models \
  ghcr.io/team-gurubodh/gurubodh-cli:sha-<full-git-sha> \
  prep-subject --config jobs/subjects/sub039_aacharan_shastra/hi-IN/prep-subject.r2.json
```

For chunks, add `--env HF_HUB_OFFLINE=1` and run the matching `generate-chunks.r2.json` configuration with the same model volume. DOCX generation needs R2 credentials but neither Gemini nor model cache. Commands download inputs to temporary container storage and upload their owned outputs to R2.

Audit reports identify the baked source revision and provenance source. After a maintained configuration change, build and publish a new image, then use its new immutable tag or digest. Review [Artifact lifecycle](../concepts/artifact-lifecycle.md) and the relevant workflow before any `--overwrite` retry.
