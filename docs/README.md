# Gurubodh Documentation

<doc_index>
This directory is the project knowledge base for humans and AI agents.
Keep `AGENTS.md` short and route durable project knowledge here.
</doc_index>

## Core Documents

- `goals.md` - active goals, non-goals, and project direction.
- `architecture.md` - current system architecture and boundaries.
- `limitations.md` - known limitations, risks, and constraints.
- `schemas.md` - schema locations, ownership, and maintenance rules.
- `agents/agent-contract.md` - expanded guidance for AI agents.
- `tasks/` - task briefs and execution history.

## Records

- `adr/` - architectural decision records for durable architecture choices.
- `decisions/` - operational, process, or product decisions that are not full ADRs.
- `tasks/` - normalized task-history records and guidance.

## Templates

Use `templates/` when creating new records:

- `templates/adr-template.md`
- `templates/decision-template.md`
- `templates/task-template.md`

## Maintenance

<maintenance_rules>
- Update docs in the same change that alters behavior, architecture, setup, schemas, or decisions.
- Prefer links over duplicating content across files.
- Keep documents readable as Markdown; use XML-style blocks only for concise agent-facing metadata or instructions.
</maintenance_rules>
