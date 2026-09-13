# Verify an outcome and recover

Use this decision guide after an error or before a rerun. The
[artifact lifecycle](../concepts/artifact-lifecycle.md) owns readiness, publication,
report schemas, and invalidation; command guides own replacement details.

## Inspect before retrying

Read the final outcome and printed report locations. For canonical commands,
JSON and Markdown audits live under `<release>/run_reports/<command>/` at the
selected destination. Inspect `run_identity`, `processing_summary`, `publication`,
and `failure` in the JSON; use the Markdown report for a readable summary.
Configuration/early setup failures may stop before an audit exists. If report
writing/upload fails, preserve terminal diagnostics; an absent remote report
does not mean the run succeeded. Lab report paths are in the
[local-tool recipe](../workflows/local-tools.md#proofread-a-docx).

| Evidence | Decision |
| --- | --- |
| `succeeded` | Verify publication readiness and the matching manifest/output set before consumption |
| `incomplete` preparation | Inspect failed/pending chapters and checkpoint compatibility; fix the cause, then resume |
| `failed` | Identify processing, publication, or reporting failure before selecting recovery; completed provider requests are not proof of valid output |
| Files exist but readiness is absent | Treat the set as incomplete; file/prefix listings alone are not success evidence |
| Processing/publication succeeded but reporting failed | Inspect actual state and readiness before retrying; do not assume publication was rolled back |

For prep, inspect `run_state/prep-subject/job-state.json` for succeeded state bound
to the current `chapters/chapter_content_manifest.json`. A retained old manifest
during incomplete replacement is not readiness for the new job. For derivations,
inspect `chapters/semantic_chunks/semantic_chunks_manifest.json` or
`chapters/msword/docx_manifest.json`, source binding, chapter coverage, and the
files listed. Execution validates these contracts; manually checking existence
does not replace that validation.

## Choose the next action

Use the original subject, language, environment, and storage selectors unless
you intentionally want a different release or destination.

| Cause or intent | Recovery and verification |
| --- | --- |
| Invalid selector, edition, component, or library root | Fix the ID/component or set the used root to an absolute path. Repeat `config resolve --provenance` and check paths before execution; see [configuration](../reference/configuration.md) |
| Missing/unreadable source | Place the supplied DOCX at the resolved path or correct the edition; recheck readability and inspect configuration |
| Unsupported/unresolved font | Correct the source document's effective fonts or use the correct supported APS edition. Follow the [font policy](../reference/legacy-docx-conversion.md#source-font-safety-boundary); changing a label does not convert input |
| Missing pinned model/tokenizer cache | [Bootstrap/repair](../environment-setup.md#bge-m3-model-cache) the exact revision deliberately, then retry cached-only execution; inspection cannot validate weights |
| Gemini failure or invalid proofreading response | Read bounded diagnostics, check credentials/service conditions, and use [compatible prep resume](../workflows/prepare-a-subject.md#resume-and-replacement) for an incomplete checkpoint. Lab must rerun |
| Incomplete prep with unchanged source/output contract | Rerun the original `prep-subject` command with `--resume`; verify succeeded state and manifest binding afterward |
| Source, split, naming, or selected output-affecting profile changed | Inspect the changed job, then deliberately use `prep-subject --overwrite`; incompatible checkpoints cannot resume |
| Existing or intentionally replaced canonical output | Follow [prep replacement](../workflows/prepare-a-subject.md#resume-and-replacement). Successful overwrite, including completion through resume, invalidates same-locale chunks and DOCX; regenerate both as needed |
| Derived output exists or needs regeneration | Rerun `generate-chunks` or `generate-docx` with `--overwrite` after checking canonical readiness; neither supports resume. Review [chunk selection](../workflows/generate-chunks.md#select-chapters-and-a-complete-profile) before replacing a set |
| R2 permission/network or publication failure | Fix credentials/access to the inspected bucket/prefix, review publication progress/readiness in the audit, then resume compatible incomplete prep or overwrite/rerun the affected derivation. See [R2 recovery](r2-production-runs.md#derived-output-readiness-and-failed-retries) |

`--resume` and `--overwrite` cannot be combined. Resume retains successful work
and the original replacement authorization; it does not grant new permission to
replace outputs. An already succeeded prep job has no incomplete work to resume.
A failed local derived run before publication preserves a prior ready set; a
failed R2 replacement may leave partial objects without a readiness marker.
Verify the current result after every retry and keep one writer per destination
as required by the [lifecycle contract](../concepts/artifact-lifecycle.md).
