# AGENTS.md

<agent_contract>
This file is the canonical instruction contract for AI agents working in this repository.
Follow it before planning, editing, generating code, refactoring, or updating documentation.
</agent_contract>

<repository_summary>
Gurubodh is a monorepo for a Strapi CMS application, planned user-facing web and
chat applications, content preparation tools, future ingestion and metadata
utilities, PostgreSQL infrastructure scripts, and ML/RAG preparation utilities
housed in the Gurubodh CLI.
</repository_summary>

<routing>
- Read `README.md` for the top-level project map and common commands.
- Read `docs/README.md` for project documentation routing.
- Read `docs/architecture.md` before architecture-affecting changes.
- Read `docs/goals.md` before scope, roadmap, or priority decisions.
- Read `docs/limitations.md` before changing behavior near known constraints.
- Read `docs/adr/` before changing previously decided architecture.
- Read `docs/decisions/` before changing operational or process decisions.
- Read the relevant GitHub issue and latest handoff comment for current execution context.
</routing>

<working_rules>
- Prefer existing repo conventions and local helper APIs over new abstractions.
- Keep edits scoped to the user request and the relevant ownership boundary.
- Do not rewrite unrelated files or revert user changes unless explicitly asked.
- Update documentation when setup, architecture, decisions, workflows, or schemas change.
- Preserve secrets: do not copy values from `.env` files into tracked documentation.
</working_rules>

<composable_jobs_documentation>
For GitHub Issues #283–#288, do not add repository implementation documentation.
Keep technical contracts and execution evidence in the GitHub issues and tests.
Operator-facing documentation belongs to a follow-up issue after #288 is
implemented and the complete composable-jobs implementation has been tested.
This scoped exception overrides documentation-update requirements for the series.
</composable_jobs_documentation>

<github_workflow>
GitHub Issue-first workflow is mandatory for any task that modifies tracked files or repository state.

Before making any change to tracked files:

1. Determine whether the requested work is associated with an existing GitHub Issue.
2. If no issue exists:
   - Do not modify the repository.
   - Stop and ask the user whether a new GitHub Issue should be created.
3. Read the complete issue description (and discussion, if available) before planning or implementing changes.
4. Treat the GitHub Issue as the authoritative definition of scope.
   - Do not implement requirements outside the issue unless explicitly instructed by the user.
5. Create and work from a dedicated branch.
   - Never work directly on `main`, `master`, or any protected branch.
   - Prefer the repository's branch naming convention. If none exists, use:
     `issue-<issue-number>-<short-description>`.
6. Reference the GitHub Issue in:
   - commit messages
   - pull request title
   - pull request description
7. Before considering the task complete:
   - run all relevant verification steps documented by the repository;
   - report any skipped verification together with the reason;
   - summarize the changes made;
   - prepare a pull request description linked to the GitHub Issue.
8. Never merge, squash, rebase, or otherwise integrate changes into the target branch unless the user explicitly instructs you to do so.
9. If the user's request conflicts with this workflow, pause implementation and ask for clarification before modifying the repository.

This workflow is mandatory unless the user explicitly instructs otherwise.
</github_workflow>

<slice_workflow>
For all GitHub issue work, read and follow `docs/development/slice-workflow.md`
before planning or implementation. This workflow is mandatory until the
maintainer changes or withdraws it; do not skip it based on task size or type.
At session entry, read the issue and latest handoff comment, identify the active
slice and phase, and state the intended session outcome. Maintain requirement
coverage in the parent issue, establish phase outcomes before advancing, and
reconcile evidence after each slice and across the whole issue before claiming
completion. Design review and explicit maintainer acceptance are mandatory
before implementation; do not bypass that phase. Obtain approval before making
individual review items optional. Other phases may be brief or marked not
applicable with a recorded reason. Record slice completion after reconciliation.
At session exit, post the handoff in the relevant GitHub issue as the workflow
specifies. Track verification, publication, and delivery separately. Mark an
issue complete and close it only after the maintainer confirms "implementation
verified" and explicitly instructs completion and closure; passing checks alone
does not authorize closure or an automatic closing reference in a PR.
Scoped exceptions require explicit maintainer instruction and must preserve
the workflow's design-review protections. Existing issue, branch, verification,
and merge rules remain applicable unless explicitly overridden.
</slice_workflow>


<verification>
- For CMS changes, prefer the commands documented in `README.md` and `apps/gurubodh-cms/README.md`.
- For content preparation changes, prefer the commands documented in `tools/gurubodh-cli/README.md`.
- If verification cannot be run, report exactly what was skipped and why.
</verification>

<skills>
Repo-local Codex skills, when they become useful, belong under `.agents/skills/`.
Do not create a skill for one-off guidance; create one only for repeatable workflows
that benefit from dedicated instructions, references, or helper scripts.
</skills>
