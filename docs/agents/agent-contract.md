# Agent Contract

<agent_contract>
This document expands the root `AGENTS.md` guidance for Codex, Antigravity, GLM 5.2, and other AI agents.
The root `AGENTS.md` remains the canonical instruction entry point.
</agent_contract>

## Priorities

<priority_order>
1. Follow explicit user instructions in the current conversation.
2. Follow root `AGENTS.md`.
3. Follow the closest relevant repository documentation.
4. Follow existing code and documentation conventions.
5. Use general best practices only when the repo does not already answer the question.
</priority_order>

## Documentation Routing

<routing>
- Architecture: `docs/architecture.md`
- Goals and non-goals: `docs/goals.md`
- Known limitations: `docs/limitations.md`
- Schemas: `docs/schemas.md`
- ADRs: `docs/adr/`
- Operational decisions: `docs/decisions/`
- Task history: `docs/tasks/`
- PostgreSQL infrastructure scripts: `database/postgres/gurubodh-cms/`
</routing>

## Markdown And XML Style

Use Markdown for human-readable documentation. Use small XML-style blocks for stable agent-facing metadata, routing, and rules. Avoid turning entire documents into XML.

## Skills

<skills_policy>
Use `.agents/skills/` only for repeatable workflows that deserve dedicated instructions, references, or helper scripts.
Do not create skills for single decisions, ordinary documentation, or one-off task notes.
</skills_policy>

## Documentation Responsibilities

<documentation_responsibilities>
- Update ADRs for durable architecture decisions.
- Update `docs/decisions/` for operational, process, or product decisions.
- Update `docs/schemas.md` when schema locations or schema rules change.
- Update `docs/tasks/` when a task brief or execution history changes.
- Update root `README.md` only for high-level project navigation and common commands.
</documentation_responsibilities>
