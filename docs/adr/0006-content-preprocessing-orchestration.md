# 0006 — Content Preprocessing Orchestration Approach

## Status

Proposed

## Context

Preprocessing involves multiple steps — cleaning, normalization, enrichment,
validation, de-duplication — that can fail independently and need retry
behavior and visibility into where a given item is in the pipeline.

## Decision

**Recommended (pending confirmation):** Use AWS Step Functions to orchestrate
the preprocessing pipeline as an explicit state machine.

## Consequences

**Positive**
- Built-in retry and error handling per step, with a visual execution history
  that makes debugging failed items straightforward.
- Easy to add, reorder, or branch pipeline steps without rewriting control-flow
  code by hand.
- Integrates natively with Lambda and ECS tasks already used elsewhere in the
  stack.

**Negative**
- Adds a managed service the team must learn and operate.
- For a very simple, strictly linear pipeline, a state machine can be more
  machinery than the problem requires.
- State machine definitions (Amazon States Language) add an authoring layer on
  top of the actual processing code.

**Alternatives Considered**
- **Queue-worker pattern (SQS + workers)** — a simpler mental model with fewer
  moving parts, but retry behavior, step visibility, and branching logic would
  all need to be built and maintained by hand.
