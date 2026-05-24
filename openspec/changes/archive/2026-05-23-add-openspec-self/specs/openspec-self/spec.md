# openspec-self

OpenSpec 规范驱动开发框架的自描述规范。本文档定义 openspec 系统本身的用途、目录结构、文件格式、书写约定和工作流程。

## 需求

### 需求：框架定位

OpenSpec 是一个轻量级的规范驱动开发框架，用 Markdown 文件管理项目的能力规范（Specs）和变更提案（Changes），无需额外数据库或服务端。

- **Specs**（规范）：定义项目应具备的稳定能力，每个 capability 一份独立的规范文档。
- **Changes**（变更）：记录对项目的一次改动提案，包含提案理由、设计决策、实施任务，并可引用已有的 specs。
- **OpenSpec 本身也需有自描述规范**，确保团队成员和 AI 助手能快速理解框架的用法。

#### 场景：新成员理解项目规范

- **前提**：一个不熟悉 openspec 的开发者或 AI 助手进入项目。
- **操作**：阅读 `openspec/specs/openspec-self/spec.md`。
- **结果**：可在 5 分钟内理解目录结构、文件格式、工作流程，并开始编写新的 spec 或变更提案。

### 需求：目录结构

openspec 根目录 `openspec/` 下包含三个部分：

| 路径 | 类型 | 用途 |
|------|------|------|
| `config.yaml` | 配置文件 | 全局 schema 和项目上下文声明 |
| `specs/` | 目录 | 存放所有能力规范，每个 capability 一个子目录 |
| `changes/` | 目录 | 存放变更提案，按日期归档 |

`specs/` 下每个子目录的命名规则、`changes/` 下每个变更的目录结构，见下文约定。

#### 场景：列出所有已定义的能力

- **前提**：`openspec/specs/` 下有多个子目录。
- **操作**：遍历 `openspec/specs/` 的子目录。
- **结果**：每个子目录名称即为一个 capability 标识符，其 `spec.md` 文件包含该 capability 的完整需求定义。

### 需求：config.yaml 格式

`openspec/config.yaml` 是框架的顶层配置文件：

```yaml
schema: spec-driven
context: |
  可选的项目上下文说明，如技术栈、编码约定、领域知识等。
rules:
  - proposal: "可选的逐件规则，如：提案不超过 500 字"
  - tasks: "任务拆分为 2 小时内可完成的小块"
```

- `schema`：固定为 `spec-driven`。
- `context`（可选）：项目上下文描述，展示给 AI 助手用于理解项目背景。
- `rules`（可选）：针对具体 artifact 的自定义规则。

#### 场景：AI 助手读取项目上下文

- **前提**：AI 助手需要生成符合项目风格的代码或文档。
- **操作**：读取 `config.yaml` 的 `context` 字段。
- **结果**：AI 助手获得技术栈、编码风格、命名约定等背景信息。

### 需求：Spec 规范文件格式

每个 capability 规范位于 `openspec/specs/<capability-name>/spec.md`。

**命名规则**：capability 名称使用小写字母、数字和连字符（kebab-case），如 `hello-page`、`chapter-paragraph-fill`。

**spec.md 文件结构**：

```markdown
# <capability-name>

<一段中文描述，说明该 capability 的职责和范围>

## 需求

### 需求：<需求标题>

<用 SHALL 陈述的需求正文>

#### 场景：<场景标题>

- **前提**（可选）：场景的初始条件
- **操作**：触发动作
- **结果**：期望的系统行为或输出

#### 场景：<另一个场景>

...
```

- 标题使用中文（capability 名称本身可用英文 kebab-case）。
- 每个需求条目使用 `SHALL`（英文）作为规范关键词，表示强制性要求。
- 每个需求下可含一个或多个场景（Scenario），用 Given-When-Then 的变体格式描述。
- 场景是验证需求的依据：测试和验收标准应能覆盖每个场景。

#### 场景：AI 助手按规范实现

- **前提**：`specs/chapter-paragraph-fill/spec.md` 定义了摘要章节的填写规则。
- **操作**：AI 助手读取 spec.md 并实现对应的 filler 逻辑。
- **结果**：实现的行为与 spec.md 中的每个场景描述一致。

#### 场景：新人添加新的 capability

- **前提**：项目需要新增一个 OCR 图像提取能力。
- **操作**：在 `openspec/specs/` 下创建 `ocr-extract/` 目录和 `spec.md`。
- **结果**：`openspec/specs/ocr-extract/spec.md` 包含该能力的完整需求文档。

### 需求：变更提案文件格式

变更提案位于 `openspec/changes/archive/<date>-<change-name>/` 目录下。

**命名规则**：`<YYYY-MM-DD>-<英文-kebab-case-描述>`，如 `2026-05-22-add-hello-page`。

每个变更目录包含以下文件：

| 文件 | 必填 | 用途 |
|------|------|------|
| `.openspec.yaml` | 是 | 元数据：schema 和创建日期 |
| `proposal.md` | 是 | 为什么改、改什么、影响范围 |
| `design.md` | 是 | 上下文、目标/非目标、决策、风险、迁移计划 |
| `tasks.md` | 是 | 具体的实施任务列表（含复选框） |
| `specs/` | 否 | 本次变更新增或修改的 spec 文件子目录 |

