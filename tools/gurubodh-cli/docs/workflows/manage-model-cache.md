# Manage the pinned model cache

`gurubodh models prepare` and `gurubodh models verify` make BGE-M3 cache readiness
an explicit operation. They resolve the normal validated chunking profile and its
full immutable model revision; they do not accept a model name or revision override.
Initial support is limited to the maintained BGE-M3 SentenceTransformer runtime.

## Prepare or repair a local cache

Set the same cache root used by chunk generation, then run preparation with network
access:

```bash
export GURUBODH_MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
gurubodh models prepare --profile bge-m3-semantic-window-v1
```

Before artifact content is downloaded, the command reports the model, exact commit
revision, selected runtime files, total required artifact bytes, and remaining bytes
after valid cached content is counted. Sizes and digests come from that selected
revision. The allowlist contains one compatible PyTorch weights file plus the required
SentenceTransformer pooling, configuration, and tokenizer files; alternate weights,
ONNX/OpenVINO exports, and unrelated repository content are excluded.

Valid files and blobs are reused. Missing or damaged required files are the only
artifact content downloaded, so repeating successful preparation reports zero
remaining download bytes. An interrupted or failed run can leave reusable Hub cache
content, but it does not report readiness. Rerun the same command to resume or repair.
Unrelated cache entries are not cleaned up or changed.

Do not set `HF_HUB_OFFLINE=1` for preparation. The command must read metadata for the
pinned revision even when every artifact is already cached.

## Verify without network access

After preparation, or before a cached-only chunk run, verify locally:

```bash
HF_HUB_OFFLINE=1 gurubodh models verify \
  --profile bge-m3-semantic-window-v1
```

Verification makes no network requests and performs no repair. It validates the local
revision contract, size and content digest of every required file, then loads the
pinned model through the production SentenceTransformer embedding helper and encodes
a small input with cached-only loading. Readiness is reported only after all checks
succeed.

If verification reports missing or damaged content, rerun `models prepare` with
network access and then repeat verification. If integrity succeeds but loading fails,
run preparation once to reconfirm the revision contract, then check that the installed
CLI dependencies and the profile's configured device are supported by the host.

## Container cache volume

The container uses the same commands and contract with
`GURUBODH_MODEL_CACHE_DIR=/var/cache/gurubodh/models`. Mount the persistent volume on
both preparation and verification; do not set offline mode until the verification
invocation. The exact commands are maintained in
[Docker and R2 operations](../operations/r2-production-runs.md#bootstrap-the-model-cache).
