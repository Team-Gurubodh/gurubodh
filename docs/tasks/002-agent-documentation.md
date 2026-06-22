# Task-002: Agent Documentation And Templates

<record_type>task_history</record_type>
<status>completed</status>
<date>2026-06-22</date>
<owners>Gurubodh maintainers</owners>

## Goal

Create a professional documentation structure and scaffold standardized templates for:

- Canonical AI agent contract.
- Top-level README routing.
- Goals.
- Architecture.
- Architectural Decision Records.
- Limitations.
- Decisions.
- Schemas.
- Task history.

The documentation should support multiple agents, especially Codex, Antigravity, and GLM 5.2, when planning and executing code changes, code generation, refactoring, and documentation work.

## Context

The repository did not yet have a durable agent contract, ADR structure, architecture overview, decision log, or normalized task-history location.

The initial working history lived under `.vibe-tasks/`, but that is not a widely recognized convention.

Codex is the highest-priority agent for this repository, but documentation should remain useful to other agents through ordinary Markdown discovery.

## Decisions

Use a small, conventional documentation scaffold with a root `AGENTS.md` as the canonical AI agent contract and `docs/` as the durable project knowledge base.

Use Markdown as the primary documentation format and add small XML-style blocks only where they help agents parse metadata, routing, rules, or policy.

Reserve `.agents/skills/` for future repo-local Codex skills, but do not create active skills yet.

Skills should be added only for repeatable workflows that benefit from dedicated instructions, references, or helper scripts. Possible future candidates:

- Strapi content type work.
- PostgreSQL RDS migration review.
- DOCX content preparation workflows.
- Agent documentation maintenance.

Keep task history under `docs/tasks/` so it is discoverable through the main documentation tree. Remove `.vibe-tasks/` as a repo convention.

## Approved Plan

Create this structure:

```text
AGENTS.md
README.md
docs/
  README.md
  goals.md
  architecture.md
  limitations.md
  schemas.md
  agents/
    README.md
    agent-contract.md
  adr/
    README.md
    0000-template.md
  decisions/
    README.md
    0000-template.md
    0001-agent-documentation-structure.md
  tasks/
    README.md
    000-db-script-placement.md
    001-db-script-fix.md
    002-agent-documentation.md
  templates/
    adr-template.md
    decision-template.md
    task-template.md
.agents/
  skills/
    README.md
```

Update root `README.md` and `AGENTS.md` with documentation routing.

Migrate existing `.vibe-tasks/*.md` files into `docs/tasks/` using the task template shape.

Remove `.vibe-tasks/` after migration.

## Execution Results

Created branch:

```text
agent-documentation-templates
```

Created root AI agent contract:

```text
AGENTS.md
```

Created documentation scaffold:

```text
docs/README.md
docs/goals.md
docs/architecture.md
docs/limitations.md
docs/schemas.md
docs/agents/README.md
docs/agents/agent-contract.md
docs/adr/README.md
docs/adr/0000-template.md
docs/decisions/README.md
docs/decisions/0000-template.md
docs/decisions/0001-agent-documentation-structure.md
docs/tasks/README.md
docs/templates/adr-template.md
docs/templates/decision-template.md
docs/templates/task-template.md
```

Created skills placeholder:

```text
.agents/skills/README.md
```

Migrated task history from `.vibe-tasks/` into:

```text
docs/tasks/000-db-script-placement.md
docs/tasks/001-db-script-fix.md
docs/tasks/002-agent-documentation.md
```

Updated root `README.md`, `AGENTS.md`, `docs/README.md`, `docs/tasks/README.md`, `docs/limitations.md`, and `docs/decisions/0001-agent-documentation-structure.md` so task history points to `docs/tasks/`.

Removed `.vibe-tasks/` as a repo convention.

The scaffold uses Markdown-first documents with small XML-style blocks for agent-facing metadata, routing, rules, and policy.

## Follow-Up

- Create active repo-local skills only after a workflow repeats enough to justify dedicated skill instructions.
- Add future task records directly under `docs/tasks/` using `docs/templates/task-template.md`.
