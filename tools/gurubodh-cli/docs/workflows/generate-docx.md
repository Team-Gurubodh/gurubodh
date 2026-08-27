# Generate DOCX exports

`gurubodh generate-docx` creates a validated Word document for each canonical proofread chapter. These exports are human-readable and rebuildable; canonical `.txt` files remain authoritative and DOCX is never chunking input.

## Run a local job

```bash
gurubodh generate-docx \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.local.json
```

The command requires the current `prep-subject` state to be `succeeded` and bound to the exact chapter manifest it reads. It validates every listed metadata/text pair, produces one DOCX per chapter, and publishes:

```text
<subject-group>/<language>/chapters/msword/
  <canonical-versioned-chapter-stem>.docx
  docx_manifest.json
<subject-group>/<language>/run_reports/generate-docx/
```

`docx_manifest.json` is the readiness marker. It binds each output to its source manifest, canonical content identity, text checksum, title/formatting contract, and DOCX checksum.

## Replacement behavior

Without `--overwrite`, an existing `chapters/msword/` directory fails preflight. A local overwrite stages and validates the full replacement before swapping just that directory. For R2, the readiness manifest is removed first, validated objects upload, and the manifest publishes last; a partial prefix is not ready.

`generate-docx` does not alter canonical artifacts or semantic chunks. A successful `prep-subject --overwrite` does invalidate its DOCX exports, so run this command again when a new reviewable set is needed. See [Artifact lifecycle](../concepts/artifact-lifecycle.md) for the cross-command contract.

## Controlled local assembly

Use the non-canonical [Lab tools](lab-tools.md) only to combine controlled exports. They do not replace this workflow or make a combined document canonical.
