## Context

项目已有 openspec 框架（`openspec/` 目录），包含：

- `config.yaml`：顶层配置
- `specs/`：两个已有 capability（`hello-page`、`chapter-paragraph-fill`）
- `changes/`：两个已归档变更

openspec 框架本身没有文档说明其用途和用法。需要一份用中文编写的自描述规范，让新人和 AI 助手能快速上手。

## Goals / Non-Goals

**Goals:**

- 创建 `openspec/specs/openspec-self/spec.md`，完整描述 openspec 框架
- 覆盖：框架定位、目录结构、config.yaml 格式、spec 文件格式、变更提案文件格式、语言约定、变更与规范关联、AI 助手协作
- 使用中文编写，与项目中已有的 spec 语言风格一致

**Non-Goals:**

- 不修改 openspec 目录结构本身
- 不动已有的 spec 内容（hello-page、chapter-paragraph-fill）
- 不改 config.yaml
- 不改任何 Python 代码

## Decisions

1. **命名 openspec-self**：使用英文 kebab-case（`openspec-self`），与已有 capability 命名风格一致；"self" 表示框架自描述。

2. **中文正文 + 英文 SHALL**：正文描述使用中文，需求约束使用英文 `SHALL`，与项目中其他 spec 的中英混合风格保持一致。

3. **场景覆盖而非指令式**：每个需求下使用 Scenario 描述（前提-操作-结果），便于测试人员日后据此编写验收用例。

4. **变更目录包含 specs 副本**：在变更目录 `specs/openspec-self/spec.md` 保留 spec 副本，评审通过后再同步到 `openspec/specs/`。这样做的好处：
   - 变更提案的审议过程可引用具体内容
   - 保持与已有变更目录结构一致（如 `2026-05-22-add-hello-page/specs/`）

5. **不修改已有规范**：openspec-self 只描述框架本身，不重新定义或修改其他 capability 的规范。

## Risks / Trade-offs

- **[低风险] 自描述循环**：openspec-self 用 openspec 的格式描述 openspec 自身，理论上可无限递归。实际无风险，因为本文档是终端的 spec，不要求 openspec-self 下有子规范。
- **[低风险] 未来框架结构变化**：如果 openspec 目录结构未来发生调整，需要同步更新本规范。这不是问题，反而正是 openspec 的意图——先改 spec，再改实现。

## Migration Plan

创建目录和文件后立即生效，无需迁移。

## Open Questions

无。
