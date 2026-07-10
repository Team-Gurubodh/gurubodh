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

This Skill is unnecessary for read-only analysis.

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

## Schemas

docs/schemas.md

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

8. Plan implementation.

9. Implement.

10. Verify.

11. Update documentation.

12. Prepare Pull Request.

13. Wait for user approval.

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

Reference the GitHub Issue using:

Closes #<issue-number>

Checklist items must only be marked complete when they were actually completed.

The Pull Request should summarize:

- implementation;
- verification;
- documentation updates;
- reviewer guidance.

---

# Completion Gate

Work is complete only when all of the following are true.

✓ Issue scope satisfied

✓ No out-of-scope implementation

✓ Verification completed or explained

✓ Documentation updated

✓ Pull Request prepared

✓ Linked Issue included

✓ Ready for review

Repository work is not complete merely because code compiles.

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
