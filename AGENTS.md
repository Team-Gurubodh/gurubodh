# AGENTS.md

<agent_contract>
This file is the canonical instruction contract for AI agents working in this repository.
Follow it before planning, editing, generating code, refactoring, or updating documentation.
</agent_contract>

<repository_summary>
Gurubodh is a monorepo for a Strapi CMS application, content preparation tools,
future ingestion and metadata utilities, PostgreSQL infrastructure scripts, and
ML research workspace.
</repository_summary>

<routing>
- Read `README.md` for the top-level project map and common commands.
- Read `docs/README.md` for project documentation routing.
- Read `docs/architecture.md` before architecture-affecting changes.
- Read `docs/goals.md` before scope, roadmap, or priority decisions.
- Read `docs/limitations.md` before changing behavior near known constraints.
- Read `docs/adr/` before changing previously decided architecture.
- Read `docs/decisions/` before changing operational or process decisions.
- Read `docs/schemas.md` before adding or changing structured data schemas.
- Read `docs/tasks/` for task briefs, execution history, and recent context.
</routing>

<working_rules>
- Prefer existing repo conventions and local helper APIs over new abstractions.
- Keep edits scoped to the user request and the relevant ownership boundary.
- Do not rewrite unrelated files or revert user changes unless explicitly asked.
- Update documentation when setup, architecture, decisions, workflows, or schemas change.
- Preserve secrets: do not copy values from `.env` files into tracked documentation.
</working_rules>

<verification>
- For CMS changes, prefer the commands documented in `README.md` and `apps/gurubodh-cms/README.md`.
- For content preparation changes, prefer the commands documented in `tools/content-preparation/README.md`.
- If verification cannot be run, report exactly what was skipped and why.
</verification>

<skills>
Repo-local Codex skills, when they become useful, belong under `.agents/skills/`.
Do not create a skill for one-off guidance; create one only for repeatable workflows
that benefit from dedicated instructions, references, or helper scripts.
</skills>
