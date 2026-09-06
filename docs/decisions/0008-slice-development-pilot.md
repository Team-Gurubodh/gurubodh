# Decision-0008: Slice Development Pilot

<record_type>decision</record_type>
<status>accepted_for_pilot</status>
<date>2026-09-06</date>
<owners>Gurubodh maintainers</owners>

## Context

The composable CLI jobs series spans contracts, composition, provenance, CLI
execution, packaging, and migration. The maintainer wants interactive planning,
interface design, test preparation, implementation, and integration testing
across sessions while retaining complete coverage of each issue.

## Decision

Pilot the [slice workflow](../development/slice-workflow.md) on the proofreading
and chunking profile-contract slice of
[#283](https://github.com/Team-Gurubodh/gurubodh/issues/283), with process work
tracked in [#289](https://github.com/Team-Gurubodh/gurubodh/issues/289).
The phase workflow is mandatory only for this slice initially; whole-issue
coverage and completion controls apply to all of #283.

## Rationale

Waiting until the series finishes would miss useful learning during the
refactoring. Making an untested process mandatory everywhere would introduce
premature overhead. A small executable-contract slice exercises existing
validation and packaging boundaries with a bounded scope.

## Impact

The workflow defines phase outcomes, requirement coverage, slice reconciliation,
whole-issue completion, session handoffs, and explicit user exceptions. Existing
GitHub contribution rules remain applicable. #284 implementation waits for
#283's completion review; completing the pilot alone does not satisfy that gate.

## Review Trigger

Review after the pilot slice. Record lessons and proposed changes in #289 and
obtain maintainer agreement before repository-wide adoption. Defer reusable
issue-template changes until that decision. This record accepts the pilot,
not an unconditionally permanent workflow.
