# Decisions

<record_collection>operational_decisions</record_collection>

Use this directory for decisions that matter but are not full architectural decisions. Examples include documentation conventions, naming choices, workflow decisions, process decisions, and tool placement decisions.

## Naming

Use numbered filenames:

```text
0001-short-title.md
0002-short-title.md
```

| # | Title | Status |
| --- | --- | --- |
| [0003](./0003-prepared-artifact-ownership-and-lifecycle.md) | Prepared Artifact Ownership and Lifecycle | Accepted |
| [0004](./0004-gurubodh-cli-container-publication-and-runtime.md) | Gurubodh CLI Container Publication and Runtime | Accepted |
| [0005](./0005-language-scoped-prepared-content-release-roots.md) | Language-Scoped Prepared Content Release Roots | Accepted |
| [0006](./0006-source-font-safety-boundary.md) | Source Font Safety Boundary | Accepted |

Keep `0000-template.md` as the local starter template.

## ADR Or Decision?

Use `docs/adr/` when the decision changes architecture. Use `docs/decisions/` when the decision is important context but does not alter core architecture.
