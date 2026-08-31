# Lab tools

`gurubodh lab` commands are explicitly local and non-canonical. They do not read job JSON, publish to `cms_library/`, or alter canonical source artifacts.

## Proofread one DOCX

After configuring `GEMINI_API_KEY` as described in [Environment setup](../environment-setup.md), run:

```bash
gurubodh lab proofread \
  --source /path/to/lab/proofread/source-files/example.docx \
  --locale hi-IN \
  --lab-root /path/to/lab
```

Only `hi-IN` and `mr-IN` are supported. The command handles approved Unicode or APS fonts in a temporary workspace and sends one structured Gemini request. It rejects ShreeLipi/Sri-Lipi/Shree Dev and every unapproved source font before conversion or proofreading. Each invocation gets a unique run under `<lab-root>/proofread/runs/active/`, which is moved atomically to `succeeded/` or `failed/` when an outcome is recorded. The run-root `README.md` links to output, report, and manifest.

The output includes a proofread DOCX and text; reports include extracted source, a readable diff, structured details, and provenance. None becomes CMS input or canonical subject text.

Each Gemini attempt has a 120-second deadline by default and reports in-flight
elapsed and remaining time every 15 seconds. HTTP 503 `UNAVAILABLE` is a
temporary service-capacity condition, distinct from quota-related HTTP 429: it
uses the same jittered 30-second then 90-second recovery schedule as
`prep-subject`, subject to a longer valid `Retry-After` hint. If that recovery
is exhausted, the failed lab report retains only safe request diagnostics; it
does not include prompts, source or corrected text, credentials, or response
bodies.

## Assemble or append controlled exports

```bash
gurubodh lab assemble-docx /path/to/chapters/msword /path/to/combined.docx
gurubodh lab append-docx /path/to/source.docx /path/to/destination.docx
```

Assembly reads direct DOCX children in case-insensitive natural filename order, ignores Word temporary files, validates a temporary output, and uses page breaks between documents. Existing output requires `--overwrite`.

Append preserves the source, replaces the destination only after validation, and inserts a page break by default. Use `--no-page-break` to omit it. These utilities are intentionally constrained to DOCX files controlled by the Gurubodh export workflow.
