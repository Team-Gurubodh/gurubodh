# Gurubodh Documentation

<doc_index>
This directory is the project knowledge base for humans and AI agents.
Keep `AGENTS.md` short and route durable project knowledge here.
</doc_index>

## Core Documents

- [goals.md](./goals.md) - active goals, non-goals, and project direction.
- [architecture.md](./architecture.md) - current system architecture and boundaries.
- [limitations.md](./limitations.md) - known limitations, risks, and constraints.
- [agents/agent-contract.md](./agents/agent-contract.md) - expanded guidance for AI agents.
- [development/](./development/README.md) - contributor workflow guides for GitHub, pull requests, and Conventional Commits.
- [Development pilot](./development/slice-workflow.md) - provisional slice workflow and historical handoffs for the completed #283 pilot; repository-wide adoption remains pending under #289 (status checked 2026-09-18).

## Records

- [adr/](./adr/README.md) - architectural decision records for durable architecture choices.
- [decisions/](./decisions/README.md) - operational, process, or product decisions that are not full ADRs.
- [interfaces/](./interfaces/README.md) - lightweight interface contracts for data and workflow boundaries between subsystems.
- [tasks/](./tasks/README.md) - task briefs, execution history, and normalized task-history guidance.

## Templates

Use these authoritative templates when creating new records:

- [ADR template](./adr/0000-template.md)
- [Decision template](./decisions/0000-template.md)
- [Task template](./templates/task-template.md)

## Maintenance

<maintenance_rules>
- Update docs in the same change that alters behavior, architecture, setup, schemas, or decisions.
- Prefer links over duplicating content across files.
- Keep documents readable as Markdown; use XML-style blocks only for concise agent-facing metadata or instructions.
</maintenance_rules>
