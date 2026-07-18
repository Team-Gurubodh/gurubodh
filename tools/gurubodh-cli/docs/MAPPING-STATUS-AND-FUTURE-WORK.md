# Legacy Font Mapping Status And Future Work

This note records the current mapping status for the DOCX-based legacy
Devanagari conversion workflow.

## Current Direction

The project now treats Microsoft Word `.docx` files as the source of truth.

The active conversion path is:

```text
DOCX source file
  -> config/job-driven converter
  -> Unicode DOCX
  -> full-subject text
  -> optional chapter DOCX/text/metadata outputs
```

The PDF extraction path has been removed because it was an earlier experiment
and is no longer the intended production workflow.

## What Is Working

### APS Family Conversion

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

The DOCX converter detects APS-like font names and routes those text runs
through the APS converter. APS conversion runs locally and offline as long as
`node` and the local project files are available.

## What Remains Risky

### ShreeLipi / Sri-Lipi Conversion

ShreeLipi conversion should be treated as incomplete until the exact mappings
are verified for the source fonts being converted.

The important lesson from earlier experiments is that "ShreeLipi" is not one
universal encoding. Different ShreeLipi-era fonts can assign different glyphs
to the same Latin or extended-ASCII character positions.

Fonts that require special caution include:

```text
SHREE-DEV7-0708
SHREE-DEV7-0712
SHREE-DEV7-0722
```

The current local ShreeLipi vendor file is:

```text
scripts/vendor/hindietools_shreelipi_to_unicode.js
```

That file should not be assumed correct for every ShreeLipi or Shree Dev7
document. A partially converted output with residual legacy characters usually
means the mapping is wrong, not merely that the output Unicode font is wrong.

Output fonts such as Mangal, Noto Sans Devanagari, or Kohinoor Devanagari only
affect rendering after conversion. They cannot repair an incorrect legacy to
Unicode mapping.

## Recommended Future Work

### 1. Collect Exact Font Names

For every failed or new document, first record exact declared Word font names.
For DOCX files, inspect the Word XML font declarations or add a reporting mode
to the DOCX converter.

### 2. Build Small Gold Samples

For each legacy font family, create a small verified fixture:

```text
legacy input text
expected Unicode output
source font name
source document name
provider/tool used for validation
```

Small fixtures are more useful than full converted documents when testing
mappings.

### 3. Route By Specific Font Name

Avoid routing all ShreeLipi fonts to one generic converter. Prefer specific
routing such as:

```text
SHREE-DEV7-0708 -> shree_dev7_0708
SHREE-DEV7-0712 -> shree_dev7_0712
SHREE-DEV7-0722 -> shree_dev7_0722
```

Only use a generic converter when the mapping has been manually verified for
the source document.

### 4. Add One Local Mapping Per Encoding

When a correct mapping is found, add it as a separate local vendor file instead
of mixing it into a generic ShreeLipi converter.

Possible future files:

```text
scripts/vendor/shree_dev7_0708_to_unicode.js
scripts/vendor/shree_dev7_0712_to_unicode.js
scripts/vendor/shree_dev7_0722_to_unicode.js
```

Then update `scripts/legacy_font_convert.js` so each mapping has a distinct
converter key.

### 5. Add Automated Mapping Tests

Add small local tests that run each mapping against known samples and compare
the output to expected Unicode.

Example direction:

```text
tests/fixtures/aps_prakash.json
tests/fixtures/shree_dev7_0708.json
tests/test_legacy_mappings.py
```

Fixtures should include cases for matra placement, reph forms, half letters,
conjuncts, anusvar, chandrabindu, visarga, nukta, punctuation, and digits.

## Practical Recommendation

Use the current workflow for APS documents, with manual review of outputs.

Pause ShreeLipi production conversion until exact mappings are available for
the specific fonts found in the source DOCX files.
