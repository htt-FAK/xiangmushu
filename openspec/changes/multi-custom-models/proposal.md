## Why

当前系统仅支持单个自定义审核模型配置，无法满足用户需要配置多个模型（如不同的文本模型、视觉模型、embedding 模型）并测试其多模态能力的需求。用户需要类似 Cursor/opencode 的模型管理界面，支持批量配置、能力测试和智能分配。

## What Changes

- **数据模型升级**：将 `user_custom_audit_models` 表改为支持多模型配置，每个模型独立记录（name、base_url、model_id、api_key、capabilities、assigned_roles）
- **新增能力测试功能**：配置时自动测试模型的文本、视觉、embedding 能力，根据测试结果建议模型分配
- **新增模型管理界面**：统一的添加/删除/编辑/测试界面，支持多模型列表管理
- **下拉栏集成**：在生成页面（5个区域）的下拉栏显示所有已配置的模型，根据能力自动过滤
- **API 变更**：扩展 `/api/user/custom-audit-model` 为 CRUD 接口，新增能力测试端点
- **BREAKING**：现有的单模型配置将迁移为多模型格式，旧数据需迁移或兼容处理

## Capabilities

### New Capabilities
- `multi-model-management`: 多自定义模型的 CRUD 管理（添加、删除、编辑）、模型列表展示、模型能力测试、模型角色分配
- `model-capability-testing`: 自动测试模型的文本、视觉、embedding 能力，返回能力标签和分配建议

### Modified Capabilities
- `custom-audit-model`: 从单模型升级为多模型支持，数据模型、API 接口、前端界面全面升级
- `generation-page`: 生成页面的下拉栏需集成多模型选择，根据模型能力自动过滤可用模型

## Impact

- **后端 API**：
  - 扩展 `/api/user/custom-audit-model` 为 RESTful CRUD（GET list, POST create, PUT update, DELETE one）
  - 新增 `/api/user/custom-audit-model/test` 端点用于测试模型能力
  - 新增 `/api/user/custom-audit-model/assign` 端点用于分配模型角色
- **数据库**：
  - 迁移 `user_custom_audit_models` 表，增加 `capabilities`（JSON）、`assigned_roles`（JSON）、`is_active`（BOOLEAN）字段
  - 或创建新表 `user_custom_models` 支持通用模型管理
- **前端**：
  - 新增 `CustomModelsManager` 组件（模型列表 + 添加对话框 + 能力测试 UI）
  - 更新 `SettingsPage` 集成模型管理组件
  - 更新生成页面下拉栏，根据模型能力自动过滤
- **依赖**：可能需要新增图标库（如 lucide-react）
