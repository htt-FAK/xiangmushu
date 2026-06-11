# kb-broad-format-support Specification

## Purpose
TBD - created by archiving change kb-formats-and-generate-redesign. Update Purpose after archive.
## Requirements
### Requirement: MarkItDown fallback extensions are whitelisted for KB ingestion

The system SHALL accept uploaded knowledge-base files whose lowercased extension is one of `.txt`, `.csv`, `.html`, `.htm`, `.xlsx`, `.xls`, `.doc`, in addition to the existing supported types, by routing them through a MarkItDown-based converter.

#### Scenario: Uploading a txt file
- **WHEN** an authenticated user uploads a knowledge-base file with a `.txt` or `.csv` extension
- **THEN** the backend SHALL treat the file as a MarkItDown-convertible input and produce a `ParsedDocument` tagged `kb_source_type="markdown"`

#### Scenario: Uploading an html file
- **WHEN** an authenticated user uploads a knowledge-base file with a `.html` or `.htm` extension
- **THEN** the backend SHALL convert it via MarkItDown and produce a `ParsedDocument` tagged `kb_source_type="markdown"`

#### Scenario: Uploading an Excel file
- **WHEN** an authenticated user uploads a knowledge-base file with a `.xlsx` or `.xls` extension
- **THEN** the backend SHALL convert it via MarkItDown and produce a `ParsedDocument` tagged `kb_source_type="markdown"`

#### Scenario: Uploading an old Word file
- **WHEN** an authenticated user uploads a knowledge-base file with a `.doc` extension
- **THEN** the backend SHALL convert it via MarkItDown and produce a `ParsedDocument` tagged `kb_source_type="markdown"`

### Requirement: MarkItDown-converted content reuses the markdown splitter

When a file is routed through the MarkItDown fallback, the converter output SHALL be processed by the existing markdown splitter (`_extract_markdown_blocks`) to produce `DocumentBlock` objects with `content_format="markdown"`, reusing the existing chunker pipeline without adding format-specific chunking.

#### Scenario: Converted blocks are emitted as markdown blocks
- **WHEN** a MarkItDown-convertible file is successfully converted
- **THEN** the resulting `ParsedDocument.blocks` SHALL contain one or more `DocumentBlock` objects whose `source_type` is `"markdown"` and `content_format` is `"markdown"`

#### Scenario: Conversion produces empty text
- **WHEN** a MarkItDown-convertible file converts successfully but yields no usable text
- **THEN** the resulting `ParsedDocument` SHALL contain a single synthetic section with the message “（未从该文件提取到有效文本内容）” and at least one empty-state block

### Requirement: Only whitelisted extensions fall back to MarkItDown

The backend SHALL NOT attempt MarkItDown conversion for extensions outside the explicit whitelist; any unrecognized extension SHALL continue to raise a clear `ValueError("不支持的文件类型: {ext}")` rather than silently attempting conversion.

#### Scenario: Uploading a binary file
- **WHEN** an authenticated user uploads a file with an extension not in the direct branch list and not in the MarkItDown whitelist (for example `.zip`, `.exe`, `.bin`)
- **THEN** the backend SHALL NOT run MarkItDown and SHALL return a user-facing error indicating the extension is not supported

### Requirement: Upload route rejects unsupported formats before writing to disk

The `/api/kb/upload` route SHALL perform an extension-supported pre-check BEFORE persisting the uploaded bytes to the historical directory. Files with unsupported extensions SHALL receive an HTTP error response and SHALL NOT be written to disk.

#### Scenario: Uploading an unsupported format
- **WHEN** an authenticated user uploads a `.zip` file
- **THEN** the backend SHALL respond with a `400/422` error containing `{"ok": false, "error": "...", "unsupported_format": true}` and SHALL NOT create a file under `data/historical/`

#### Scenario: Uploading a supported format
- **WHEN** an authenticated user uploads a supported file (direct branch or MarkItDown whitelist)
- **THEN** the file SHALL be written to disk and processed as before

### Requirement: MarkItDown declared as project dependency

The project's declared Python dependencies (`requirements.txt`) SHALL include an explicit entry for the `markitdown` package at a pinned patch version, so the backend's PDF and fallback paths no longer rely on ad-hoc installation.

#### Scenario: Fresh environment install
- **WHEN** a developer runs `pip install -r requirements.txt` in a fresh environment
- **THEN** `from markitdown import MarkItDown` SHALL succeed without a separate installation step

