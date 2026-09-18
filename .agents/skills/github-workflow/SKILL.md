---
name: github-workflow
description: Follow Gurubodh's issue-first and mandatory slice workflow when planning or implementing GitHub issue work, changing tracked files, or preparing commits and pull requests. Not needed for unrelated read-only analysis.
---

# GitHub Workflow

## Purpose

A GitHub Issue is considered the source of scope when the user has identified it,
or when the user has agreed that a new Issue should be created for the requested work.

The workflow ensures that repository changes are:

- traceable to the GitHub Issue that defines the work;
- consistent with repository architecture and documented decisions;
- limited to the scope defined by that Issue;
- verified before review;
- documented through the repository Pull Request process.

This Skill defines workflow.

Repository policies remain defined by `AGENTS.md`.

GitHub Issue templates define work.

The Pull Request template defines review documentation.

When these documents disagree, precedence is:

1. explicit user instruction
2. AGENTS.md
3. this Skill
4. GitHub Issue
5. repository documentation

---

# When This Skill Must Be Loaded

Load this Skill whenever work may:

- modify tracked files;
- create tracked files;
- delete tracked files;
- rename tracked files;
- update documentation;
- change repository configuration;
- prepare commits;
- prepare Pull Requests.

Also load this skill when planning GitHub issue work, including an investigation
whose deliverable is analysis. Unrelated read-only questions do not need it.

Before planning or implementation, read and follow
[the slice workflow](../../../docs/development/slice-workflow.md). It is mandatory
for all GitHub issue work until the maintainer changes or withdraws it. Use its
phase outcomes, requirement coverage, reconciliation, and issue-comment handoffs.
Design review and explicit maintainer acceptance are required before implementation;
that phase cannot be bypassed or marked not applicable. Prompt for approval before
making individual review items optional. Other phases may be brief or marked not
applicable with a reason. Record scoped maintainer exceptions in the issue,
preserving the workflow's design-review protections.

---

# Guiding Principles

The workflow follows six principles.

1. Issues define work.
2. Documentation defines implementation.
3. Scope is intentionally limited.
4. Verification is mandatory.
5. Human approval precedes integration.
6. Clarification is preferred over assumptions.

---

# Repository Sources of Truth

Before implementing work, treat the following as authoritative.

## Scope

GitHub Issue

## Repository policy

AGENTS.md

## Architecture

docs/architecture.md

docs/adr/

docs/decisions/

## Project goals

docs/goals.md

## Known constraints

docs/limitations.md

## Repository commands

README.md

project README files

## Review documentation

.github/PULL_REQUEST_TEMPLATE.md

Never duplicate information that already exists in these documents.

---

# Required Inputs

Implementation must not begin until the following information is known.

- GitHub Issue
- implementation objective
- expected completion criteria
- affected components
- verification approach

If any required information is missing:

STOP.

Request clarification.

---

# Decision Gate

Before modifying any tracked file, verify all of the following.

✓ A GitHub Issue exists.

✓ The Issue has been read completely.

✓ The requested work is understood.

✓ Repository documentation relevant to the task has been reviewed.

✓ Any referenced ADRs or Decisions have been reviewed.

✓ Planned work stays within Issue scope.

✓ The slice workflow has been read, the latest issue handoff consulted, and the
active slice, phase, and intended session outcome identified.

✓ Parent requirements are assigned and the active slice's acceptance criteria,
relevant contracts, and verification approach are settled before implementation.

✓ The maintainer explicitly accepted the design for the affected work; blocking
questions and approved optional review items are recorded in its execution issue.

✓ The current branch is not:

- main
- master
- any protected branch

If every condition cannot be satisfied:

STOP.

Do not modify tracked files.

---

# Standard Workflow

Every implementation follows this sequence.

1. Understand the request.

2. Locate the GitHub Issue.

3. Read the Issue completely.

4. Identify the Issue type.

5. Read all referenced documentation.

6. Identify implementation boundaries.

7. Create a dedicated working branch.

8. Maintain the parent issue's requirement coverage and plan the active slice.

