# Multi-Model Management - Design Document

## Overview

This design document outlines the implementation of multi-model management functionality, enabling users to configure, test, and manage multiple custom AI models for text generation, vision tasks, and embeddings.

## Core Design Principles

1. **User-Friendly**: Simple UI for adding/editing/deleting models
2. **Capability-First**: Automatic capability detection and role assignment
3. **Backward Compatible**: Existing single-model configurations remain functional
4. **Performance**: Efficient testing and caching to avoid repeated API calls

## Architecture

### Data Model

#### New Table: `user_custom_models`

```sql
CREATE TABLE user_custom_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,                    -- User-friendly name
    base_url TEXT NOT NULL,                -- API base URL
    model_id TEXT NOT NULL,                -- Model identifier (can be comma-separated for multiple IDs)
    encrypted_api_key TEXT NOT NULL,       -- Encrypted API key
    capabilities TEXT,                     -- JSON: ["text", "vision", "embedding"]
    assigned_roles TEXT,                   -- JSON: ["text-gen", "vision", "embedding"]
    default_model_id TEXT,                 -- Primary model ID for this entry
    status TEXT DEFAULT 'untested',        -- 'untested', 'tested', 'active'
    last_tested_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

**Migration Strategy:**
- Create new `user_custom_models` table
- Migrate existing `user_custom_audit_models` data:
  ```sql
  INSERT INTO user_custom_models (user_id, name, base_url, model_id, encrypted_api_key, default_model_id, status, created_at)
  SELECT user_id, name, base_url, model_id, encrypted_api_key, model_id, status, created_at
  FROM user_custom_audit_models;
  ```
- Mark old table as deprecated (optional: drop after verification)

### API Design

#### New Endpoints

1. **GET /api/user/custom-models**
   ```json
   // Response:
   {
     "models": [
       {
         "id": 1,
         "name": "Qwen Max",
         "base_url": "https://api.deepseek.com/v1",
         "model_id": "deepseek-chat,deepseek-coder",
         "default_model_id": "deepseek-chat",
         "capabilities": ["text"],
         "assigned_roles": ["text-gen"],
         "status": "tested",
         "last_tested_at": "2026-07-14T10:30:00Z",
         "last_error": null
       }
     ]
   }
   ```

2. **POST /api/user/custom-models** (Create)
   ```json
   // Request:
   {
     "name": "Qwen Max",
     "base_url": "https://api.deepseek.com/v1",
     "model_id": "deepseek-chat,deepseek-coder",
     "api_key": "sk-...",
     "default_model_id": "deepseek-chat"
   }
   // Response: Created model object
   ```

3. **PUT /api/user/custom-models/{id}** (Update)
   ```json
   // Request: (partial update)
   {
     "name": "New Name",
     "assigned_roles": ["text-gen", "vision"]
   }
   ```

4. **DELETE /api/user/custom-models/{id}**
   ```json
   // Response: {"status": "success"}
   ```

5. **POST /api/user/custom-models/{id}/test** (Test capabilities)
   ```json
   // Request:
   {
     "test_types": ["text", "vision", "embedding"]  // Optional, defaults to all
   }
   // Response:
   {
     "id": 1,
     "capabilities": ["text", "embedding"],
     "status": "tested",
     "last_tested_at": "2026-07-14T10:30:00Z",
     "last_error": null,
     "suggested_roles": ["text-gen", "embedding"]
   }
   ```

6. **POST /api/user/custom-models/{id}/assign** (Assign roles)
   ```json
   // Request:
   {
     "assigned_roles": ["text-gen", "vision"],
     "default_model_id": "deepseek-chat"
   }
   ```

### Frontend Architecture

#### New Component: `CustomModelsManager`

```
CustomModelsManager
├── ModelList (display all configured models)
│   ├── ModelCard (per model)
│   │   ├── ModelInfo (name, base_url, model_id)
│   │   ├── CapabilityBadges (text/vision/embedding)
│   │   ├── RoleBadges (assigned roles)
│   │   └── ActionButtons (test/edit/delete)
│   └── AddModelDialog (form for new model)
│       ├── NameInput
│       ├── BaseUrlInput
│       ├── ModelIdInput (comma-separated)
│       ├── ApiKeyInput
│       ├── DefaultModelIdSelect
│       └── TestButton
└── TestResultPanel (show test results)
```

#### Component Responsibilities

1. **CustomModelsManager** (settings page integration)
   - Fetch and display model list
   - Handle add/edit/delete operations
   - Coordinate testing and role assignment

2. **ModelList**
   - Render all configured models as cards
   - Show empty state when no models configured
   - Sort by status (tested > untested) then by name

3. **ModelCard**
   - Display model info (name, base_url, model_id)
   - Show capability badges (green for supported, gray for unsupported)
   - Show role badges (which roles this model is assigned to)
   - Action buttons: Test (triggers test), Edit (opens dialog), Delete (with confirmation)

4. **AddModelDialog**
   - Form fields: name, base_url, model_id (comma-separated for multiple IDs), api_key, default_model_id (select from model_id list)
   - Validation: required fields, URL format, API key format
   - Save button triggers POST /api/user/custom-models
   - Show loading state during save

5. **TestResultPanel**
   - Display test results after testing
   - Show capabilities discovered
   - Show suggested roles
   - Allow user to accept/modify role assignments

### Integration Points

#### Generation Page Integration

Update `GeneratePage.tsx` dropdowns to show custom models:

```typescript
// Fetch custom models
const [customModels, setCustomModels] = useState([]);

