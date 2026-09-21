# AGENTS.md

Start here before working in this repository. Gurubodh contains a Strapi CMS,
content and seed-data tools, PostgreSQL infrastructure, and planned web/chat apps.

## Authority

Within your platform's instruction hierarchy, follow explicit maintainer
instructions. This file defines repository instruction ownership:

| Source | Owns |
| --- | --- |
| This file | Entry route, authority, and essential repository rules |
| [Slice workflow](docs/development/slice-workflow.md) | Issue lifecycle, collaboration, approval gates, coverage, verification, handoffs, and completion |
| Relevant GitHub issue and discussion | Complete task scope, accepted designs, execution decisions, and evidence |
| Applicable technical references | Architecture, schemas, interfaces, and component commands |
| [GitHub conventions](docs/development/github-workflow.md) | Issue, branch, commit, PR, and cleanup mechanics |

Skills, templates, tutorials, and indexes support these sources; they do not
override them. Use existing conventions where the sources leave a choice.
If instructions conflict or intent is unclear, clarify before changing the
affected work. Do not infer authorization from historical records.

## Classify and Read

- **Unrelated read-only question:** read the relevant sources and answer.
- **GitHub issue work**, including planning and investigation: read the
  [slice workflow](docs/development/slice-workflow.md), then
  [slice-session](.agents/skills/slice-session/SKILL.md). Follow that route to
  the issue, accepted decisions, latest handoff, and current phase's resources.
- **Tracked-file or repository-state change without an issue:** stop before
  changing the repository and ask whether to create an issue. Then use the
  issue-work route.

Read applicable `SKILL.md` files directly even if your agent has no automatic
skill discovery. Read only the technical references relevant to the task:

| Need | Read |
| --- | --- |
| Project map and commands | [README.md](README.md) |
| Documentation or component guide | [docs/README.md](docs/README.md) |
| Architecture change | [Architecture](docs/architecture.md) and applicable [ADRs](docs/adr/README.md) |
| Scope, roadmap, or priority decision | [Goals](docs/goals.md) |
| Behavior near a known constraint | [Limitations](docs/limitations.md) |
| Operational or process decision | Applicable [decision records](docs/decisions/README.md) |

## Essential Rules

- Work within the issue's scope and accepted design. Obtain explicit direction
  before expanding scope.
- Work on a dedicated issue branch, never directly on `main`, `master`, or
  another protected branch; use the GitHub conventions for branch mechanics.
- Prefer existing conventions and helper APIs. Preserve unrelated files and
  user changes unless explicitly instructed otherwise.
- Keep secrets, credentials, real `.env` values, and local runtime data out of
  commits, documentation, and tool output.
- Update documentation when setup, architecture, decisions, workflows, schemas,
  or behavior changes. Follow the exception below when applicable.
- Add repo-local skills under `.agents/skills/` only for repeatable workflows
  that benefit from dedicated instructions, references, or helpers.

## Composable Jobs Documentation Exception

For GitHub Issues #283–#288, do not add repository implementation documentation.
Keep technical contracts and execution evidence in the GitHub issues and tests.
Operator-facing documentation belongs to a follow-up issue after #288 is
implemented and the complete composable-jobs implementation has been tested.
This scoped exception overrides documentation-update requirements for the series.
