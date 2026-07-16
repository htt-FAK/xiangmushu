# 智能文档生成系统 · docs 目录

本目录包含项目公开文档与真实模板，作为 GitHub showcase 的配套资源。

---

## 📚 用户向文档

| 文件 | 内容 |
|:---|:---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 系统技术架构（组件图、数据流、模型路由表、Firecrawl 联网补料流程、持久化层与部署说明） |
| [api-custom-models.md](./api-custom-models.md) | 自定义模型接入指南（OpenAI SDK 兼容接口注册与路由） |
| [features/multi-model.md](./features/multi-model.md) | 多模型功能说明（MAIN_WRITER / FAST_WRITER / VISION / AUDIT 角色与降级链） |
| [mysql-storage-setup.md](./mysql-storage-setup.md) | MySQL 持久化生产环境配置 |
| [模型选型建议.md](./模型选型建议.md) | 各角色默认模型选择与成本权衡 |
| [模型评分榜.md](./模型评分榜.md) | 不同模型在不同任务类型上的评测记录 |
| [测试与验收.md](./测试与验收.md) | 测试策略、离线冒烟用例矩阵、手工验收要点 |
| [模板与职责.md](./模板与职责.md) | 各模块与模板的关系说明 |
| [智能体模型运作流程与框架.md](./智能体模型运作流程与框架.md) | 模型分工、数据流与路由逻辑完整说明 |
| [动态模板上传和自定义数据库.md](./动态模板上传和自定义数据库.md) | 用户侧动态模板与知识库管理能力 |

## 📐 真实模板素材

| 文件 | 用途 |
|:---|:---|
| `2.1.2024级广东理工学院创新计划书参考模板（通用）.docx` | 真实创新创业计划书模板，被 `scripts/showcase_pipeline.py` 和 `scripts/real_llm_generation.py` 用作端到端验收素材 |
| `2.1.2024级广东理工学院创新计划书参考模板（通用）.doc` | 上述模板的原版 OLE 格式（LibreOffice 转换后生成 .docx） |

## 🖼️ screenshots/

README 引用的界面截图（01-06 PNG），覆盖：
- 主页底部导航
- 生成页空闲态
- 更多选项
- 移动端生成中
- 移动端生成完整流程
- 桌面端生成

## 🗂️ features/

子功能专题文档。目前包含：
- `multi-model.md` — 多模型专题

## 🗃️ _internal/ — 内部归档

**不在主 README 公开展示的内部文档**，包含：
- `Ace第二阶段验收用例.md` — 阶段验收内部用例
- `DEPLOY_AFTER_DESIGN_ROLLOUT.md` — 设计回滚后部署文档
- `migration-guide-v2.md` — v2 数据迁移指南

这些文档保留用于项目追溯，但不作为 showcase 的一部分。详见 [_internal/README.md](_internal/README.md)。

---

## 📖 推荐阅读顺序

**新来者**：
1. [ARCHITECTURE.md](./ARCHITECTURE.md) — 全局视角
2. [智能体模型运作流程与框架.md](./智能体模型运作流程与框架.md) — 核心生成流程
3. [测试与验收.md](./测试与验收.md) — 跑一次 `smoke_test_models.py --offline` 验证本地环境

**只关心部署**：[mysql-storage-setup.md](./mysql-storage-setup.md)

**只关心模型**：[模型选型建议.md](./模型选型建议.md) + [模型评分榜.md](./模型评分榜.md)
