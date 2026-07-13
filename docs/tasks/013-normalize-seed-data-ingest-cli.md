# Task-013: Normalize Seed-Data Ingest CLI Command Structure

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-07-13</date>
<owners>Gurubodh maintainers</owners>
<github_issue>https://github.com/Team-Gurubodh/gurubodh/issues/75</github_issue>

## Goal

Define a defensive implementation plan for simplifying the `gurubodh-seed-data
ingest` command structure after Task 011 and Task 012 proved the Category,
Subject, Sanatan Glossary, and Prabodhan Glossary ingestion workflows.

The final public CLI should use one repeatable command grammar:

```bash
gurubodh-seed-data ingest <operation> <target>
```

The supported operations should be:

- `preflight`
- `plan`
- `apply`

The supported targets should be the real individual seed-data units:

- `category`
- `subject`
- `sanatan-glossary`
- `prabodhan-glossary`

The plan should remove confusing legacy forms after implementation, preserve
the currently working ingestion behavior, and avoid broad internal rewrites
that could accidentally change live ingestion semantics.

## Context

Task 011 implemented Category and Subject ingestion with:

```bash
gurubodh-seed-data ingest preflight
gurubodh-seed-data ingest plan
gurubodh-seed-data ingest plan --apply
```

Task 012 implemented glossary ingestion later with separate commands:

```bash
gurubodh-seed-data ingest glossary-preflight
gurubodh-seed-data ingest glossary-plan
gurubodh-seed-data ingest glossary-plan --apply
```

Both workflows function as designed, but the command grammar now mixes several
concepts:

- generic commands for Category and Subject;
- glossary-specific command names;
- dry-run and write behavior combined under `plan`;
- two glossary seed-data units hidden behind one glossary command;
- Category and Subject grouped by the historical implementation sequence.

The desired simplification is intentionally conservative. The command surface
should become explicit and repeatable, while the implementation should continue
to rely on the working loaders, preflight checks, planners, appliers, and
reporting behavior wherever possible.

## Decisions

- Use `gurubodh-seed-data ingest <operation> <target>` as the final public CLI
  grammar.
- Keep `<target>` limited to real individual seed-data units:
  - `category`;
  - `subject`;
  - `sanatan-glossary`;
  - `prabodhan-glossary`.
- Do not add `all` as a target in this task.
- Do not add aggregate targets such as `glossary`, `category-subject`,
  `categories`, or `subjects`.
- Treat `plan` as dry-run only.
- Treat `apply` as the only write-capable operation.
- Remove the `--apply` mode from the final public `plan` command.
- Remove legacy ingest commands from the final public CLI:
  - `ingest preflight` without a target;
  - `ingest plan` without a target;
  - `ingest plan --apply`;
  - `ingest glossary-preflight`;
  - `ingest glossary-plan`;
  - `ingest glossary-plan --apply`.
- Keep dependency behavior explicit:
  - `subject` commands may read Category records to validate relation
    readiness;
  - `subject` commands must not create or update Category records;
  - missing or ambiguous Category dependencies should block Subject planning or
    apply and tell the operator to run the Category workflow first.
- Keep Sanatan Glossary and Prabodhan Glossary independent:
  - `sanatan-glossary` commands should not load, plan, or write Prabodhan
    Glossary records;
  - `prabodhan-glossary` commands should not load, plan, or write Sanatan
    Glossary records.
- Preserve stable-key reconciliation and Strapi REST ingestion semantics from
  Tasks 011 and 012.

## Target Command Contract

### Category

```bash
gurubodh-seed-data ingest preflight category
gurubodh-seed-data ingest plan category
gurubodh-seed-data ingest apply category
```

Expected behavior:

- preflight checks Strapi reachability, Category endpoint access, expected
  locales, and Draft & Publish support;
- plan loads the Category artifact, runs Category preflight, classifies
  creates, updates, matching records, conflicts, skipped fields, and publish
  actions without writes;
- apply repeats the safe checks, applies only Category writes, re-plans, and
  prints the post-apply state.

### Subject

