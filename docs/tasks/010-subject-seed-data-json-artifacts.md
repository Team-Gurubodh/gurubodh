# Task-010: Subject Seed-Data JSON Artifacts

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Goal

Validate subject CSV seed data, verify subject-to-category references, and
generate a reviewable JSON artifact for later Strapi 5 ingestion.

## Context

Subject seed data depends on category seed data because each subject belongs to
or references a category. This task should follow category artifact generation.

The expected external CSV source path is:

```text
subject/subjects.csv
```

relative to:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

## Decisions

- Use the Task 007 config-driven source discovery foundation.
- Treat the subject code as the stable business key.
- Validate category references by stable category code.
- Keep generated artifacts free of Strapi internal identifiers.
- Keep actual Strapi ingestion out of this task.

## Approved Plan

1. Define required subject CSV headers based on the current source file and
   intended Strapi-facing shape.
2. Add subject source lookup and path display through the shared config layer.
3. Add subject CSV validation.
4. Validate subject category references against category source data or the
   generated category artifact.
5. Generate:
   - `tools/seed-data/artifacts/subject/subjects.json`
6. Add tests for subject validation, reference validation, and artifact
   generation.
7. Update `tools/seed-data/README.md` with subject validation and generation
   commands.

## Execution Results

Pending.

## Follow-Up

- Strapi 5 ingestion follows in Task 011.
