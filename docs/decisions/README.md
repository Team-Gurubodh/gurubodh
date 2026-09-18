# Decisions

<record_collection>operational_decisions</record_collection>

Use this directory for decisions that matter but are not full architectural decisions. Examples include documentation conventions, naming choices, workflow decisions, process decisions, and tool placement decisions.

## Naming

Use numbered filenames:

```text
0001-short-title.md
0002-short-title.md
```

## Local Records

| # | Title | Status |
| --- | --- | --- |
| 0001 | [Agent Documentation Structure](./0001-agent-documentation-structure.md) | Accepted |
| 0002 | [GitHub Contribution Workflow](./0002-github-contribution-workflow.md) | Accepted |
| 0003 | [GitHub Issue Taxonomy](./0003-github-issue-taxonomy.md) | Accepted |
| 0003 | [Prepared Artifact Ownership and Lifecycle](./0003-prepared-artifact-ownership-and-lifecycle.md) | Accepted |
| 0004 | [Gurubodh CLI Container Publication and Runtime](./0004-gurubodh-cli-container-publication-and-runtime.md) | Accepted |
| 0005 | [Language-Scoped Prepared Content Release Roots](./0005-language-scoped-prepared-content-release-roots.md) | Accepted |
| 0006 | [Source Font Safety Boundary](./0006-source-font-safety-boundary.md) | Accepted |
| 0007 | [Executable Gurubodh CLI JSON Schema Boundaries](./0007-executable-cli-json-schema-boundaries.md) | Accepted |
| 0008 | [Slice Development Pilot](./0008-slice-development-pilot.md) | Superseded by Decision-0011; retained as pilot history |
| 0011 | [Mandatory Slice Workflow](./0011-mandatory-slice-workflow.md) | Accepted |

The two Decision-0003 records retain their historical numbers and paths.
Number-only references to Decision-0003 are ambiguous: cite the full title and
link to [GitHub Issue Taxonomy](./0003-github-issue-taxonomy.md) or
[Prepared Artifact Ownership and Lifecycle](./0003-prepared-artifact-ownership-and-lifecycle.md)
as appropriate.

## Records On GitHub

These records were moved to GitHub under #300; their contents remain there.

| # | Title | Status |
| --- | --- | --- |
| 0009 | [CLI Execution Profile Contracts](https://github.com/Team-Gurubodh/gurubodh/issues/292#issuecomment-5571635810) | Accepted; record moved to GitHub under #300 |
| 0010 | [CLI Manifest and Locale Contracts](https://github.com/Team-Gurubodh/gurubodh/issues/294#issuecomment-5571636132) | Accepted; record moved to GitHub under #300 |

## Adding A Decision

Copy the [authoritative decision template](./0000-template.md), choose the next
unused number across both indexes above, and add the record to the local index.
The existing [templates/decision-template.md](../templates/decision-template.md)
entry point links to the same authoritative template.

## ADR Or Decision?

Use [ADRs](../adr/README.md) when the decision changes architecture. Use [decisions](./README.md) when the decision is important context but does not alter core architecture.
