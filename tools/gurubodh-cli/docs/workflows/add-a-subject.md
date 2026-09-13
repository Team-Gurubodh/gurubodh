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

## Execute and verify

With the source at the inspected path and Gemini credentials ready:

```bash
gurubodh prep-subject \
  --subject "$GURUBODH_RECIPE_SUBJECT" --language hi-IN \
  --environment development --storage-profile local
```

Follow [local release verification and derivation](../getting-started.md#prepare-and-verify)
using your inspected artifact root and language. Check the generated chapter
count/titles against the supplied document before deriving outputs. If a split,
source, or output-affecting setting was wrong, correct it and use the deliberate
[replacement procedure](prepare-a-subject.md#resume-and-replacement);
`--resume` cannot accept a changed preparation contract.
