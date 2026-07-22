# Gurubodh Chat

<app_status>planned</app_status>

`gurubodh-chat` is the planned Next.js application for interacting with
Gurubodh through a conversational chat interface.

## Purpose

This app will provide the public user-facing chat experience for asking
questions about Gurubodh content and receiving grounded answers.

## Architectural Boundary

- Calls the RAG Query Service for retrieval-augmented answers.
- May read CMS APIs for source display, citations, and content previews.
- Does not generate embeddings, maintain vector indexes, or choose model
  providers directly.
- Does not write content or metadata to the CMS.

## Implementation Status

This directory is a placeholder root only. The Next.js application has not been
scaffolded yet.

The proposed chat/RAG workflow is tracked separately in
[`docs/tasks/015-chat-rag-workflow.md`](../../docs/tasks/015-chat-rag-workflow.md)
and has not been promoted to accepted stable architecture.
