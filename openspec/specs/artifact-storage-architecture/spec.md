# artifact-storage-architecture Specification

## Purpose
TBD - created by archiving change design-mysql-storage-provider-foundation. Update Purpose after archive.
## Requirements
### Requirement: Large artifacts are stored outside MySQL
The system SHALL store generated documents, quality reports, uploaded source files, extracted markdown, preview images, and other large binary artifacts in a storage backend rather than directly in MySQL binary columns.

#### Scenario: Generated document is completed
- **WHEN** a generation workflow produces a `.docx` document
- **THEN** the document file SHALL be written to the configured artifact storage backend and MySQL SHALL store only metadata and a storage key for the artifact

#### Scenario: Quality report is completed
- **WHEN** a quality report is produced for a generated document
- **THEN** the report SHALL be stored as an artifact object and linked to the generation session or generated article through MySQL metadata

### Requirement: Artifact metadata controls ownership and downloads
The system SHALL authorize downloads through artifact metadata records that include owner, artifact type, storage backend, object key, original filename, MIME type, size, checksum, status, and timestamps.

#### Scenario: Owner downloads an artifact
- **WHEN** an authenticated user requests an artifact that belongs to them
- **THEN** the system SHALL verify ownership through MySQL metadata and stream or redirect to the storage-backed object

#### Scenario: Another user requests an artifact
- **WHEN** an authenticated user requests an artifact owned by another user
- **THEN** the system SHALL deny access even if the user knows the original filename or storage key

### Requirement: Storage backend is configurable
The system SHALL support a local filesystem artifact backend for development and an object-storage style backend for production.

#### Scenario: Local storage mode is enabled
- **WHEN** the artifact storage backend is configured as local
- **THEN** the system SHALL store artifacts under a configured local root using generated storage keys and SHALL still write MySQL artifact metadata

#### Scenario: Object storage mode is enabled
- **WHEN** the artifact storage backend is configured as object storage
- **THEN** the system SHALL write artifacts to the configured bucket or container and SHALL store bucket/container and object key metadata in MySQL

### Requirement: Downloads use artifact identifiers instead of raw paths
The system SHALL expose download access through artifact identifiers or authorized download URLs rather than raw absolute paths or filename-only ownership checks.

#### Scenario: Frontend renders a download button
- **WHEN** the frontend displays a generated article or generation completion state
- **THEN** the download action SHALL reference an authorized artifact id or server-issued URL instead of relying on a bare local filename

#### Scenario: Legacy download paths still exist during migration
- **WHEN** an old generation session contains a legacy `/api/download/{filename}` path
- **THEN** the system MAY serve it through a compatibility path but SHALL prefer artifact metadata for newly generated files

### Requirement: Artifact integrity is tracked
The system SHALL record checksums and byte sizes for stored artifacts so missing or corrupted files can be detected.

#### Scenario: Artifact is stored
- **WHEN** the storage backend successfully writes an artifact
- **THEN** the system SHALL store its byte size and checksum in MySQL metadata

#### Scenario: Artifact retrieval fails integrity checks
- **WHEN** an artifact cannot be found or fails checksum validation during retrieval
- **THEN** the system SHALL return an error and mark or report the artifact as unavailable without exposing internal storage paths

