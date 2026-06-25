# 0002 — Use Next.js for Web Frontend

## Status

Accepted

## Context

The platform needs a modern web UI to consume and present CMS content, with
good ***SEO - Search Engine Optimization*** and performance, and a clear path to add RAG-based Q&A features to
the same UI in a later phase. We want a framework with a strong ecosystem and
broadly available engineering talent.

## Decision

Adopt **Next.js (React)** as the web frontend framework.

## Consequences

**Positive**
- Built-in support for multiple rendering strategies (SSG, ISR, SSR), suited to
  a content-heavy site where most pages are largely static but need periodic or
  on-demand updates.
- Large React ecosystem and broadly available engineering talent.
- First-class hosting support on AWS (via Amplify Hosting) as well as
  general-purpose options (ECS, containers).

**Negative**
- Adopting Next.js means adopting its framework conventions and release cadence,
  which the team must keep up with.
- ***SSR - Server-Side Rendering*** / ***ISR - Incremental Static Regeneration*** hosting is operationally more complex than serving plain static files.
- React/Next.js ecosystem churn requires ongoing maintenance attention.

**Alternatives Considered**
- **Nuxt (Vue)** — comparable capability, but a smaller ecosystem and talent
  pool relative to React.
- **SvelteKit** — lighter-weight runtime, but a younger ecosystem with fewer
  engineers already familiar with it.