```bash
gurubodh-seed-data ingest preflight subject
gurubodh-seed-data ingest plan subject
gurubodh-seed-data ingest apply subject
```

Expected behavior:

- preflight checks Strapi reachability, Subject endpoint access, expected
  locales, Draft & Publish support, and read access to Category records needed
  for relation resolution;
- plan loads the Subject artifact, resolves Category dependencies from
  existing Category records, and reports blocked records for missing or
  ambiguous Category codes;
- apply writes only Subject records and blocks if required Category
  dependencies are missing or ambiguous.

### Sanatan Glossary

```bash
gurubodh-seed-data ingest preflight sanatan-glossary
gurubodh-seed-data ingest plan sanatan-glossary
gurubodh-seed-data ingest apply sanatan-glossary
```

Expected behavior:

- preflight checks Sanatan Glossary endpoint access and Draft & Publish support;
- plan loads only the Sanatan Glossary artifact, validates its approved target,
  and plans creates, updates, matching records, conflicts, blocked records, and
  publish actions without writes;
- apply writes only Sanatan Glossary records and re-plans after apply.

### Prabodhan Glossary

```bash
gurubodh-seed-data ingest preflight prabodhan-glossary
gurubodh-seed-data ingest plan prabodhan-glossary
gurubodh-seed-data ingest apply prabodhan-glossary
```

Expected behavior:

- preflight checks Prabodhan Glossary endpoint access and Draft & Publish
  support;
- plan loads only the Prabodhan Glossary artifact, validates its approved
  target, and plans creates, updates, matching records, conflicts, blocked
  records, and publish actions without writes;
- apply writes only Prabodhan Glossary records and re-plans after apply.

## Defensive Implementation Plan

### Stage 1 - Command Contract And Parser Tests

Goal: introduce the new command grammar in tests before changing ingestion
behavior.

Scope:

1. Add parser coverage for:
   - `ingest preflight category`;
   - `ingest preflight subject`;
   - `ingest preflight sanatan-glossary`;
   - `ingest preflight prabodhan-glossary`;
   - equivalent `plan` and `apply` commands.
2. Assert that unsupported aggregate targets are rejected:
   - `all`;
   - `glossary`;
   - `category-subject`.
3. Assert that legacy command forms are rejected after the final parser change:
   - `ingest preflight`;
   - `ingest plan`;
   - `ingest glossary-preflight`;
   - `ingest glossary-plan`.
4. Assert that `plan --apply` is not accepted in the final command grammar.

Defensive checks:

- Parser tests should not require a live Strapi instance.
- Parser tests should verify command dispatch and parsed operation/target
  values, not only help text.

Expected output:

- The new command contract is locked by tests before implementation details are
  reshaped.

### Stage 2 - Target-Specific Artifact Loading And Preflight Wrappers

Goal: add thin target-specific routing without rewriting the working planners.

Scope:

1. Add a target registry for the four supported seed-data targets.
2. Add target-specific artifact loading helpers:
   - Category artifact only;
   - Subject artifact only;
   - Sanatan Glossary artifact only;
   - Prabodhan Glossary artifact only.
3. Add target-specific preflight helpers:
   - Category checks only Category-specific readiness;
   - Subject checks Subject readiness plus Category read access for dependency
     resolution;
   - Sanatan Glossary checks only Sanatan Glossary readiness;
   - Prabodhan Glossary checks only Prabodhan Glossary readiness.
4. Reuse existing Strapi client configuration and request wrappers.
5. Keep environment variable behavior unchanged:
   - `GURUBODH_STRAPI_URL`;
   - `GURUBODH_STRAPI_API_TOKEN`.

Defensive checks:

- Unit-test each target-specific artifact loader with valid, missing, malformed,
  and schema-invalid artifacts.
- Unit-test glossary target validation so Sanatan artifacts cannot be routed to
  Prabodhan endpoints, and vice versa.
- Unit-test Subject preflight dependency checks without performing writes.

Expected output:

- The CLI can route to one target at a time while preserving existing artifact
  validation and Strapi readiness checks.

### Stage 3 - Target-Specific Plan Operation

