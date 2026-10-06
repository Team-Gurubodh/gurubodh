# Decision-0006: Source Font Safety Boundary

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-08-28</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Accept centrally approved Unicode and APS source families only. An unverified
ShreeLipi/Shree Dev mapping can silently corrupt canonical text, and a job's font
declaration does not establish the DOCX's effective fonts. Check text-bearing
runs before processing or checkpoint reuse; no manifest/profile override can
approve a font.

Unicode ingestion requires approved Unicode fonts and does not switch pipelines
or convert APS. Legacy conversion and lab proofreading retain approved mixed
Unicode/APS handling. Exact matching and validation belong to the
[shared font policy](../../tools/gurubodh-cli/config/policies/source-fonts.json),
its [schema](../../tools/gurubodh-cli/config/policies/source-fonts.schema.json), and
[font detection](../../tools/gurubodh-cli/gurubodh/legacy/font_detection.py).
See [source handling](../../tools/gurubodh-cli/docs/reference/legacy-docx-conversion.md#source-font-safety-boundary)
and implementation decisions [#307](https://github.com/Team-Gurubodh/gurubodh/issues/307)
and [#318](https://github.com/Team-Gurubodh/gurubodh/issues/318).

## Tradeoff and review trigger

Unsupported sources fail rather than producing potentially corrupt text.
New legacy families require verified font-specific mappings, golden fixtures,
and explicit production-support approval.