useEffect(() => {
  fetch('/api/user/custom-models')
    .then(res => res.json())
    .then(data => setCustomModels(data.models || []));
}, []);

// Filter models by capability for each dropdown
const textModels = filterModelsByCapability(customModels, 'text');
const visionModels = filterModelsByCapability(customModels, 'vision');
const embeddingModels = filterModelsByCapability(customModels, 'embedding');
```

### Performance Considerations

1. **Caching**: Cache model list in localStorage with 5-minute TTL
2. **Testing Optimization**: Only test untested models or when user explicitly requests
3. **Lazy Loading**: Only fetch model list when Settings page or Generation page is accessed

## Backward Compatibility

### Migration Steps

1. **Data Migration** (automatic on first run):
   ```python
   def migrate_custom_models():
       # Check if old table exists
       if not table_exists('user_custom_models'):
           create_table('user_custom_models')
           migrate_from_old_table()
   ```

2. **API Compatibility**:
   - Old endpoints (`/api/user/custom-audit-model`) remain functional
   - New endpoints added alongside old ones
   - Frontend uses new endpoints, old endpoints deprecated

### Breaking Changes

- **Data Model**: Existing `user_custom_audit_models` data will be migrated to new format
- **Frontend**: Old `CustomAuditModelCard` component will be deprecated in favor of `CustomModelsManager`
- **API**: Old endpoints remain available but marked as deprecated

## Testing Strategy

### Unit Tests

1. **Capability Testing Logic**:
   - Test text generation with valid/invalid API key
   - Test vision capability with sample image
   - Test embedding with sample text
   - Error handling for network failures, invalid credentials

2. **Model Management**:
   - CRUD operations (create, read, update, delete)
   - Role assignment and validation
   - Model filtering by capability

3. **API Endpoints**:
   - Test all new endpoints with valid/invalid inputs
   - Test error handling and edge cases

### Integration Tests

1. **End-to-End Flow**:
   - Add new model → test capabilities → assign roles → use in generation
   - Edit existing model → verify updates propagate
   - Delete model → verify cleanup

2. **Migration Test**:
   - Verify old data migrates correctly
   - Verify backward compatibility of old endpoints

### Manual Testing Checklist

- [ ] Add model with single model_id
- [ ] Add model with multiple model_ids (comma-separated)
- [ ] Test capabilities (text, vision, embedding)
- [ ] Assign roles to model
- [ ] Use custom model in generation page
- [ ] Edit existing model
- [ ] Delete model
- [ ] Verify dropdown shows custom models
- [ ] Test backward compatibility (old single-model config still works)

## Security Considerations

1. **API Key Storage**: API keys must be encrypted before storage (Fernet)
2. **Validation**: Validate base_url to prevent SSRF attacks
3. **Rate Limiting**: Limit testing requests to prevent API abuse
4. **Access Control**: Only authenticated users can manage their own models

## Future Considerations

1. **Batch Operations**: Support bulk operations (delete multiple models)
2. **Import/Export**: Import/export model configurations as JSON
3. **Model Templates**: Pre-configured templates for common models (DeepSeek, Qwen, etc.)
4. **Usage Analytics**: Track which models are used most frequently
5. **Cost Estimation**: Show estimated cost per model based on usage

## Success Metrics

1. **User Adoption**: >80% of users configure at least one custom model within first week
2. **Capability Testing**: >90% of models tested successfully
3. **Role Assignment**: >85% of models assigned to appropriate roles
4. **User Satisfaction**: >4.5/5 rating for model management interface