Goal: make `ingest plan <target>` the dry-run-only planning surface.

Scope:

1. Route `plan category` to the existing Category planner with only the
   Category artifact.
2. Route `plan subject` to the existing Subject planner with only the Subject
   artifact and existing Category lookup behavior.
3. Route `plan sanatan-glossary` to the existing glossary planner with only the
   Sanatan loaded artifact.
4. Route `plan prabodhan-glossary` to the existing glossary planner with only
   the Prabodhan loaded artifact.
5. Ensure no plan path can call create, update, localization, or publish
   methods.
6. Adjust reports so the selected target is clear and unrelated targets are not
   shown as zero-count sections unless that is intentionally chosen for
   continuity.

Defensive checks:

- Unit-test dry-run classification for each target:
  - create;
  - update;
  - matching;
  - conflict;
  - blocked where applicable.
- Unit-test that `plan subject` reports missing Category dependencies as
  blocked records and recommends the Category workflow first.
- Unit-test that `plan sanatan-glossary` never reads or reports Prabodhan
  Glossary artifacts.
- Unit-test that `plan prabodhan-glossary` never reads or reports Sanatan
  Glossary artifacts.
- Use fake Strapi clients to assert no write calls happen during planning.

Expected output:

- Operators can inspect one seed-data unit at a time with one consistent dry-run
  command.

### Stage 4 - Target-Specific Apply Operation

Goal: make `ingest apply <target>` the only write-capable ingestion command.

Scope:

1. Run artifact loading, target-specific preflight, and planning before writes.
2. Block apply when artifact loading, preflight, conflicts, or blocked records
   prevent a safe write.
3. Route `apply category` to the existing Category applier.
4. Route `apply subject` to the existing Subject applier and ensure it writes
   only Subject records.
5. Route `apply sanatan-glossary` to the existing glossary applier with only
   Sanatan Glossary plan items.
6. Route `apply prabodhan-glossary` to the existing glossary applier with only
   Prabodhan Glossary plan items.
7. Re-query Strapi and re-plan after apply, preserving the existing
   post-apply verification pattern.

Defensive checks:

- Unit-test that `apply category` writes only to `categories`.
- Unit-test that `apply subject` writes only to `subjects` and blocks if
  Category dependencies are missing or ambiguous.
- Unit-test that `apply sanatan-glossary` writes only to
  `sanatan-glossaries`.
- Unit-test that `apply prabodhan-glossary` writes only to
  `prabodhan-glossaries`.
- Unit-test that apply mode is blocked by conflicts and blocked records.
- Unit-test that post-apply re-planning is performed.

Expected output:

- The write path is explicit, target-specific, and no longer hidden under
  `plan --apply`.

### Stage 5 - Remove Legacy Commands And Update Documentation

Goal: complete the public CLI simplification.

Scope:

1. Remove old ingest parser entries:
   - `preflight` without target;
   - `plan` without target;
   - `plan --apply`;
   - `glossary-preflight`;
   - `glossary-plan`.
2. Update `tools/seed-data/README.md` command examples.
3. Update task history execution notes after implementation.
4. Ensure help text describes only the final public command grammar.

Defensive checks:

- Unit-test that old commands fail argument parsing.
- Run `gurubodh-seed-data ingest --help` and confirm only final operations are
  shown.
- Run `gurubodh-seed-data ingest plan --help` and confirm it requires a target
  and does not show `--apply`.

Expected output:

- The final public CLI has no transitional command aliases.

## Risk Assessment

### Low-Risk Areas

- Adding parser tests for the new command grammar.
- Adding thin target routing over existing working planners and appliers.
- Splitting glossary artifact selection so one loaded artifact is passed to the
  existing glossary planner.

### Medium-Risk Areas

- Splitting Category and Subject loading/preflight, because their current
  workflow was implemented as a pair.
- Updating reports without losing useful conflict, blocked-record, skipped-field,
  and publish-action details.
- Removing legacy commands too early without tests that clearly define the new
  replacements.

### Highest-Risk Areas