**.openspec.yaml 格式**：

```yaml
schema: spec-driven
created: YYYY-MM-DD
```

**proposal.md 结构**：

```markdown
## Why

<变更动机：当前有什么问题或不足>

## What Changes

<变更内容概述：改了哪些文件、新增了什么、移除了什么>

## Capabilities

### New Capabilities

- `<capability-name>`：<简短描述>

### Modified Capabilities

- `<capability-name>`：<修改描述>

## Impact

- **代码**：涉及的文件和模块
- **依赖**：新增或删除的依赖
- **配置**：环境变量或配置项变更
- **文档/测试**：需要同步更新的文档或测试
```

**design.md 结构**：

```markdown
## Context

<当前系统状态和约束>

## Goals / Non-Goals

**Goals:**
- <实施目标>

**Non-Goals:**
- <明确不做的范围>

## Decisions

<逐一列出关键设计决策及其理由>

## Risks / Trade-offs

<风险和权衡>

## Migration Plan

<部署、回滚、数据迁移方案>

## Open Questions

<待解决的问题——为空即无>
```

**tasks.md 结构**：

```markdown
## <序号>. <标题>

- [ ] <任务项>
- [ ] <任务项>
```

#### 场景：提交一个新功能变更

- **前提**：开发者需要实现一个"OCR 提取"新功能。
- **操作**：创建 `2026-05-23-add-ocr-extract/` 目录，写入 `.openspec.yaml`、`proposal.md`、`design.md`、`tasks.md`，并在 `specs/` 子目录放置对应的 spec。
- **结果**：变更提案结构完整，团队成员可评审提案，AI 助手可据此实施任务。

#### 场景：变更被否决或废弃

- **前提**：某个变更提案不再需要。
- **操作**：直接在 `tasks.md` 开头标注 `**状态：已废弃**`，保留文件作为历史记录。
- **结果**：目录不删除，保留审计线索。

### 需求：语言约定

openspec 框架的语言策略：

- **spec.md 标题和描述**：使用中文，确保团队成员无需翻译即可理解。
- **需求正文的规范关键词**：使用英文 `SHALL`，这是需求工程的惯用关键词，与语言无关。
- **场景描述**：中文为主，必要时可混用英文字段名（如 `WHEN`、`THEN`）。
- **变更提案文件**：`proposal.md`、`design.md`、`tasks.md` 使用中文。
- **目录和文件名**：使用英文 kebab-case，避免跨平台编码问题。
- **代码引用**：保持原始英文（如函数名、类名、配置键名）。

#### 场景：中英混杂的场景描述

- **前提**：一个 spec 中的场景段落使用了中文描述和英文 WHEN/THEN 关键词。
- **结果**：文件被正确解析，团队成员和 AI 助手均能理解。

### 需求：变更与规范的关联

变更提案可以通过两种方式关联规范：

1. **直接引用**：在 `proposal.md` 的 `Capabilities` 字段中列出 New/Modified Capabilities 名称。
2. **内嵌 specs**：在变更目录下的 `specs/` 子目录中放置新增或修改的 spec 文件，评审通过后再合并到 `openspec/specs/`。

#### 场景：变更引入新的规范

- **前提**：`2026-05-22-add-hello-page` 变更引入了 `hello-page` capability。
- **操作**：变更目录 `specs/hello-page/spec.md` 在提案阶段编写，评审通过后合并到 `openspec/specs/hello-page/`。
- **结果**：规范的变更历史可通过对应的变更目录追溯。

### 需求：AI 助手协作

openspec 的设计目标之一是便于 AI 助手理解和使用。

- AI 助手首次进入项目时，应优先读取 `openspec/specs/openspec-self/spec.md` 了解框架。
- 实施变更时，AI 助手应读取对应的 `spec.md` 和 `design.md`，确保实现与需求和设计一致。
- AI 助手生成代码后，应在 `tasks.md` 中更新任务状态（将 `[ ]` 改为 `[x]`）。

#### 场景：AI 助手按规范实施

- **前提**：AI 助手收到一个实施任务，任务指向某个变更目录。
- **操作**：AI 助手读取该变更的 `proposal.md`、`design.md`、`tasks.md` 和引用的 `spec.md`。
- **结果**：AI 助手按设计和需求实施代码，完成后更新 `tasks.md` 中的复选框。

### 需求：框架不受现有功能影响

新增或修改 openspec 框架本身的规范或结构，不应影响项目其他 capabilites 的实现。

#### 场景：更新 openspec-self 规范

- **前提**：需要修改 openspec 框架的自描述规范。
- **操作**：按变更提案流程创建新的变更目录，通过评审后更新 `openspec/specs/openspec-self/spec.md`。
- **结果**：只有 openspec-self 规范发生变化，不影响 `hello-page`、`chapter-paragraph-fill` 等其他规范。
