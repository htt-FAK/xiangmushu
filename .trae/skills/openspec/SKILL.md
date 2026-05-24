---
name: "openspec"
description: "Generates and maintains OpenAPI/Swagger specification documents. Invoke when user needs to create, update, or validate API specifications."
---

# OpenSpec Skill

This skill helps you generate and maintain OpenAPI/Swagger specification documents for your project.

## What This Skill Does

1. **Generate OpenAPI Specifications**: Automatically create OpenAPI 3.0+ specification documents from your codebase
2. **Update Existing Specs**: Keep your API documentation in sync with code changes
3. **Validate API Compliance**: Ensure your API implementations match their specifications
4. **Generate API Documentation**: Create human-readable API documentation from specs

## When to Invoke This Skill

Invoke this skill when:
- User asks to create or generate API specifications
- User wants to document their REST API endpoints
- User needs to update existing OpenAPI specs after code changes
- User wants to validate API implementation against specifications
- User mentions "OpenAPI", "Swagger", "API spec", or "API documentation"

## Usage Examples

### Generate a New Specification

```
Generate an OpenAPI specification for my REST API
```

### Update Existing Specification

```
Update the OpenAPI spec to reflect the new user endpoints
```

### Validate API Compliance

```
Check if my API implementation matches the OpenAPI specification
```

## Workflow

1. **Analyze Codebase**: Scan your API routes, controllers, and models
2. **Extract API Information**: Identify endpoints, parameters, request/response schemas
3. **Generate Specification**: Create OpenAPI 3.0+ compliant YAML/JSON document
4. **Validate & Refine**: Ensure specification accuracy and completeness

## Output Format

The skill generates OpenAPI 3.0+ specifications in YAML format by default, including:
- API metadata (title, version, description)
- Server configurations
- Path definitions with operations
- Request/response schemas
- Authentication requirements
- Tags for logical grouping

## Best Practices

- Keep specifications in a dedicated `openspec/` directory
- Version your API specifications alongside your code
- Use descriptive operation IDs and summaries
- Include examples for request/response bodies
- Document all possible error responses
