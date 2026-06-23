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
- About 50% to 60% of the raw content is stored as MS Word 2007 documents in a legacy, non-unicode encoding/font called 'APS Prakash' or 'APS Priyanka' or the likes of it. These documents must converted to unicode compatible fonts. The ```gurubodh_utils``` python tool does this job well for the detected source fonts. However, we have not tested this conversion against all the source documents that carry the APS family of fonts.
- About 10% of the raw content, that was stored in the more recent days uses another non-unicode font family called 'Shri-Lipi'. Character maps for converting this text to unicode compatible fonts was not found freely on the internet; so, presently the system is unable to process these documents.
- The document are always stored as one document per subject involving about 50 lectures. However before ingesting the content in the CMS, we must to split the subject into chapters. However, while the chunking into chapters may be good enough for the initial phases, when we implement ChatBot / RAG service, we may need more granular chunking and much better metadata.
- We will have to rely on AI and external vocabulary / glossary / concepts-list based on Indian Knowledge System to allow AI to understand the content and apply appropriate 'content-descriptor' metadata to the content chunks. Presently this is an area of exploration and we dont have technical expertise to guide us in the correct direction.

## Risk Mitigations

- Keep `AGENTS.md` short and route agents to the right durable docs.
- Record durable architecture decisions as ADRs.
- Record operational decisions separately from ADRs to avoid overloading architecture records.
- Keep task-history documents under `docs/tasks/` so they are discoverable through the main docs tree.

## Update Rules

<update_rules>
Update this file when a known constraint, unsupported environment, fragile workflow, or recurring agent risk is discovered.
</update_rules>
