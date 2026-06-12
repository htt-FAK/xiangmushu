# knowledge-vector-metadata Specification

## Purpose
TBD - created by archiving change design-mysql-storage-provider-foundation. Update Purpose after archive.
## Requirements
### Requirement: MySQL tracks knowledge base and source metadata
The system SHALL store knowledge base records, uploaded source records, parsed source artifacts, and ownership metadata in MySQL while Chroma stores vector embeddings.

#### Scenario: Knowledge base is created
- **WHEN** a user creates a knowledge base
- **THEN** the system SHALL persist its owner, slug, label, status, vector collection mapping, and timestamps in MySQL

#### Scenario: Source document is uploaded
- **WHEN** a user uploads a supported source document to a knowledge base
- **THEN** the system SHALL store source metadata in MySQL and store the uploaded file or parsed derivative as an artifact object

### Requirement: Vector collection mapping is durable
The system SHALL track the relationship between each knowledge base and its Chroma collection name in MySQL.

#### Scenario: Retrieval starts for a knowledge base
- **WHEN** generation or search retrieves context from a knowledge base
- **THEN** the system SHALL resolve the Chroma collection using the MySQL knowledge base/vector mapping

#### Scenario: Collection is missing
- **WHEN** MySQL metadata references a Chroma collection that does not exist
- **THEN** the system SHALL report a recoverable indexing error rather than silently returning unrelated or empty evidence

### Requirement: Chunks are traceable to source records
The system SHALL make retrieved vector chunks traceable to MySQL knowledge source and chunk metadata.

#### Scenario: Document is indexed
- **WHEN** a source document is split and embedded
- **THEN** the system SHALL create stable chunk metadata records and include their ids or source ids in Chroma metadata

#### Scenario: Evidence is returned from retrieval
- **WHEN** a retrieval result is used as evidence in generation
- **THEN** the system SHALL be able to identify the originating knowledge base, source document, and chunk metadata for display or audit

### Requirement: Knowledge source lifecycle updates vector metadata
The system SHALL keep MySQL source status and Chroma vector contents consistent when sources are indexed, removed, or reindexed.

#### Scenario: Source indexing succeeds
- **WHEN** all chunks for a source are written to Chroma
- **THEN** the system SHALL mark the MySQL source and chunk metadata as indexed with collection and timestamp details

#### Scenario: Source is removed
- **WHEN** a user removes a knowledge source
- **THEN** the system SHALL delete or deactivate its MySQL source/chunk metadata and remove or tombstone corresponding vectors in Chroma

### Requirement: Vector storage remains separate from document artifact storage
The system SHALL distinguish between original source artifacts, parsed text artifacts, chunk metadata, and vector embeddings.

#### Scenario: Source file is uploaded and indexed
- **WHEN** the system stores and indexes a source file
- **THEN** original/parsed files SHALL be represented as artifacts, chunk metadata SHALL be represented in MySQL, and embeddings SHALL be stored in Chroma

