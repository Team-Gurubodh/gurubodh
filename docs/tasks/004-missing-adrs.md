# Task-004: Missing ADRs

<record_type>task_history</record_type>
<status>proposed</status>
<date>2026-06-25</date>
<owners>Gurubodh maintainers</owners>

## Goal

Identify and create the missing Architectural Decision Records needed to make the Gurubodh architecture complete, especially around ingestion, metadata, CMS identity, media storage, hosting runtime, event integration, and RAG behavior.

## Context

The current ADR set captures several foundation choices, including Strapi, AWS, Next.js, CMS API style, content preparation orchestration, vector database selection, model/provider direction, mobile framework, infrastructure-as-code tooling, and CI/CD tooling.

Several durable architecture areas are still implied by `docs/architecture.md`, future tool directories, or cross-cutting requirements, but do not yet have their own ADRs. Capturing these now will reduce ambiguity before implementation work begins.

## Decisions

No decisions have been approved for this task yet.

## Approved Plan

Pending approval.

Suggested execution plan:

1. Review `docs/architecture.md`, `docs/goals.md`, `docs/limitations.md`, `docs/schemas.md`, and existing ADRs.
2. Confirm whether each candidate topic below needs a standalone ADR or should be merged into another ADR.
3. Prioritize the missing ADRs by implementation dependency and architectural risk.
4. Draft approved ADRs using `docs/templates/adr-template.md`.
5. Cross-link the new ADRs from `docs/adr/README.md` and update related documentation if the decisions clarify architecture, schemas, workflows, or limitations.

## Execution Results

Not started.

## Follow-Up

Candidate missing ADRs:

| Candidate ADR | Decision scope |
| --- | --- |
| Content Ingestion Architecture | Artifact contract, idempotency strategy, CMS API write behavior, retry and failure handling, and the rule that ingestion must never write directly to the database. |
| Metadata Generation Architecture | How tags and content descriptors are generated, reviewed, versioned, and tied to chapter-level artifacts. |
| Metadata Ingestion Architecture | Update-only semantics, matching keys, failure behavior when content is absent, idempotent patching, and CMS API contract. |
| CMS Content Model and Identifier Strategy | Subject, category, and chapter relationships; stable codes; seed-data ownership; and how generated filenames map back to CMS entities. |
| Media Storage Strategy | S3, Strapi upload provider, and CDN decisions; asset ownership; bucket layout; and whether ingestion uploads binaries directly or only through the CMS. |
| CMS/Backend Hosting Runtime Model | Runtime choice for Strapi and backend workers. ADR-0003 chooses AWS, but does not choose ECS/Fargate or another concrete runtime shape. |
| Webhook/Event Integration Backbone | Webhook delivery, retries, authentication, EventBridge or SQS usage, cache invalidation, re-embedding triggers, and related event handling. |
| RAG Chunking and Retrieval Strategy | Chunking granularity, content descriptor usage, citation rules, rebuild behavior, and retrieval quality strategy. ADR-0008 chooses vector storage and ADR-0009 chooses model/provider direction, but neither anchors these details. |


## Follow-up (Metadata Generation)

- We have ```A-Glossary-Of-Philosophical-Terms.pdf``` saved in the [Project documentation](https://gurubodh.atlassian.net/wiki/spaces/TSS/pages/5767177/A+glossary+of+philosophical+terms?atlOrigin=eyJpIjoiMWY5MjNhZGZjYzg1NDY1MTk3Nzk5YzdjYTU5ZTZjN2EiLCJwIjoiYyJ9) page. One experiment would be to use this or similar glossary and create tags of matching words or content-descriptors when a match is found. At this point, this is just a thought. 
