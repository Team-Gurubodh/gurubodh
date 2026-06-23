# Project Goals

<record_type>project_goals</record_type>
<status>living</status>

## Purpose

Gurubodh is a monorepo for building and operating the Gurubodh CMS, content preparation workflows, future ingestion and metadata tooling, database infrastructure scripts, and ML research experiments.
The project exists in order to bring over 7000 legacy audio files containing knowledge about "Sanatan Dharma", which is the central concept in the Indian Knowledge System. The project will progress in phases with initial phases attempting to display content that is already converted from audio into Hindi Language transcripts. In the final phase, all the knowledge lives within the Gurubodh CMS ready to be queried using AI prompts.

## Current Goals

- Create a Strapi 5 CMS application for Gurubodh content. The content is divided in about 75 different subjects that are already converted from audio to Hindi transcript in MS Word 2007 format. The Strapi 5 CMS headless backend will work with Next.js front end application to bring content to knowledge-seekers worldwide.
- Maintain reliable content preparation tooling for DOCX and metadata workflows. 
  - Each subject is  typically available as a single MS Word 2007 file. We need to divide that content into chapters - typically 50 per subject. 
  - While spitting the original file into chapters (about 50 per subject), also capture relevant metadata that describes the content.
  - Subjects are grouped in Categories. We need to maintain strict mapping between the Subject and Category codes stored in the PostgreSQL ```gurubodh_db``` and the respective codes used while generating names for the subject files available in chapters as well as the entire subject. This mapping is important because it will be repeatedly used to update metadata for a chapter or the entire subject with the help of AI and ML. The metadata updates will come in later phases, as we may adopt more efficient content-chunking strategies and techniques but it is important to know this dependency from the starting phase. 
- Build subscription based content consumption model as soon as possible using industry standard payment gateway integration. The idea is to promote pay-as-you-go model with very nominal fees charged for consuming content. We need to develop an approach such that a new-comer is encouraged to browse content scope or map at no cost, and very nominal fees for consuming content at a single subject level. 


## Ultimate Goal
We have ingested all the content from all the Subjects in all Categories and other unstructured data and metadata into the CMS, use vector database to store, index, and query embeddings, and then build chatbots on top using RAG (retrieval-augmented generation). 

## Non-Goals

- Do not treat generated or experimental code as production-ready without review.
- Do not place raw PostgreSQL infrastructure scripts inside Strapi application migration folders.
- Do not create agent-specific documentation silos unless a specific agent requires them.

## Update Rules

<update_rules>
Update this file when project priorities, scope boundaries, or explicit non-goals change.
</update_rules>
