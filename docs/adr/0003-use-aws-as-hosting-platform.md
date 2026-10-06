# 0003 — Use AWS as Hosting Platform

## Status

Accepted

## Decision and rationale

AWS is the accepted hosting direction for infrastructure other than prepared
artifact storage. Existing team familiarity and account setup favor a common
security, networking, billing, and operational model.
[ADR-0006](0006-use-cloudflare-r2-for-prepared-content-artifacts.md) qualifies the
original single-provider choice: prepared artifacts use private Cloudflare R2,
with local storage supported for development and compatibility.

## Tradeoff and review trigger

AWS-specific services increase switching costs; cost control and AWS operational
knowledge remain team responsibilities. R2 adds a second provider boundary.
Reconsider when portability, cost, or operational requirements change materially.

This direction does not select ECS, RDS, Bedrock, or another runtime/service for
an unimplemented component and does not establish deployment. See
[open choices](README.md#open-choices).
