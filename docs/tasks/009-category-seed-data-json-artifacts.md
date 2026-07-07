# Task-009: Category Seed-Data JSON Artifacts

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-07</date>
<owners>Gurubodh maintainers</owners>

## Goal

Validate category CSV seed data and generate a reviewable JSON artifact for
later Strapi 5 ingestion.

## Context

Category seed data is one of the three currently available CSV source types.
It should be implemented before subject seed data because subjects reference
categories.

The expected external CSV source path is:

```text
category/categories.csv
```

relative to:

```text
/Users/rajeev/Gurubodh_library/seed_data/csv_import
```

## Decisions

- Use the Task 007 config-driven source discovery foundation.
- Validate category source data before writing JSON artifacts.
- Treat the category code as the stable business key.
- Keep generated artifacts free of Strapi internal identifiers.
- Keep actual Strapi ingestion out of this task.

## Approved Plan

1. Define required category CSV headers based on the current source file and
   intended Strapi-facing shape.
2. Add category source lookup and path display through the shared config layer.
3. Add category CSV validation.
4. Generate:
   - `tools/seed-data/artifacts/category/categories.json`
5. Add tests for category validation and artifact generation.
6. Update `tools/seed-data/README.md` with category validation and generation
   commands.

## Execution Results

Pending.

## Follow-Up

- Subject validation and artifact generation in Task 010 should validate
  category references against the category stable keys.
