# 0004 — Strapi API Style: REST vs GraphQL

## Status

Proposed — broader API policy remains undecided.

## Current evidence and open decision

[Seed ingestion](../interfaces/seed-data-artifacts.md) implements REST writes;
[adapters](../../tools/seed-data-cli/gurubodh_seed_data/) reconcile business keys
through the Strapi API. This establishes the seed boundary, not an accepted
API policy for future chapter/metadata writes or client reads.

The original proposal favors REST for server writes and considers GraphQL only
if client query needs justify a second surface. Its tradeoff is simple,
inspectable writes versus richer nested reads and additional contract upkeep.
Revisit with a concrete consumer requirement; approval is still required before
adopting a broader policy.
