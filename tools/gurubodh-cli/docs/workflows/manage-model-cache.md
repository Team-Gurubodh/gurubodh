# Manage the pinned model

`gurubodh models prepare` and `gurubodh models verify` make BGE-M3 cache readiness
an explicit operation. They resolve the normal validated chunking profile and its
full immutable model revision; they do not accept a model name or revision override.
Initial support is limited to the maintained BGE-M3 SentenceTransformer runtime.

With the maintained profile, both commands use its explicit CPU selection and report
`Embedding device: cpu` before the offline embedding check. See
[Intentional CPU execution](../environment-setup.md#intentional-cpu-execution)
for GPU support status, system RAM requirements, and existing project-local profiles.

`gurubodh models check-updates` resolves that same profile and compares its pin with
upstream repository metadata. It is advisory only: it does not change the profile,
prepare or alter the runtime cache, certify compatibility, or upgrade the model.

## Check the upstream revision

Run the check with network access; no cache variable or downloaded model is required:

```bash
gurubodh models check-updates --profile bge-m3-semantic-window-v1
```

The report identifies the profile and model; gives the pinned and upstream commit IDs
and dates plus the check time; and reports either `current` or `update available` only
after establishing their order from upstream history. For a newer commit, it separates
changes to required weights, tokenizer files, and runtime configuration from
documentation/metadata and other non-runtime artifacts. It also links the model card
and relevant commits and reports upstream architecture, embedding dimensions,
context/token limit, license, and required-runtime byte size when exposed. Unavailable
details are identified instead of inferred. A final `Conclusion` block groups the
status, change summary, and advisory caveat after those details.

The check reads repository metadata and downloads at most the small configuration
files needed for those details into temporary storage. It never downloads weights,
initializes the embedding runtime, or writes the selected model cache. A newer commit
does not by itself mean a newly trained or better model, or one validated as compatible
with Gurubodh; in particular, a model-card-only commit is reported as
documentation/metadata-only rather than as a new model release.

Exit behavior is intended for manual or scripted checks:

- `current`: exit zero.
- `update available`: exit zero; operator assessment is still required.
- `unable to check` / `unable to determine`: nonzero. Missing pins, missing or
  divergent history, and authentication, network, or API failures use this result and
  never claim the pin is current.

## Prepare or repair a local cache

Set the same cache root used by chunk generation, then run preparation with network
access:

```bash
export GURUBODH_MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
gurubodh models prepare --profile bge-m3-semantic-window-v1
```

Before artifact content is downloaded, the command reports the model, exact commit
revision, embedding device, selected runtime files, total required artifact bytes,
and remaining bytes after valid cached content is counted. Sizes and digests come from that selected
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
