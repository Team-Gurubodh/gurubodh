# Limitations

<record_type>limitations</record_type>
<status>living</status>

## Known Limitations

- AWS RDS PostgreSQL scripts have placeholder directories, but local PostgreSQL scripts have not yet been adapted or verified for AWS RDS.
- Several monorepo areas are placeholders for future work: content ingestion, metadata generation, metadata ingestion, and ML research.
- AI agents may not automatically discover every Markdown file unless rooted through `AGENTS.md`, `README.md`, or explicit user instructions.

## Risk Mitigations

- Keep `AGENTS.md` short and route agents to the right durable docs.
- Record durable architecture decisions as ADRs.
- Record operational decisions separately from ADRs to avoid overloading architecture records.
- Keep task-history documents under `docs/tasks/` so they are discoverable through the main docs tree.

## Update Rules

<update_rules>
Update this file when a known constraint, unsupported environment, fragile workflow, or recurring agent risk is discovered.
</update_rules>
