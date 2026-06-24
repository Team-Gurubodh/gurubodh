# 0006 — Content Preparation Orchestration Approach

## Status

Proposed

## Context

Content Preparation turns legacy source documents into durable artifacts for
later Content Ingestion and Metadata Generation. This stage includes source
document handling, Unicode conversion, chapter splitting, basic metadata
capture, validation, and artifact writing.

Content Preparation is intentionally separate from Content Ingestion, Metadata
Generation, and Metadata Ingestion. It does not write finalized content or
metadata into the CMS. Any orchestration choice for this stage must preserve
that boundary and make failures visible before artifacts cross into later
pipeline stages.

## Decision

**Recommended (pending confirmation):** Keep the current local Python
Content Preparation utility as the implementation for the initial phase. When
the preparation workflow needs managed execution, retries, scheduling, or
operator visibility beyond local runs, use AWS Step Functions to orchestrate
Content Preparation as an explicit state machine whose outputs are prepared
artifacts, not CMS writes.

## Consequences

**Positive**
- Preserves the architecture boundary: Content Preparation produces artifacts
  for later stages and never writes finalized entries directly into the CMS.
- Avoids adding managed orchestration before the preparation workflow requires
  it.
- Step Functions remains a clear scale-up path when the workflow needs built-in
  retry/error handling per step and visual execution history for failed items.
- Easy to add, reorder, or branch pipeline steps without rewriting control-flow
  code by hand once the workflow is ready for managed orchestration.

**Negative**
- Delays a final production orchestration decision until the preparation
  workflow is better understood.
- Step Functions, if adopted later, adds a managed service the team must learn
  and operate.
- For a very simple, strictly linear pipeline, a state machine can be more
  machinery than the problem requires.
- State machine definitions (Amazon States Language) add an authoring layer on
  top of the actual processing code.

**Alternatives Considered**
- **Use Step Functions immediately** — gives strong visibility and retry
  controls from day one, but may add unnecessary managed-service overhead while
  the content preparation workflow is still being validated locally.
- **Queue-worker pattern (SQS + workers)** — a useful pattern for high-volume
  asynchronous processing, but retry behavior, step visibility, and branching
  logic would all need to be built and maintained by hand.
