# Gurubodh Web

<app_status>planned</app_status>

`gurubodh-web` is the planned Next.js application for reading Gurubodh content
online.

## Purpose

This app will provide the public user-facing reading experience for published
Gurubodh subjects, chapters, search, navigation, and related content discovery.

## Architectural Boundary

- Reads published content and metadata from the Gurubodh CMS APIs.
- May call the RAG Query Service in later phases for Q&A features.
- Does not write content or metadata to the CMS.
- Does not own content preparation, ingestion, metadata generation, or vector
  indexing workflows.

## Implementation Status

This directory is a placeholder root only. The Next.js application has not been
scaffolded yet.