9. Obtain explicit design acceptance, establish test-preparation outcomes, then implement.

10. Verify integration, reconcile parent requirements, and post the slice-completion record.

11. Update documentation.

12. Prepare Pull Request; perform whole-issue review before requesting issue completion.

13. Record the session handoff as an issue comment when pausing or transferring work.

14. Obtain explicit maintainer authorization before merging or integrating changes.

Complete each applicable step, and explicitly note any step that is already satisfied or not applicable.

---

# Issue Types

Use the Issue type to determine implementation behavior.

- Feature: Acceptance Criteria define the Definition of Done. Do not implement work outside those criteria. Treat "Out of Scope" as prohibited.
- Bug Report: Reproduce the issue whenever practical. Understand root cause before changing code. Prefer minimal corrections and protect against regression.
- Documentation: Avoid code changes unless explicitly requested. Maintain technical correctness and repository terminology.
- Configuration: Understand operational consequences before changing configuration. Document operational impact when appropriate.
- Decision: Read linked ADRs and architectural documentation. If implementation conflicts with the documented decision, stop and request clarification.
- Task: Treat the task description as the implementation boundary. Avoid feature expansion.

---

# Planning

Implementation begins with a short plan.

The plan should identify:

- affected components;
- dependencies;
- verification strategy;
- documentation updates;
- risks.

Large tasks should be divided into logical implementation steps.

Planning should reduce implementation surprises.

---

# Branch Management

Never work directly on:

- main
- master
- protected branches

Follow repository branch naming conventions.

If none exist, use:

issue-<number>-<short-description>

One branch should normally correspond to one GitHub Issue.

---

# Implementation Rules

During implementation:

- keep changes cohesive;
- preserve repository conventions;
- preserve architecture;
- avoid unrelated cleanup;
- avoid speculative improvements;
- avoid unnecessary abstraction.

Do not solve adjacent problems unless requested.

When additional work becomes necessary:

STOP.

Request approval before expanding scope.

---

# Documentation Responsibilities

Update documentation whenever implementation changes:

- architecture;
- workflows;
- schemas;
- operational behavior;
- user-facing behavior;
- repository setup.

Documentation should evolve together with implementation.

---

# Verification

Use repository verification procedures before inventing alternatives.

Prefer commands documented in:

- README.md
- project README files
- repository documentation

Never claim verification that was not executed.

If verification cannot be completed:

- identify the skipped verification;
- explain why;
- describe potential impact.

---

# Pull Request Preparation

Use the repository Pull Request template.

Populate every applicable section.

Never remove template sections.

Reference the GitHub Issue using `Refs #<issue-number>` until whole-issue review
passes and the maintainer confirms "implementation verified" and explicitly
instructs issue completion and closure. Only then may a closing reference be used.
Include the issue number in the Conventional Commit PR title.

Checklist items must only be marked complete when they were actually completed.

The Pull Request should summarize:

- implementation;
- verification;
- documentation updates;
- reviewer guidance.

---

# Completion Gate

Implementation is ready for review only when all of the following are true.

✓ Issue scope satisfied

✓ No out-of-scope implementation

✓ Verification completed or explained

✓ Slice evidence reconciled against parent requirements; whole-issue review
passed before requesting that the entire issue be marked complete

✓ Session handoff posted in the relevant GitHub issue when ending the session

✓ Documentation updated

✓ Pull Request prepared

✓ Linked Issue included

✓ Ready for review

Track implementation verified, published for review, and delivered separately.
Mark an issue complete and close it only after the maintainer confirms
"implementation verified" and explicitly instructs completion and closure.
Record that instruction; readiness for review or successful checks do not
provide it. Follow the slice workflow for pending delivery and closure records.

---

# Stop Conditions

Stop implementation and ask the user when new information shows that:

- no GitHub Issue defines the requested work;
- implementation requires expanding Issue scope;
- repository documentation or architecture guidance conflicts;
- required repository information is missing;
- verification cannot establish reasonable confidence;
- continuing would require work on a protected branch.

Clarification is preferred over guessing.
