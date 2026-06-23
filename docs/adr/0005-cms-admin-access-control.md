# 0005 — CMS Admin UI Access Control

## Status

Proposed

## Context

Strapi's admin UI must be reachable by content editors, but it allows content
mutation and should not be exposed to the open internet protected by
application-level login alone.

## Decision

**Recommended (pending confirmation):** Restrict the admin UI at the network
layer (VPN or IP allowlist enforced at the load balancer/security group),
layered on top of Strapi's own user authentication.

## Consequences

**Positive**
- Defense-in-depth: a network-level restriction plus app-level authentication,
  rather than relying on a single layer of protection.
- Straightforward to implement using existing AWS networking primitives
  (security groups, ALB listener rules) without new services.

**Negative**
- VPN or IP-allowlist access adds friction for remote editors with changing or
  unpredictable IP addresses.
- Does not solve access for editors who need to work from arbitrary,
  unpredictable locations without a VPN client.

**Alternatives Considered**
- **Cognito-fronted access** — more flexible, identity-based access control,
  but requires more setup (user pools, auth flows in front of the admin UI).
- **App-level auth only (no network restriction)** — simplest to set up, but
  the weakest defense-in-depth posture for a UI that can mutate content.
