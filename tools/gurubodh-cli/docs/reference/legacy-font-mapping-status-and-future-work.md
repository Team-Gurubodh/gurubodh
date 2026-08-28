# Legacy font mapping status and future work

This note records the current mapping status for the DOCX-based legacy Devanagari conversion workflow.

## Current direction

The project now treats Microsoft Word `.docx` files as the source of truth.

The active conversion path is:

```text
DOCX source file
  -> config/job-driven converter
  -> transient Unicode DOCX when legacy conversion is required
  -> ordered chapter source-text snapshots
  -> canonical proofread chapter text/metadata and provenance
```

The PDF extraction path has been removed because it was an earlier experiment and is no longer the intended production workflow.

## What is working

### APS family conversion

APS conversion is the most usable mapping path today.

Known supported or targeted font names include:

```text
APS-DV-Priyanka
APS-DV-Prakash
APS DV Priyanka
APS DV Prakash
```

The local mapping file is:

```text
scripts/vendor/hindietools_aps_prakash_to_unicode.js
```

The dispatcher is:

```text
scripts/legacy_font_convert.js
```

The DOCX converter detects APS-like font names and routes those text runs through the APS converter. APS conversion runs locally and offline as long as `node` and the local project files are available.

## What remains risky

### ShreeLipi / Sri-Lipi conversion

ShreeLipi conversion is disabled at runtime. Gurubodh rejects ShreeLipi,
Sri-Lipi, and Shree Dev source families before conversion, proofreading, or
canonical publication because verified mappings are unavailable.

The important lesson from earlier experiments is that "ShreeLipi" is not one universal encoding. Different ShreeLipi-era fonts can assign different glyphs to the same Latin or extended-ASCII character positions.

Fonts that require special caution include:

```text
SHREE-DEV7-0708
SHREE-DEV7-0712
SHREE-DEV7-0722
```

The former generic local ShreeLipi mapping has been removed. A partially
converted output with residual legacy characters usually means the mapping is
wrong, not merely that the output Unicode font is wrong.

Output fonts such as Mangal, Noto Sans Devanagari, or Kohinoor Devanagari only affect rendering after conversion. They cannot repair an incorrect legacy to Unicode mapping.

## Recommended future work

### 1. Collect exact font names

For every failed or new document, first record exact declared Word font names. For DOCX files, inspect the Word XML font declarations or add a reporting mode to the DOCX converter.

### 2. Build small gold samples

For each legacy font family, create a small verified fixture:

```text
legacy input text
expected Unicode output
source font name
source document name
provider/tool used for validation
```

Small fixtures are more useful than full converted documents when testing mappings.

### 3. Route by specific font name

Avoid routing all ShreeLipi fonts to one generic converter. Prefer specific routing such as:

```text
SHREE-DEV7-0708 -> shree_dev7_0708
SHREE-DEV7-0712 -> shree_dev7_0712
SHREE-DEV7-0722 -> shree_dev7_0722
```

Do not use a generic converter. Any future support requires a verified,
font-specific mapping and approval to reintroduce it.

### 4. Add one local mapping per encoding

When a correct mapping is found, add it as a separate local vendor file instead of mixing it into a generic ShreeLipi converter.

Possible future files:

```text
scripts/vendor/shree_dev7_0708_to_unicode.js
scripts/vendor/shree_dev7_0712_to_unicode.js
scripts/vendor/shree_dev7_0722_to_unicode.js
```

Then update `scripts/legacy_font_convert.js` so each verified mapping has a
distinct converter key and a centrally reviewed source-font allowlist entry.

### 5. Add automated mapping tests

Add small local tests that run each mapping against known samples and compare the output to expected Unicode.

Example direction:

```text
tests/fixtures/aps_prakash.json
tests/fixtures/shree_dev7_0708.json
tests/test_legacy_mappings.py
```

Fixtures should include cases for matra placement, reph forms, half letters, conjuncts, anusvar, chandrabindu, visarga, nukta, punctuation, and digits.

## Practical recommendation

Use the current workflow for approved Unicode and APS documents, with manual
review of outputs. ShreeLipi production conversion is disabled until exact,
font-specific mappings and golden fixtures are available.
