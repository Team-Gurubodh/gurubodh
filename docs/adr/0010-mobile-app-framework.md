# 0010 — Mobile App Framework (Phase 4)

## Status

Proposed

## Context

Phase 4 requires a mobile app that consumes the same CMS and RAG APIs as the
web app. Sharing logic and types with the existing Next.js codebase would
reduce duplicate work and keep the API contract consistent across channels.

## Decision

**Recommended (pending confirmation):** Use React Native (with Expo) for the
mobile app.

## Consequences

**Positive**
- Shares TypeScript types and API client logic with the Next.js web app via a
  shared package, reducing duplicated integration code.
- A single codebase targets both iOS and Android.
- Expo reduces native build and release overhead compared to a bare React
  Native setup.

**Negative**
- React Native can hit limits for highly custom native UI or performance-
  sensitive features.
- Expo's managed workflow may require "ejecting" to access certain native
  modules, adding complexity later if those needs arise.

**Alternatives Considered**
- **Native iOS (Swift) + Native Android (Kotlin), built separately** — the best
  possible platform-specific UX and performance, but doubles build and
  maintenance effort and shares no code with the web app.
