# Local lab tools and tokenizer comparison

Run from `tools/gurubodh-cli` with the installed CLI. These commands use explicit
local paths, not canonical storage selectors; their results do not publish a
canonical release. Keep lab destinations outside the CMS library.

## Proofread a DOCX

Prerequisites: a supplied local DOCX, a supported `hi-IN` or `mr-IN` locale,
[Gemini credentials and runtime](../environment-setup.md), and a separate lab
root. Read the [source-font policy](../reference/legacy-docx-conversion.md#source-font-safety-boundary);
lab detects supported Unicode/APS input and needs Node for APS conversion.

Inspect the local file and installed options, then execute (replace the source
path with your supplied document):

```bash
test -r /path/to/review.docx
gurubodh lab proofread --help
gurubodh lab proofread --source /path/to/review.docx --locale hi-IN \
  --lab-root "$HOME/gurubodh-lab" \
  --proofreading-profile gemini-3.6-flash-large-input-v1
```

The optional selector chooses the [complete larger-input profile](../reference/command-reference.md#optional-larger-input-proofreading);
omit it for the lab default. On success, follow the printed run path under
`<lab-root>/proofread/runs/active/<run-id>/`: inspect `output/` for corrected TXT
and DOCX, `report/proofreading.diff.txt`, `report/run_report.md`, and
`run_manifest.json`. Check the outcome and review the corrections. The original
DOCX is preserved. On font/provider failure, read available reports, correct the
cause, and rerun into a new run directory; lab has no `--resume`.

## Assemble controlled chapter exports

Prerequisites: a completed [DOCX derivation](generate-docx.md), direct-child
controlled Gurubodh exports, and an existing writable output directory. Use the
local release path from [Getting started](../getting-started.md):

```bash
export GURUBODH_RECIPE_RELEASE="$GURUBODH_CMS_LIBRARY_ROOT/123_spand_rahasya/hi-IN"
mkdir -p "$HOME/gurubodh-lab"
ls "$GURUBODH_RECIPE_RELEASE/chapters/msword"
gurubodh lab assemble-docx "$GURUBODH_RECIPE_RELEASE/chapters/msword" \
  "$HOME/gurubodh-lab/combined.docx"
```

Check the printed source count and open `combined.docx` to verify chapter order
and page breaks. Sources are naturally sorted by filename; temporary Word lock
files and the output itself are excluded. Only direct-child DOCX files are read.
If the destination exists, choose another name or deliberately rerun with
`--overwrite`. Invalid inputs must be repaired/regenerated first. Assembly
validates and atomically replaces its output; it writes no canonical readiness
manifest or run audit.

## Append one export to a review copy

Prerequisites: two different, valid controlled DOCX files with compatible
paragraph styles. Set `GURUBODH_RECIPE_APPEND_SOURCE` to the exact export you
intend to append; use a review copy as the destination:

```bash
export GURUBODH_RECIPE_APPEND_SOURCE=/path/to/next-chapter.docx
cp "$HOME/gurubodh-lab/combined.docx" "$HOME/gurubodh-lab/review.docx"
test -r "$GURUBODH_RECIPE_APPEND_SOURCE"
gurubodh lab append-docx "$GURUBODH_RECIPE_APPEND_SOURCE" \
  "$HOME/gurubodh-lab/review.docx" --page-break
```

Inspect `review.docx` for the intended added chapter and destination styling.
Append replaces that destination atomically without an `--overwrite` flag; it
uses destination paragraph styles and discards appended direct run formatting.
`--no-page-break` omits the separator. Repeating append duplicates content, so
restore the review copy before retrying an already successful operation. Missing
styles or invalid DOCX inputs require correction first. This command prints its
result but creates no audit or canonical readiness marker.

## Compare tokenizer counts

Prerequisites: local UTF-8 chapter TXT files and the pinned BGE-M3 tokenizer
snapshot. Bootstrap through [model-cache setup](../environment-setup.md#bge-m3-model-cache).
Unlike canonical chunking, comparison uses the Hugging Face cache directly;
point `HF_HUB_CACHE` at the provisioned hub cache before starting the process.

```bash
export GURUBODH_RECIPE_RELEASE="$GURUBODH_CMS_LIBRARY_ROOT/123_spand_rahasya/hi-IN"
export HF_HUB_CACHE="$GURUBODH_MODEL_CACHE_DIR"
ls "$GURUBODH_RECIPE_RELEASE/chapters/text_and_metadata"
gurubodh compare-tokenizers \
  --source-dir "$GURUBODH_RECIPE_RELEASE/chapters/text_and_metadata" \
  --model-name BAAI/bge-m3 \
  --model-revision 5617a9f61b028005a4858fdac845db406aefb181 \
  --local-files-only --format json > /tmp/gurubodh-token-counts.json
python -m json.tool /tmp/gurubodh-token-counts.json
```

Require exit zero and inspect per-file counts in stdout JSON; progress is on
stderr. `--source-file /path/to/chapter.txt` processes one file instead.
Directory filters such as `--chapter exact-filename-stem` match filenames/stems,
not the three-digit `generate-chunks --chapters` selector. Missing tokenizer
files require cache repair and rerun; these counts do not create chunks or
canonical artifacts.

External comparison sends selected text to Sarvam. Only when you intend that
transfer, set `SARVAM_API_KEY` in the calling environment and add **both**
`--include-sarvam --approve-external-api` to the preceding command. Review the
selected files before opting in. Provider/key failures require correction and
rerun; offline counts do not establish live provider availability or quota.
