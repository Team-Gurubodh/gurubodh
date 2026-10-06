# Decision-0011: Mandatory Slice Workflow

<record_type>decision</record_type>
<status>accepted</status>
<date>2026-09-18</date>
<owners>Gurubodh maintainers</owners>

## Adoption and rationale

Under [#355](https://github.com/Team-Gurubodh/gurubodh/issues/355), the maintainer
adopted the [slice workflow](../development/slice-workflow.md) repository-wide,
replacing the limited pilot in [#289](https://github.com/Team-Gurubodh/gurubodh/issues/289).
One explicit lifecycle makes issue execution predictable; scalable phase outcomes
and issue-owned evidence avoid competing execution histories.

Current operational rules belong to that workflow; [AGENTS.md](../../AGENTS.md)
owns entry routing. [#357](https://github.com/Team-Gurubodh/gurubodh/issues/357)
consolidated policy ownership. This record describes adoption, not another copy
of gates, procedures, or completion rules.

The superseded pilot decision remains in
[pinned Git history](https://github.com/Team-Gurubodh/gurubodh/blob/f9039b13d87ea0bdcf1bb9b746fe4a8f8f788bab/docs/decisions/0008-slice-development-pilot.md);
its [execution archive](https://github.com/Team-Gurubodh/gurubodh/issues/289#issuecomment-5571636976)
preserves the retrospective and historical handoffs.

## Review trigger

Use observed process evidence to propose refinements in an issue. Policy changes
require maintainer direction and coordinated updates to the maintained workflow
and entry points.
