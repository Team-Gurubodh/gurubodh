# Limitations

<record_type>limitations</record_type>
<status>living</status>

## Known Limitations

- AWS RDS PostgreSQL scripts have placeholder directories, but local PostgreSQL scripts have not yet been adapted or verified for AWS RDS.
- Local PostgreSQL scripts are not automated because proper working of the database involves the following:
  - Creation of starting roles, including DB owner, creation of the database itself
  - Allowing Strapi app scaffolding command to populate Schema in the database created in previous step
  - Granting privileges on objects created by the app scaffolding command to roles created in the first step
  - Possible locking of the Public schema for better security
- Several monorepo areas are placeholders for future work: content ingestion, metadata generation, metadata ingestion, and ML research.
- AI agents may not automatically discover every Markdown file unless rooted through `AGENTS.md`, `README.md`, or explicit user instructions.


## Technical Limitations

- There are over 7000 lectures on 'Sanatan Dharma' captured in audio format that is the starting source material for this project. All the lectures are in traditional Hindi language, not English.
- People have been employed to convert the audio to MS Word using MS Word 2007. 60% to 70% of the content is already converted, but they use non-unicode encoding while saving the documents.
- About 50% to 60% of the raw content is stored as MS Word 2007 documents in legacy, non-Unicode font encodings such as APS Prakash and APS Priyanka. These documents must be converted to Unicode-compatible text. The `gurubodh_utils` Python tool handles detected APS-family source fonts, but this conversion has not yet been tested against all source documents that use APS-family fonts.
- About 10% of the raw content, stored in more recent documents, uses
  Shri-Lipi-family legacy font encodings. Current Shri-Lipi conversion attempts
  fail because the project does not yet have verified character mapping tables
  from the source legacy encoding variants to Unicode. Until those mappings are
  identified, validated, and integrated into the conversion workflow,
  Shri-Lipi-source documents remain unsupported for reliable automated Unicode
  conversion.
- Source content is usually stored as one document per subject, with about 50 lectures per document. Before ingesting the content into the CMS, each subject document must be split into chapters. Chapter-level chunking may be sufficient for initial phases, but the later chatbot/RAG service may require more granular chunks and richer metadata.
- We will have to rely on AI and external vocabulary, glossary, or concept lists based on the Indian Knowledge System to help AI systems understand the content and apply appropriate content-descriptor metadata to content chunks. This remains an exploration area, and the project does not yet have enough technical expertise to define the final approach.

## Risk Mitigations

- Keep `AGENTS.md` short and route agents to the right durable docs.
- Record durable architecture decisions as ADRs.
- Record operational decisions separately from ADRs to avoid overloading architecture records.
- Keep task-history documents under `docs/tasks/` so they are discoverable through the main docs tree.

## Update Rules

<update_rules>
Update this file when a known constraint, unsupported environment, fragile workflow, or recurring agent risk is discovered.
</update_rules>
