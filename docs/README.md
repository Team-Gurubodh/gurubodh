# Gurubodh Documentation

<doc_index>
This directory is the project knowledge base for humans and AI agents.
Keep `AGENTS.md` short and route durable project knowledge here.
</doc_index>

## Start here

Read only the route relevant to your work. The project preserves Sanatan Dharma
lectures and transcripts; today the repository provides a CMS and preparation
and seed-data tools. Reading, chat, and retrieval applications are future work.

| Your goal | Essential reading, in order |
| --- | --- |
| Understand the project | [Purpose and goals](goals.md) → [current system map and domain vocabulary](architecture.md#3-system-context) → [limitations relevant to your work](limitations.md) |
| Set up your component | Choose the [CMS local recipe](../apps/gurubodh-cms/README.md#setup), [content-preparation CLI](../tools/gurubodh-cli/docs/getting-started.md), [seed-data CLI](../tools/seed-data-cli/README.md#setup), or [PostgreSQL DBA guide](../database/postgres/gurubodh-cms/README.md). [Web](../apps/gurubodh-web/README.md) and [chat](../apps/gurubodh-chat/README.md) are placeholders, not runnable setup options. |
| Make your first contribution | [Contributing](../CONTRIBUTING.md) → [slice workflow and activity route](development/slice-workflow.md) → [GitHub conventions](development/github-workflow.md); use the chosen component guide's verification commands ([CMS](../apps/gurubodh-cms/README.md#common-commands), [content CLI](../tools/gurubodh-cli/docs/getting-started.md), [seed data](../tools/seed-data-cli/README.md#end-to-end-checklist)). |

Everything below is reference material. You do not need to read the ADR archive,
task history, or pilot handoffs to get started.

## Which source answers which question?

| Question | Source and status |
| --- | --- |
| What works now? | Maintained component guides, executable schemas, code/tests, and applicable [interface contracts](interfaces/README.md). If they disagree, report the command, observed behavior, and conflicting link in a GitHub issue; reconcile documentation and implementation through that issue. Prose does not override executable behavior. |
| Why was a choice made? | [ADRs](adr/README.md) and [decisions](decisions/README.md): **Accepted** records a decision, **Proposed** remains undecided, **Superseded** points to a replacement. Acceptance alone does not prove implementation or deployment. |
| What is authorized or delivered? | The relevant GitHub issue and discussion own scope, execution evidence, and latest delivery status. Follow the [maintained links to GitHub-only contracts](decisions/README.md#records-on-github); scoped documentation exceptions still apply. |
| What was explored or done previously? | [Task records](tasks/README.md) and archived handoffs provide historical context, not proof of current behavior or authorization for future work. [Decision-0011](decisions/0011-mandatory-slice-workflow.md) records repository-wide adoption of the slice workflow under #355; current session handoffs live in GitHub issue comments. |

## Core Documents

- [goals.md](./goals.md) - active goals, non-goals, and project direction.
- [architecture.md](./architecture.md) - current system architecture and boundaries.
- [limitations.md](./limitations.md) - known limitations, risks, and constraints.
- [AGENTS.md](../AGENTS.md) - universal agent entry point, instruction authority, and reading route.
- [Skill catalogue](../.agents/skills/README.md) - operational assistance by issue activity.
- [Slice record formats](development/templates/slice-records.md) - reusable issue records.
- [development/](./development/README.md) - contributor workflow guides for GitHub, pull requests, and Conventional Commits.
- [Slice workflow](./development/slice-workflow.md) - mandatory execution workflow for all GitHub issues, including phase outcomes, coverage, and session handoffs.

## Records

- [adr/](./adr/README.md) - architectural decision records for durable architecture choices.
- [decisions/](./decisions/README.md) - operational, process, or product decisions that are not full ADRs.
- [interfaces/](./interfaces/README.md) - lightweight interface contracts for data and workflow boundaries between subsystems.
- [tasks/](./tasks/README.md) - existing task briefs and retained execution history; new handoffs belong in GitHub issue comments.

## Templates

Use these authoritative templates when creating new records:

- [ADR template](./adr/0000-template.md)
- [Decision template](./decisions/0000-template.md)
- [Task template](./templates/task-template.md) - reference for existing task records; do not create new records for slice-workflow work.

## Documentation Maintenance

Follow [AGENTS.md](../AGENTS.md#essential-rules) for documentation updates and
its [scoped exception](../AGENTS.md#composable-jobs-documentation-exception).
Choose the appropriate home:

| Content | Home |
| --- | --- |
| High-level project navigation and common commands | Root README |
| Architecture decisions | [ADRs](adr/README.md) |
| Operational, process, or product decisions | [Decisions](decisions/README.md) |
| Component setup, behavior, schemas, and interfaces | Component guides and applicable technical references |
| Current designs, acceptance, execution evidence, completion, handoffs | GitHub issue under the [slice workflow](development/slice-workflow.md#authoritative-records) |
| Existing task history | [Task archive](tasks/README.md) |

Prefer links over repeated content. Use readable Markdown; small XML-style
blocks are optional for concise agent-facing metadata or instructions.
