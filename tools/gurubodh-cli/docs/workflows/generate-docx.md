# Generate DOCX exports

`gurubodh generate-docx` creates a validated Word document for each canonical proofread chapter. These exports are human-readable and rebuildable; canonical `.txt` files remain authoritative and DOCX is never chunking input.

## Run a local job

```bash
gurubodh generate-docx \
  --config jobs/subjects/sub123_spand_rahasya/hi-IN/generate-docx.local.json
```

The command requires the current `prep-subject` state to be `succeeded` and bound to the exact chapter manifest it reads. It validates every listed metadata/text pair, produces one DOCX per chapter in a unique staged workspace, validates the complete package, and revalidates the source release immediately before publishing:

```text
<subject-group>/<language>/chapters/msword/
  <canonical-versioned-chapter-stem>.docx
  docx_manifest.json
<subject-group>/<language>/run_reports/generate-docx/
```

`docx_manifest.json` is the readiness marker. It binds each output to its source manifest, canonical content identity, text checksum, title/formatting contract, and DOCX checksum.

## Replacement behavior

Without `--overwrite`, an existing `chapters/msword/` directory fails preflight without modification. A local overwrite preserves the prior ready set through generation, staged validation, and source revalidation, then uses a same-directory incoming/backup swap with recovery if the swap fails. Only `chapters/msword/` is replaced.

For R2, the old readiness manifest is removed first, validated DOCX objects upload, and `docx_manifest.json` publishes last; a failed partial replacement has no readiness manifest. This is a readiness protocol, not an atomic multi-object replacement. JSON and Markdown success/failure audits record the active lifecycle state, per-chapter progress, and the actual publication result; R2 failure reports upload when possible.

`generate-docx` does not alter canonical artifacts or semantic chunks. A successful `prep-subject --overwrite` does invalidate its DOCX exports, so run this command again when a new reviewable set is needed. See [Artifact lifecycle](../concepts/artifact-lifecycle.md) for the cross-command contract.

## Controlled local assembly

Use the non-canonical [Lab tools](lab-tools.md) only to combine controlled exports. They do not replace this workflow or make a combined document canonical.
