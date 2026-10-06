# Decisions

<record_collection>operational_decisions</record_collection>

Use this directory for decisions that matter but are not full architectural decisions. Examples include documentation conventions, naming choices, workflow decisions, process decisions, and tool placement decisions.

Status meanings follow the [ADR status legend](../adr/README.md#status-legend).
Acceptance is scoped and does not establish implementation or deployment.

## Naming

Current local records use zero-padded contiguous numbers beginning at 0001.
Templates are not numbered records. Use numbered filenames:

```text
0001-short-title.md
0002-short-title.md
```

## Local Records

| # | Title | Status |
| --- | --- | --- |
| 0001 | [Agent Documentation Structure](./0001-agent-documentation-structure.md) | Accepted entry-point rationale; current routing in AGENTS.md |
| 0002 | [GitHub Contribution Workflow](./0002-github-contribution-workflow.md) | Accepted collaboration rationale; current policy in development guides |
| 0003 | [Prepared Artifact Ownership and Lifecycle](./0003-prepared-artifact-ownership-and-lifecycle.md) | Accepted |
| 0004 | [Gurubodh CLI Container Publication and Runtime](./0004-gurubodh-cli-container-publication-and-runtime.md) | Accepted |
| 0005 | [Language-Scoped Prepared Content Release Roots](./0005-language-scoped-prepared-content-release-roots.md) | Accepted |
| 0006 | [Source Font Safety Boundary](./0006-source-font-safety-boundary.md) | Accepted |
| 0007 | [Executable Gurubodh CLI JSON Schema Boundaries](./0007-executable-cli-json-schema-boundaries.md) | Accepted |
| 0008 | [Mandatory Slice Workflow](./0008-mandatory-slice-workflow.md) | Accepted |

Issue [#389](https://github.com/Team-Gurubodh/gurubodh/issues/389) renamed
**Decision-0011: Mandatory Slice Workflow** to **Decision-0008: Mandatory Slice
Workflow**. Its [pinned Decision-0011 source](https://github.com/Team-Gurubodh/gurubodh/blob/9d4a5fd7f8adbb63818c8d1a420cee4e757d1240/docs/decisions/0011-mandatory-slice-workflow.md)
preserves the former number. Current Decision-0008 is distinct from the historical
[Decision-0008: Slice Development Pilot](https://github.com/Team-Gurubodh/gurubodh/blob/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/decisions/0008-slice-development-pilot.md),
which it superseded.

The retired GitHub Issue Taxonomy record is recoverable in
[pinned Git history](https://github.com/Team-Gurubodh/gurubodh/blob/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/decisions/0003-github-issue-taxonomy.md);
current choices are in [GitHub conventions](../development/github-workflow.md#issues)
and [issue templates](../../.github/ISSUE_TEMPLATE/). Historical aliases support
recovery; they are not active records or number reservations. Use full titles and
links, including
[Prepared Artifact Ownership and Lifecycle](0003-prepared-artifact-ownership-and-lifecycle.md),
when referring to either record. Superseded pilot history is linked from
[Mandatory Slice Workflow](0008-mandatory-slice-workflow.md), outside the normal route.

## Records On GitHub

These records were moved to GitHub under #300; their contents remain there.

| # | Title | Status |
| --- | --- | --- |
| 0009 | [CLI Execution Profile Contracts](https://github.com/Team-Gurubodh/gurubodh/issues/292#issuecomment-5571635810) | Accepted; record moved to GitHub under #300 |
| 0010 | [CLI Manifest and Locale Contracts](https://github.com/Team-Gurubodh/gurubodh/issues/294#issuecomment-5571636132) | Accepted; record moved to GitHub under #300 |

## Adding A Decision

Copy the [decision template](../templates/decision-template.md), choose the next
number across the local and GitHub records above (0011 after this migration), and
add the record to the local index. The GitHub-only 0009 and 0010 records share
this collection's sequence. Historical aliases are recovery references, not
active records or reservations.

## ADR Or Decision?

Use [ADRs](../adr/README.md) when the decision changes architecture. Use [decisions](./README.md) when the decision is important context but does not alter core architecture.
