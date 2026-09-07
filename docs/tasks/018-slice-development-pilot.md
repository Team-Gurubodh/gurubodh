# Task-018: Slice Development Pilot

<record_type>task_history</record_type>
<status>in_progress</status>
<date>2026-09-06</date>
<owners>Gurubodh maintainers</owners>

## Goal

Establish the provisional process under
[#289](https://github.com/Team-Gurubodh/gurubodh/issues/289) and prepare the
proofreading/chunking profile-contract pilot under
[#283](https://github.com/Team-Gurubodh/gurubodh/issues/283).

## Context

The six-issue implementation series is #283–#288. Completed #263 supplied
in-memory job preparation and checkpoint equivalence foundations. The parent
issue's requirement-coverage checklist lives in #283; the S1 brief and execution
evidence live in [#292](https://github.com/Team-Gurubodh/gurubodh/issues/292).
This handoff links to them rather than maintaining a competing scope checklist.

## Decisions

- The maintainer accepted the selected pilot, the provisional process, and the
  requirement coverage, reconciliation, and whole-issue completion additions.
- The maintainer has now authorized repository and code changes within the
  agreed workflow. That authorization does not waive the design/test gates or
  authorize merging, wider process adoption, or legacy retirement.
- [Decision-0008](../decisions/0008-slice-development-pilot.md) records the
  process choice; the [workflow](../development/slice-workflow.md) owns its rules.

## Approved Plan

Set up the process before technical implementation. Map all #283 requirements,
then settle the pilot's acceptance criteria, contracts, and verification plan.
After the pilot, reconcile #283 and review the process under #289. Continue
through outstanding #283 requirements before #284 implementation.

## Execution Results

### 2026-09-06 — process setup and planning draft

- Branch: `issue-289-pilot-development-workflow`, based on fetched `origin/main`
  at `d24b552`. Repository was clean at session entry.
- Added the provisional workflow, agent/documentation routing, process decision,
  and this handoff. The initial planning draft was local and uncommitted.
- Reviewed the full #283/#289 descriptions and empty discussions, existing
  schema machinery, job definition schemas, package metadata, and validator
  tests. Existing policies require 18 proofreading settings and 11 chunking
  settings. Existing tests validate all maintained complete jobs.
- Identified an implementation boundary for interface design: `_validate()`
  currently chooses `ConfigurationError` only for the `jobs` schema directory;
  component validation must retain configuration-domain errors without changing
  artifact errors. This is an observation, not an implemented fix.
- Prepared #283's complete requirement mapping and a pilot brief with
  acceptance criteria and verification proposals. Later slice groupings remain
  planning proposals, not additional maintainer-approved technical contracts.

## Process Setup Handoff — Historical

At setup completion, planning was drafted; interface design, tests, and runtime
implementation had not begun. Both issues remained open for pilot execution,
reconciliation, retrospective, and adoption. The next session was to review
#283's checklist and brief, then settle profile envelopes, ID checks, constraint
reuse, and validation examples before test preparation. #284's resolver and
runtime-default changes remained outside scope.

`git diff --check` passed. All 15 relative Markdown links in eight changed/new
documents resolved; whitespace and final newlines passed. The workflow review
covered #289's exceptions, partial PR references, the #283-to-#284 gate, and
separate pilot, adoption, and issue-completion milestones. Application tests
were not run for this documentation-only increment; technical checks remained
pending.

The maintainer authorized committing, pushing, and merging the process PR after
checks, with `Refs #289` and #289 left open. Its linked live PR records publication
and merge status. Pilot completion and wider adoption were still pending.
Slices stay in the parent table unless independent tracking warrants sub-issues.

### Prepared process PR description

Title: `docs: establish the slice development pilot (#289)`

Refs #289. Adds the provisional workflow, agent/documentation routing, process
decision, and handoff. The phase workflow applies only to S1; requirement
coverage and whole-issue completion apply throughout #283. The coverage map and
planning brief are recorded in #283. Technical delivery, the retrospective, and
adoption remain pending at this stage.

Documentation checks passed as recorded above; application tests were not run.
Review scope, session handoffs, exceptions, and the parent-issue completion gate.
The maintainer authorized merging this process PR after checks, leaving #289 open.

## S1 Results — 2026-09-06 (historical delivery status)

S1 is implemented and verified locally on `issue-283-s1-profile-contracts`, based
on fetched `origin/main` at `c97f89f`. Changes remain **uncommitted and unpublished**.
The working tree contains the implementation. #283 holds the authoritative
requirement map and S1-A1–A8 evidence; S2–S4 and whole-issue review remain pending.

### Planning, design, and implementation

- The maintainer authorized implementation after the effort assessment. The
  working tree was clean. The full #283/#289 descriptions and empty discussions
  were read, R01–R38 were assigned, and S1-A1–A8 were adopted with the brief's
  exclusions. No maintainer-reserved product question remained open.
- [Decision-0009](../decisions/0009-cli-execution-profile-contracts.md) records
  kind-specific envelopes, versioned safe IDs, explicit expected-ID matching,
  configuration errors, non-mutation, and downstream obligations. The initial
  design referenced job definition schemas; the ownership correction below
  supersedes that choice. The timing invariant is checked after schema
  validation without constructing runtime policy records.
- Independent Gemini/BGE-M3 fixtures and invalid cases preceded implementation.
  Initial discovery failed on the missing component API. Tests covered every
  envelope and policy field, unknown fields, kinds/IDs/versions, types/bounds,
  non-JSON values, booleans/nulls, non-mutation, safe deterministic diagnostics,
  resource matching, cache reuse, and job/artifact compatibility. They used real
  validators. The plan included temporary sdist/wheel builds, non-editable
  package checks, focused/full tests, Markdown links, and whitespace checks.
- Implementation registered and packaged both schemas, added
  `validate_component()`, and declared the direct `referencing` dependency.
  Job definition schemas, all 26 complete jobs, `--config`, runtime policy
  constructors, and checkpoint code remained unchanged.
- The first installed probe exposed the incorrect `site-packages/config`
  assumption: wheel data files install under the environment prefix. Returning
  to design/test preparation produced a failing real `PathDistribution`
  regression. Discovery now follows distribution records and preserves
  source-tree precedence. Rebuilding and reinstalling passed S1-A5; broader
  catalog discovery remains outside S1.

### Property ownership correction

The maintainer required both job component schemas to own their complete
specifications without references to other schemas. The correction kept the
envelopes, constraints, API, and timing check, declared all 18 proofreading and
11 chunking properties locally, and removed job-definition registration from
component validation. It refined S1-A1/A3/A5 and R02/R03/R18/R21 without deciding
broader series changes or retirement.

Before implementation, two new tests required complete standalone definitions
and forbade reads of job definition schemas. Both failed, then passed after the
correction. Plain Draft 2020-12 validation and installed checks with job definition
schemas temporarily absent now verify independence. Decision-0009 and current
schema/CLI references document this ownership.

### Verification

| Check | Initial S1 result | Corrected S1 result |
| --- | --- | --- |
| Profile tests | 17 passed. | 18 passed. |
| Full CLI suite | 224 passed in 22.682 seconds; none skipped. | 225 passed in 26.049 seconds; none skipped. |
| Existing schema tests | All 12 passed, including 26 maintained jobs through real loaders and artifact error/pre-write behavior. | These checks still pass. |
| Distribution build | The sdist and its wheel included both job component schemas and all three job definition schemas; wheel metadata declared `referencing`. | Both distributions were rebuilt and their schema inventories passed. |
| Installed probe | Both profiles, all 29 missing-setting cases, local references, non-mutation, and artifact error classification passed. | Profile, missing-setting, non-mutation, and error checks passed independently, with job definition schemas present and temporarily absent. |
| Documentation | Relative links and `git diff --check` passed. | Both checks passed again. |

The full-suite command, run from `tools/gurubodh-cli`, was:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -v
```

Builds used `python -m build --no-isolation` in temporary source copies. Each wheel
was built from its sdist and installed non-editably outside the checkout in a
Python 3.12 environment with schema-validation dependencies. The copied
`tests/check_installed_profiles.py` ran with `-I -B`, checked installed import/schema
locations, and blocked networking. The
[fixture guide](../../tools/gurubodh-cli/tests/fixtures/job-components/README.md)
provides reproduction commands.

No required S1 check was skipped. Live Gemini/R2/model execution and broader
container/catalog discovery were outside scope. Only schema dependencies were
needed for the installed probe.

The original run recorded these temporary evidence locations (no longer
available at the 2026-09-07 publication check):

- `/private/tmp/gurubodh-s1.1yYtcR/` contains the initial `full-suite.log`,
  `build.log`, `dist/`, probe, and environment.
- `/private/tmp/gurubodh-s1-independent.eIUc9l/` contains correction logs,
  distributions, and the copied probe. The installation remains at
  `/private/tmp/gurubodh-s1.1yYtcR/build-env/`.

These transient artifacts are not repository dependencies.

### Reconciliation and next action

R02, R03, and R18 are satisfied locally. Shared requirements remain partial;
S2–S4 own the other five schemas, command/lab selections, environment/storage
contracts, complete field mapping, and whole-issue integration. The S1 review
found no uncovered requirement or scope expansion. Next is S2: subject
manifest/edition and locale contracts. #284 waits for #283's completion review.

The retrospective under #289 recorded the initial offline shared-schema design
and the installed check that caught a defect missed by checkout tests. The
property-ownership correction supersedes that design. The main process overhead
is maintaining the long coverage table: link compact evidence instead of copying
scope into handoffs. Test preparation should identify distribution form and
import origin. These remain proposed refinements; the workflow is provisional,
and wider adoption and reusable templates await the maintainer. Both issues
remain open.

### Prepared S1 PR description

Title: `feat(cli): validate complete execution profiles (#283 S1)`

Refs #283. Implements S1; S2–S4 remain pending. Both job component schemas own all
29 property specifications without references to other schemas. Missing settings
fail without defaults, and resource-ID mismatches produce safe configuration errors.

Package both schemas and fix installed discovery through distribution records.
Document property mappings, immutable policy IDs, and selection/retirement
obligations. Complete jobs and runtime policy behavior remain unchanged.

Verification: 225 CLI tests passed, including all 26 maintained jobs. Sdist/wheel
inventories and the non-editable installed probe passed, including all 29
missing-setting cases with job definition schemas present and absent and
networking blocked. Markdown links and `git diff --check` passed; no required
S1 check was skipped. #283's coverage is reconciled and #289 records the
retrospective. Merge is not authorized.

## S1 publication handoff — 2026-09-07

The maintainer authorized committing, pushing, and opening the S1 PR on
`issue-283-s1-profile-contracts`; merging remains a separate decision.
The branch is based on current `origin/main` at `c97f89f`.
[#292](https://github.com/Team-Gurubodh/gurubodh/issues/292) now owns the slice
brief, current evidence, and publication status, including the PR/commit link.
#283 retains authoritative requirement coverage. The earlier unpublished status
above describes the implementation session, not the subsequent PR delivery.

Publication verification passed: 225 CLI tests in 24.032 seconds, including
18 profile tests and the existing 26-job checks; no skips. Fresh sdist/wheel
inventories matched both schemas, and the non-editable installed probe passed
with job definition schemas present and absent. All 21 relative Markdown links
and `git diff --check` passed. No required S1 check was skipped; live providers
and broader container/catalog checks remain outside S1. The previous temporary
artifacts had expired, so the package checks were rebuilt from current sources.
The PR and current delivery status are recorded in #292.

Next action is PR review. R02/R03/R18 have S1 implementation evidence; shared
requirements remain partial. S2–S4 and whole-issue completion remain pending,
and #284 implementation still waits for that review. The process remains a
pilot; publication does not adopt it repository-wide or authorize retirement.

## S2 implementation handoff — 2026-09-07 (historical delivery status)

The maintainer approved the [S2 scope (#294)](https://github.com/Team-Gurubodh/gurubodh/issues/294)
and authorized implementation, explicitly reserving commits until after review.
S1 merged in PR #293. S2 is on `issue-294-s2-manifest-locale-contracts`, based on
current `main`/remote main at `ffdabd0`. The working tree was clean at entry.
All S2 changes are **local, uncommitted, and unpublished**; no PR has been opened.

### Contracts and implementation

- Read the complete #294/#283 descriptions and empty discussions, current
  workflow/handoff, existing schemas, validation, locale/font decisions, and
  downstream #284 obligations. Scope and acceptance criteria are approved.
- [Decision-0010](../decisions/0010-cli-manifest-locale-contracts.md) records
  concrete identity/path grammar, explicit split shapes, metadata ownership,
  expected-ID checks, safe regex diagnostics, and every S2 field's destination.
  Disabled splitting contains only `enabled: false`; enabled regex splitting
  requires explicit flags. These component rules preserve legacy job behavior.
- Independent fixtures and 15 test methods preceded schema/validator changes.
  Initial tests failed on missing component kinds. The separate mapping test
  already passed existing preparation functions, establishing compatible field
  construction without a production resolver.
- Added standalone subject-manifest and locale-definition schemas, using only
  in-document definitions. Extended the cached component boundary to validate
  resource IDs and Python regex syntax without mutation, defaults, or raw regex
  diagnostics. The existing data-files wildcard packages both schemas; no
  packaging declaration change was needed. Updated the S1 installed probe to
  permit additional registered kinds while retaining its profile checks.
- Fixtures cover APS/Hindi, Unicode/Hindi/Marathi, independent bilingual releases,
  all split modes, manifest/edition selections, and both locale definitions.
  Existing jobs, job schemas, profile contracts, policy constructors, `--config`,
  locale templates, source-font checks, and historical checkpoints are unchanged.

### Verification

- Focused S2 tests: **15 passed**. Structural invalid cases use both standalone
  Draft 2020-12 and shared validation. Separate semantic tests cover regex flags
  and sanitized compiler errors. Mapping tests use real prep/chunks/DOCX
  preparation functions and local/R2 prep source shapes without source execution.
- Full CLI suite: **240 passed in 27.006 seconds, no skips**, including all
  26 maintained-job validations, S1 profiles, and existing error/import boundaries.
  Command from `tools/gurubodh-cli`:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -v`.
- Built the sdist and its wheel in a temporary source copy. Both inventories
  contain all four component schemas byte-for-byte from the working tree.
  Installed the wheel non-editably in an isolated Python 3.12 environment.
- Installed S2 probe: **14 validation tests passed with job schemas present,
  then all 14 passed with them physically absent**. The probe reuses the entire
  validation case class, including standalone checks; mapping tests stay at the
  separate job boundary. The S1 installed probe also passed both profiles,
  29 missing-setting cases, non-mutation, and artifact error classification with
  job schemas present and absent. Both probes block networking and assert
  imports/schema paths originate in the installation outside the checkout.
- Documentation relative links and `git diff --check` passed. No required S2
  verification was skipped. Live sources/providers/R2/models, production catalog
  discovery, and container rollout are outside S2.

Reproduction commands are in the
[fixture guide](../../tools/gurubodh-cli/tests/fixtures/job-components/README.md).
Temporary evidence lives under `/private/tmp/gurubodh-s2-implementation.JZjK0z/`
(`before.log`, `full-suite.log`, `build.log`, `dist/`, `installed-s2.log`, and
`installed-profiles.log`); it is transient, not a repository dependency.

### Reconciliation and next action

R04, R05, R12, R13, and R17 have local implementation and verification evidence.
S2 contributes to R01, R09–R11, R19–R25, R27, and R31–R39; shared requirements
remain partial. #283 retains the authoritative checklist, with #294 owning S2
execution evidence. No uncovered requirement or scope expansion was identified.
S3 owns command/environment/storage contracts and lab binding; S4 owns complete
mapping and all-seven review. #284 remains gated on #283's whole-issue review.

Next action is maintainer review and clarification of the local diff. Do not
commit, push, open a PR, or merge before the requested review and subsequent
authorization. #294 remains open for delivery. The process remains provisional.

### Prepared S2 PR description

Title: `feat(cli): validate subject and locale components (#294, #283 S2)`

Closes #294. Refs #283. Adds two self-contained component schemas for subject
manifests, locale editions, and locale metadata. Invalid paths, releases, split
declarations, and profile references fail without defaults; explicit resource
identity and safe regex checks extend the existing validation boundary.

Document field ownership and downstream mapping. Preserve complete jobs and
runtime behavior; component lookup/composition and S3–S4 remain pending.

Verification: 240 CLI tests passed with no skips, including 15 S2 tests and all
26 maintained jobs. Sdist/wheel inventories and isolated installed S1/S2 probes
passed with job schemas present and absent. Documentation links and whitespace
checks passed. All changes remain uncommitted pending maintainer review.

## S2 publication handoff — 2026-09-07

The maintainer reviewed S2, clarified whole-profile override behavior, and
authorized committing, pushing, and opening its PR. This fulfills the earlier
hold before committing; merging remains a separate decision. The implementation
is unchanged after review on `issue-294-s2-manifest-locale-contracts`, based on
current remote `main` at `ffdabd0`.

Publication verification confirmed that runtime sources, schemas, S2 tests,
installed probes, and fixtures match the verified build/test inputs byte for
byte. The existing 240-test result and both installed probes remain applicable;
no application tests needed repeating for this handoff-only update. Documentation
links, whitespace, and commit-message checks are validated for publication.
No required implementation check is skipped.

[#294](https://github.com/Team-Gurubodh/gurubodh/issues/294) records the resulting
commit, PR, and current delivery status. The earlier local/uncommitted statements
describe the implementation session. #283 retains coverage and remains open for
S3–S4 and whole-issue review; #284 implementation remains gated. Next is PR review.

## S4 implementation handoff — 2026-09-07

S1–S3 are merged, most recently S3 in PR #297. The maintainer reviewed S4's
field ownership, profile selection, and validation/compatibility in separate
discussions, then explicitly approved the consolidated contract and authorized
implementation. Additional locale metadata waits for a separate change request
when needed. [#298](https://github.com/Team-Gurubodh/gurubodh/issues/298) records
the approved contract, execution evidence, and prepared PR description.

S4 is implemented locally on `issue-298-s4-contract-reconciliation`, based on
`6849ceb`. Changes are **uncommitted and unpublished**; no PR is open and nothing
has been merged. The working tree contains the reviewable implementation.

- The [field mapping](../interfaces/assembled-job-field-mapping.md) accounts for
  all 116 command/field paths (56 prep, 38 chunks, 22 DOCX, including containers
  and array items), component selection fields, omission/legacy rules, and
  downstream responsibilities. S1/S2 records are retained and S3 remains
  authoritative in #296 under its documentation exception.
- Test preparation preceded the mapping: the initial combined run passed both
  independence checks and failed on the missing mapping document. The finished
  inventory now rejects missing/duplicate/unmapped job fields. Expanded existing
  mapping tests and new selection/compatibility examples use real preparation
  APIs, without adding a production resolver.
- Final full CLI suite: **262 tests passed in 30.240 seconds, no skips**. This
  includes 27 command/route/edition cases, twelve profile-selection examples,
  all 26 maintained jobs, fonts, checkpoints, and import boundaries. Command:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover -s tests -v`
  from `tools/gurubodh-cli`.
- All-seven ownership checks and 44 reused S1–S3 validation methods passed with
  checkout job-schema access forbidden, then through a fresh non-editable wheel
  installation with job schemas present and physically absent. Standalone
  Draft 2020-12 checks use no external property registry. Networking is blocked;
  installed imports/schema locations are asserted. Job/artifact error-domain
  checks remain separate.
- Sdist and its wheel contain all seven component schemas byte-for-byte from
  the checkout. All 119 tracked runtime/schema/job/packaging files match merged
  S3 exactly. Documentation links and whitespace checks pass. No required
  verification was skipped; live providers/R2/models and later-series runtime
  integration remain outside this slice.

Reproduction is in the [fixture guide](../../tools/gurubodh-cli/tests/fixtures/job-components/README.md).
Transient evidence is under `/private/tmp/gurubodh-s4-2ihmrsiw/`; the final full
suite log is `/private/tmp/gurubodh-s4-full.log`. These are not repository inputs.

Whole-issue review reread #283 and its empty discussion and reconciled R01–R39
and all seven acceptance criteria. Technical requirements have local evidence;
R38 retains S4 publication/PR delivery. #283 remains open and #284 remains gated
until that final delivery/completion review. No requirement was removed or
silently deferred; production resolution, fallback removal, auditing, CLI,
discovery, migration/retirement, and process adoption retain their named later
owners. Next action is maintainer review of the local diff before publication.

## S4 publication handoff — 2026-09-07

The maintainer authorized committing, pushing, and opening the S4 PR. This
supersedes the implementation-session publication hold above; merging remains
a separate decision. The branch is `issue-298-s4-contract-reconciliation`,
based on current remote `main` at `6849ceb`.

Publication verification confirmed that all 145 recorded test/runtime/schema
inputs match the passing verification snapshot. The 262-test full-suite result
and all-seven installed/distribution results remain applicable. No application
change required repeating those checks. Documentation, whitespace, and commit
checks are performed for publication; no required verification is skipped.

[#298](https://github.com/Team-Gurubodh/gurubodh/issues/298) records the resulting
commit/PR and current delivery status; #283 retains parent coverage and the
completion-review gate. Earlier uncommitted/unpublished statements describe
the implementation session. Next is PR review; this publication does not
authorize merging or begin #284 implementation.
