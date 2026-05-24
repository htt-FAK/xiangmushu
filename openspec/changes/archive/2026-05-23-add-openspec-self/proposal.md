## Why

openspec 目录结构存在于项目中，但框架本身没有中文的自描述文档。新成员和 AI 助手进入项目时，需要一份中文说明来快速理解：目录结构、文件格式、书写约定和工作流程。

## What Changes

- 新增 capability `openspec-self`：openspec 框架的中文自描述规范
- 在 `openspec/specs/openspec-self/spec.md` 放置完整的自描述规范
- 在变更目录内嵌 spec 副本供评审

## Capabilities

### New Capabilities

- `openspec-self`：OpenSpec 规范驱动开发框架的自描述规范，覆盖框架定位、目录结构、config.yaml 格式、spec 文件格式、变更提案文件格式、语言约定、变更与规范关联、AI 助手协作。

### Modified Capabilities

无

## Impact

- **代码**：无代码变更，仅新增 openspec/specs/openspec-self/spec.md
- **依赖**：无
- **配置**：无
- **文档/测试**：新增的 spec 本身就是 openspec 框架的文档
