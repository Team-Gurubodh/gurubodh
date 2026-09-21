# Decision-0001: Agent Documentation Structure

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-06-22</date>
<owners>Gurubodh maintainers</owners>

## Current Applicability

The historical decision below is retained. Under
[#357](https://github.com/Team-Gurubodh/gurubodh/issues/357),
[AGENTS.md](../../AGENTS.md) remains the universal entry point and now defines
instruction ownership and direct reading routes. The separate `docs/agents/`
expansion is retired, and repeatable [repo skills](../../.agents/skills/README.md)
are active. These replace the earlier scaffold and reserved-skills guidance.

New execution records and handoffs belong in GitHub issues under the
[slice workflow](../development/slice-workflow.md#authoritative-records),
adopted by [Decision-0011](0011-mandatory-slice-workflow.md); the instruction
below to create task execution records in `docs/tasks/` is superseded.
Existing task records remain historical. Formatting guidance lives in the
[documentation index](../README.md#documentation-maintenance).

## Context

Gurubodh will be worked on by multiple AI agents, with Codex used most often and Antigravity / GLM 5.2 also expected for code generation, refactoring, and planning.

The repository needs documentation that is discoverable by agents, readable by humans, and organized enough to reduce repeated context reconstruction.

## Decision

Use a root `AGENTS.md` as the canonical AI agent contract, with durable project knowledge under `docs/`.

Use Markdown as the primary documentation format. Add concise XML-style blocks only for agent-facing metadata, routing, and rules.

Reserve `.agents/skills/` for future repo-local Codex skills, but do not define active skills until repeatable workflows emerge.

Keep task history under `docs/tasks/` instead of a hidden `.vibe-tasks/` directory.

## Rationale

- Codex recognizes `AGENTS.md` as a durable repository instruction file.
- Plain Markdown under `docs/` is broadly discoverable by other agents and humans.
- Small XML-style blocks give agents stable parse anchors without making docs unpleasant to read.
- Skills are powerful but should be reserved for workflows, not ordinary documentation.
- `docs/tasks/` is easier for agents and humans to discover than a hidden task-history directory.

## Impact

Future agents should start with `AGENTS.md`, then follow links into `docs/`.

Architecture decisions should use `docs/adr/`.

Operational, process, and documentation decisions should use `docs/decisions/`.

Task briefs and execution records should live in `docs/tasks/`, and durable outcomes should be linked or promoted into the broader docs tree.

## Review Trigger

Revisit this decision if another agent becomes the primary development agent, if a tool requires a different canonical instruction file, or if repeated workflows justify active repo-local skills.
