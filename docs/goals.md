# Project Goals

<record_type>project_goals</record_type>
<status>living</status>

## Purpose

Gurubodh is a monorepo for building and operating the Gurubodh CMS, content preparation workflows, future ingestion and metadata tooling, database infrastructure scripts, and ML research experiments.
The project exists in order to bring over 7000 legacy audio files containing knowledge about "Sanatan Dharma", which is the central concept in the Indian Knowledge System. The project will progress in phases, with the initial phases displaying content that has already been converted from audio into Hindi-language transcripts. In the final phase, all knowledge lives within the Gurubodh CMS and is ready to be queried using AI prompts.

## Current Goals

- Create a Strapi 5 CMS application for Gurubodh content. The content is divided into about 75 subjects that have already been converted from audio to Hindi transcripts in MS Word 2007 format. The Strapi 5 headless CMS backend will work with a Next.js frontend application to bring content to knowledge-seekers worldwide.
- Maintain reliable content preparation tooling for DOCX and metadata workflows. 
  - Each subject is typically available as a single MS Word 2007 file. We need to divide that content into chapters, typically about 50 per subject. 
  - While splitting the original file into chapters, also capture relevant metadata that describes the content.
  - Subjects are grouped in Categories. We need to maintain strict mapping between the Subject and Category codes stored in the PostgreSQL ```gurubodh_db``` and the respective codes used while generating names for the subject files available in chapters as well as the entire subject. This mapping is important because it will be repeatedly used to update metadata for a chapter or the entire subject with the help of AI and ML. The metadata updates will come in later phases, as we may adopt more efficient content-chunking strategies and techniques but it is important to know this dependency from the starting phase. 

## Ultimate Goal
Ingest all content from all subjects in all categories, along with other unstructured data and metadata, into the CMS. Use a vector database to store, index, and query embeddings, then build chatbots on top using RAG (retrieval-augmented generation). 

## Global Launch Requirements

- Before Gurubodh is made globally available, define and implement a
  subscription-based content consumption model using an industry-standard
  payment gateway. The model should let newcomers browse the content scope or
  map at no cost, then pay nominal fees for subject-level content consumption.

## Non-Goals

- Do not treat generated or experimental code as production-ready without review.
- Do not place raw PostgreSQL infrastructure scripts inside Strapi application migration folders.
- Do not create agent-specific documentation silos unless a specific agent requires them.

## Update Rules

<update_rules>
Update this file when project priorities, scope boundaries, or explicit non-goals change.
</update_rules>
