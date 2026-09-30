# Development Guides

This guide helps human contributors navigate agent-assisted work. It adds no
requirements or approval gates. Agents continue to enter through
[AGENTS.md](../../AGENTS.md); this guide is not required agent reading.

The [slice workflow](slice-workflow.md) defines requirements and approval
boundaries. [Skills](../../.agents/skills/README.md) explain how agents carry out
the work. [Templates](templates/slice-records.md) provide formats for issue records.

## Find Your Activity

Choose the activity you need now. Open a skill to understand the agent's actions;
you do not need to read every linked document. These rows are navigation choices,
not a required sequence of phases.

| Activity | Workflow section to read first | Skill/procedure explaining the agent's actions | Template or record to expect |
| --- | --- | --- | --- |
| Start or resume work | [Session entry](slice-workflow.md#session-entry-and-exit) | [Start or resume](../../.agents/skills/slice-session/SKILL.md#start-or-resume) | Existing issue, accepted decisions, and latest [handoff](templates/slice-records.md#session-handoff); resumption does not itself require a new record |
| Clarify requirements | [Requirements and approval](slice-workflow.md#requirements-and-approval) | [Discover requirements](../../.agents/skills/slice-session/SKILL.md#discover-requirements-and-plan-coverage) | [Requirements specification](templates/slice-records.md#requirements-specification) |
| Plan slices and coverage | [Requirement coverage](slice-workflow.md#requirement-coverage) | [Plan coverage](../../.agents/skills/slice-session/SKILL.md#discover-requirements-and-plan-coverage) | [Parent coverage and slice plan](templates/slice-records.md#parent-coverage-and-slice-plan) |
| Review a solution | [Interface design review](slice-workflow.md#interface-design-review) | [Investigate design choices](../../.agents/skills/slice-design-review/SKILL.md#investigate-and-discover-design-choices) and [prepare a proposal](../../.agents/skills/slice-design-review/SKILL.md#prepare-a-concrete-proposal) | [Design and acceptance](templates/slice-records.md#design-and-acceptance) |
| Revise accepted decisions | [Requirements and approval](slice-workflow.md#requirements-and-approval) | [Discuss and record revisions](../../.agents/skills/slice-design-review/SKILL.md#discuss-and-record) | [Material revision](templates/slice-records.md#material-revision) |
| Implement and verify | [Phase outcomes](slice-workflow.md#phase-outcomes) and [verification](slice-workflow.md#verification-and-delivery-status) | [Advance through phases](slice-workflow.md#advancing-through-phases) and [keep execution records](../../.agents/skills/slice-session/SKILL.md#keep-execution-records-useful) | Verification evidence in the issue: [required evidence and delivery status](slice-workflow.md#verification-and-delivery-status) |
| Complete a slice | [Slice reconciliation](slice-workflow.md#slice-reconciliation) | [Keep execution records](../../.agents/skills/slice-session/SKILL.md#keep-execution-records-useful) | [Slice completion](templates/slice-records.md#slice-completion) and updated [parent coverage](templates/slice-records.md#parent-coverage-and-slice-plan) |
| Pause or transfer work | [Session exit](slice-workflow.md#session-entry-and-exit) | [Pause or transfer](../../.agents/skills/slice-session/SKILL.md#pause-or-transfer) | [Session handoff](templates/slice-records.md#session-handoff) |
| Publish, integrate, or close | [Publication and integration](slice-workflow.md#publication-and-integration), then [whole-issue completion](slice-workflow.md#whole-issue-completion) when closing | [Prepare commits and PRs](../../.agents/skills/github-workflow/SKILL.md#prepare-commits-and-prs) and [integrate, clean up, and close](../../.agents/skills/github-workflow/SKILL.md#integrate-clean-up-and-close) | [PR template](../../.github/PULL_REQUEST_TEMPLATE.md); issue records of delivery evidence and [completion confirmation](slice-workflow.md#whole-issue-completion), as applicable |

## Other Development References

- [Discovery interview protocol](interview-protocol.md) and [skill catalogue](../../.agents/skills/README.md)
- [GitHub conventions](github-workflow.md) and optional [Git and GitHub CLI tutorial](git-github-cli-workflow-tutorial.md)
- [Conventional Commits](conventional-commits.md) and [repository automation](automation.md)
