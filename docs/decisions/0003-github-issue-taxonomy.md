# Decision-0003: GitHub Issue Taxonomy

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-07-05</date>
<owners>Gurubodh maintainers</owners>

## Context

Gurubodh uses an issue-first GitHub workflow with Conventional Commits for
commit messages and pull request titles. The repository previously included
issue templates for tasks, bugs, documentation, and decisions, but did not have
a dedicated feature template.

This created ambiguity when contributors wanted to create an issue for work
that would later use the Conventional Commit `feat` type.

## Decision

Use a dedicated Feature issue template for new functionality or meaningful
capabilities. Feature issue titles should start with `feat: ` so issue titles
align with Conventional Commits where practical.

Keep the Task issue template for scoped non-feature work such as cleanup,
maintenance, migration, investigation, and project enablement.

Continue using Bug Report for reproducible problems, Documentation for
documentation-only work, and Decision for workflow, process, product, or
architecture choices that need an explicit decision before implementation.

## Rationale

Separating Feature from Task makes issue creation clearer for contributors and
keeps GitHub Issues aligned with the repository's Conventional Commit workflow.
It also preserves Task as a useful category for work that does not add a new
capability but still needs planning and tracking.

## Impact

Contributors should choose among Feature, Task, Bug Report, Documentation, and
Decision when creating issues. New functionality should use Feature, while
non-feature project work should use Task.

The `type: feature` label should exist in GitHub so Feature issues receive the
expected label.

## Review Trigger

Revisit this decision if the team adopts a dedicated project management tool,
changes issue labels, or finds that Feature and Task are still being confused in
practice.
