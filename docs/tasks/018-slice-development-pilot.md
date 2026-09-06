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
issue's requirement-coverage checklist and pilot brief live in #283; this
handoff links to them rather than maintaining a competing scope checklist.

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
  schema machinery, resolved policy schemas, package metadata, and validator
  tests. Existing policies require 18 proofreading settings and 11 chunking
  settings. Existing tests validate all maintained complete jobs.
- Identified an implementation boundary for interface design: `_validate()`
  currently chooses `ConfigurationError` only for the `jobs` schema directory;
  component validation must retain configuration-domain errors without changing
  artifact errors. This is an observation, not an implemented fix.
- Prepared #283's complete requirement mapping and a pilot brief with
  acceptance criteria and verification proposals. Later slice groupings remain
  planning proposals, not additional maintainer-approved technical contracts.

## Follow-Up

Current phase: planning draft prepared; interface design has not been completed.
No #283 runtime/schema implementation or test fixtures have been added. #283
and #289 remain open; pilot execution, reconciliation, retrospective, and the
adoption decision remain pending.

Next session: read #283's coverage checklist and pilot brief, review the planning
draft with the maintainer, and work through concrete profile examples and the
validation interface. Resolve profile-envelope naming, component ID checks,
and reuse of resolved-schema constraints before test preparation. Technical
choices should preserve the accepted #283 design and avoid broadening into
#284's resolver or runtime-default changes.

Verification: `git diff --check` passed. A local link/whitespace check covered
all eight changed/new documents; all 15 relative Markdown links resolved and
the documents had clean trailing whitespace and final newlines. Reviewed the
workflow against #289, including exceptions, partial PR references, the
#283-to-#284 gate, and the separate pilot/adoption/issue-completion milestones.
Application tests were not run because this increment changes only process
documentation and issue planning. #283's focused/full tests and package checks
remain pending for technical implementation.

## Publication Handoff

The maintainer authorized committing, pushing, and merging the process PR after
checks, explicitly retaining #289 as open. Use `Refs #289` in the PR. The live
PR linked from #289 records commit, publication, checks, and merge status.
Pilot completion and repository-wide adoption remain pending. The parent-table
approach to slices was accepted; promote slices to sub-issues only when
independent tracking helps.

## Prepared PR Description

Title: `docs: establish the slice development pilot (#289)`

### Summary

Document the provisional workflow for #283's profile-contract pilot, with
agent routing, session handoffs, user exceptions, requirement coverage, and a
whole-issue completion gate. The phase workflow applies only to the selected
pilot; issue-level coverage applies to all of #283.

### Linked Issue

Refs #289. This is partial process setup; pilot execution, retrospective, and
adoption remain pending. Merging this PR must leave #289 open.

### Scope

Adds the workflow guide, process decision, task handoff, and documentation
routing. The coverage map and planning brief were recorded in #283. Technical
schema and runtime implementation remain pending.

### Verification

- `git diff --check` passed.
- All 15 relative Markdown links in eight changed/new documents resolved;
  whitespace and final-newline checks passed.
- Application tests not run: documentation-only increment.

### Notes For Reviewers

Review the pilot scope, parent-issue completion gate, and explicit exception
rules. The maintainer authorized this PR to be merged after checks, leaving
#289 open.
