# Decision-0001: Agent Documentation Structure

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-06-22</date>
<owners>Gurubodh maintainers</owners>

## Decision and rationale

Use root [AGENTS.md](../../AGENTS.md) as the universal agent entry point and
Markdown under `docs/` for discoverable human/agent knowledge. Small XML-style
metadata supplies stable parse anchors. Repo-local skills are for repeatable
workflows, not another copy of ordinary documentation.

The original scaffold and repository task-handoff guidance were replaced under
[#357](https://github.com/Team-Gurubodh/gurubodh/issues/357) and
[Mandatory Slice Workflow](0011-mandatory-slice-workflow.md).
Current routing belongs to AGENTS.md; documentation placement belongs to the
[documentation index](../README.md#documentation-maintenance); execution records
belong to their owning GitHub issues. Existing task files are historical.

## Review trigger

Reconsider if agent tooling needs a different entry point or repeatable work
needs a dedicated skill. Earlier instructions remain recoverable in Git history.