- Subject dependency behavior. Subject planning and apply must continue to
  resolve Category relations correctly, but `apply subject` must not silently
  create or update Category records.
- Glossary target isolation. `sanatan-glossary` and `prabodhan-glossary` must
  remain separate Strapi Collection Types with independent stable-code
  reconciliation.
- Dry-run safety. `plan <target>` must never perform Strapi writes.

## Verification Plan

Required automated checks:

```bash
cd tools/seed-data
python3 -m unittest
```

Required command-shape checks:

```bash
gurubodh-seed-data ingest --help
gurubodh-seed-data ingest preflight --help
gurubodh-seed-data ingest plan --help
gurubodh-seed-data ingest apply --help
```

Required dry-run checks against a configured disposable or staging Strapi
instance:

```bash
gurubodh-seed-data ingest preflight category
gurubodh-seed-data ingest plan category
gurubodh-seed-data ingest preflight subject
gurubodh-seed-data ingest plan subject
gurubodh-seed-data ingest preflight sanatan-glossary
gurubodh-seed-data ingest plan sanatan-glossary
gurubodh-seed-data ingest preflight prabodhan-glossary
gurubodh-seed-data ingest plan prabodhan-glossary
```

Required apply checks against an approved disposable or staging Strapi instance:

```bash
gurubodh-seed-data ingest apply category
gurubodh-seed-data ingest apply subject
gurubodh-seed-data ingest apply sanatan-glossary
gurubodh-seed-data ingest apply prabodhan-glossary
```

After each apply command, rerun the corresponding plan command and confirm it
reports no pending creates, updates, conflicts, blocked records, or publish
actions for that target.

Required repository checks:

```bash
git diff --check
```

Run CMS verification only if implementation changes touch CMS application files.
This CLI normalization should not require CMS schema or build changes.

## Execution Results

### Stage 2 - 2026-07-13

GitHub issue: https://github.com/Team-Gurubodh/gurubodh/issues/79

Implementation branch:

```text
issue-79-task-13-stage-2-target-preflight
```

Implemented target-specific artifact loading and read-only preflight routing in
`tools/seed-data`:

- added a target registry for:
  - `category`;
  - `subject`;
  - `sanatan-glossary`;
  - `prabodhan-glossary`;
- added one-target-at-a-time artifact loading with schema validation and target
  identity checks;
- validates glossary target routing so Sanatan artifacts cannot be routed to
  Prabodhan endpoints, and Prabodhan artifacts cannot be routed to Sanatan
  endpoints;
- added target-specific preflight behavior:
  - Category checks Category endpoint access, expected locales, and Category
    Draft & Publish status-query support;
  - Subject checks Subject endpoint access, Category read access for relation
    dependency resolution, expected locales, and Subject Draft & Publish
    status-query support;
  - Sanatan Glossary checks only the Sanatan Glossary endpoint and Draft &
    Publish support;
  - Prabodhan Glossary checks only the Prabodhan Glossary endpoint and Draft &
    Publish support;
- wired `gurubodh-seed-data ingest preflight <target>` to the new target-specific
  read-only route;
- kept `plan <target>` and `apply <target>` explicitly deferred to later Task
  13 stages.

Stage 2 performs no create, update, localization, or publish writes.

Verification ran the seed-data unit test suite and read-only preflight checks
against the throwaway Strapi database:

```bash
cd tools/seed-data
python3 -m unittest discover -s tests
python3 -m gurubodh_seed_data.cli ingest preflight category
python3 -m gurubodh_seed_data.cli ingest preflight subject
python3 -m gurubodh_seed_data.cli ingest preflight sanatan-glossary
python3 -m gurubodh_seed_data.cli ingest preflight prabodhan-glossary
```

The unit test suite passed with 87 tests. The live preflight checks passed for
all four targets and each command reported that no writes were performed.

## Follow-Up

- Create implementation issues or implementation branches from GitHub issue
  #75 when work resumes.
- Consider an `all` target only after the single-target command grammar has
  proven insufficient in real operator use.
- Consider a durable decision record only if the CLI grammar becomes a broader
  project convention beyond seed-data ingestion.
