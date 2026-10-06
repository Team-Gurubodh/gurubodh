# 0002 — Use Next.js for Web Frontend

## Status

Accepted

## Decision and rationale

Use Next.js (React) for the web frontend. A content-heavy site needs search-engine
visibility and performant rendering with static generation, revalidation, and
server rendering where appropriate. The React ecosystem and available engineering
experience provide a path to later retrieval/Q&A features.

## Tradeoff and review trigger

Framework conventions and release churn require maintenance. Server rendering
and revalidation add hosting complexity beyond static files. Reconsider if those
capabilities no longer justify that operational cost.

The [web root](../../apps/gurubodh-web/README.md) is a placeholder, not a scaffolded
application. [Hosting](README.md#adr-0007--web-hosting) remains undecided.
