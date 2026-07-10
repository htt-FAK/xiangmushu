# Changelog

本文件记录项目可追溯的变更历史。格式基于 [Keep a Changelog](https://keepachangelog.com/)，由工程师维护，不作营销修饰。
This file tracks notable changes. Engineer-maintained, factual, terse.

## Recent / Notable

- **d16966a** (2026-07-10) — feat(web-search): replace LLM web search with keyless Firecrawl MCP client.  
  Full replacement of DashScope enable_search / MiMo web_search with a keyless sync Firecrawl MCP client. Removed `web_search` model role end-to-end; added Firecrawl config/env vars; 12 new/rewritten tests.

- **b0499fa** (2026-07-10) — docs: archive firecrawl migration work plan and evidence.  
  Move completed OpenSpec artifacts to archive.

- **63d6c36** (2026-06-17) — feat(frontend): improve mobile navigation and generate running layout.  
  6-tab bottom bar → 4 primary tabs + More sheet; compact active-session banners; responsive Generate page.

- **180dc81** (2026-06-16) — feat: add strict model selection and session termination.  
  `strict_model_selection` on ContentGenerator/ContentAuditor disables fallback chain; `POST /api/generate/sessions/{id}/terminate` endpoint.

- **3d70b70** (2026-06-16) — refactor: split GeneratePage and add shared frontend modules.  
  Monolithic GeneratePage → SetupPanel, RunOverview, OutputList, modals, useGenerationSession.

- **5b3d146** (2026-06-17) — feat: add saved provider key test flow.  
  End-to-end validation for saved API keys.

- **3531a50** (2026-06-15) — Add MiMo provider and tighten model registry seeding.

- **ca8a122** (2026-06-15) — Add model catalog backfill and template analysis persistence.  
  Model registry auto-backfill; template analysis now persists across sessions.

- **550b2f4** (2026-06-17) — fix: persist provider key validation updates.

- **0402b77** (2026-06-16) — fix: clear stale background sessions and fix hook ordering.

- **0a91643** (2026-06-16) — chore: remove legacy Streamlit app and config.  
  Full Streamlit entrypoint and config deleted; FastAPI + React is now the sole frontend.

- **d331460** (2026-06-16) — chore: stop tracking .env and refresh env template.  
  Remove .env from version control to prevent credential leaks; update .env.example with MySQL/COS/SMTP/auth schema.

- **e5bf4bc** (2026-06-06) — feat: data dashboard in financial-terminal style.

- **ee2ef61** (2026-06-06) — feat: add multilingual generation preferences.

- **e882908** (2026-06-11) — AI：生成流程稳定性增强与测试整理。  
  Generation session resume, strict API key validation, knowledge-base format expansion; pytest directory cleanup.

- **fd9dce4** (2026-06-14) — AI：兼容腾讯 COS bucket 域名 endpoint。

## Full history

```
d16966a - 2026-07-10 - feat(web-search): replace LLM web search with keyless Firecrawl MCP client
63d6c36 - 2026-06-17 - feat(frontend): improve mobile navigation and generate running layout
550b2f4 - 2026-06-17 - fix: persist provider key validation updates
df623b7 - 2026-06-17 - fix: track web and audit usage across generation
5b3d146 - 2026-06-17 - feat: add saved provider key test flow
e51bfb1 - 2026-06-17 - fix: expand provider catalog seeds for DeepSeek and MiMo
6be0d59 - 2026-06-16 - fix: reuse provider-aware template key readiness
e8aadf2 - 2026-06-16 - fix: recompute billing summaries from model pricing
0402b77 - 2026-06-16 - fix: clear stale background sessions and fix hook ordering
cbec074 - 2026-06-16 - docs: archive completed OpenSpec changes and update specs
911117b - 2026-06-16 - test: cover strict model selection, terminate, and dashscope chat
3d70b70 - 2026-06-16 - refactor: split GeneratePage and add shared frontend modules
180dc81 - 2026-06-16 - feat: add strict model selection and session termination
0a91643 - 2026-06-16 - chore: remove legacy Streamlit app and config
d331460 - 2026-06-16 - chore: stop tracking .env and refresh env template
de9725f - 2026-06-15 - Fix provider-gated model selection refresh
3531a50 - 2026-06-15 - Add MiMo provider and tighten model registry seeding
61e9627 - 2026-06-15 - Stabilize template analysis history and model selection
ca8a122 - 2026-06-15 - Add model catalog backfill and template analysis persistence
3dc67ac - 2026-06-14 - AI：修复模板分析拦截提示显示
d510e06 - 2026-06-14 - AI：补齐 BYOK 拦截提示中文化
f10f443 - 2026-06-14 - AI：前端错误提示中文化
911d53b - 2026-06-14 - AI：修复 COS 冒烟脚本 MySQL 用户外键
fd9dce4 - 2026-06-14 - AI：兼容腾讯 COS bucket 域名 endpoint
37cf1dc - 2026-06-14 - AI：修复 COS 冒烟脚本直接执行导入路径
5e5abb1 - 2026-06-14 - AI：补齐严格 BYOK 与腾讯 COS 制品存储
c81b5ae - 2026-06-13 - AI：修复路由兜底
df5bc5e - 2026-06-12 - AI：服务发布整理
8ad07f8 - 2026-06-12 - AI：添加MySQL连接配置
7ed6cf4 - 2026-06-11 - AI：额度不足时提示用户切换模型
e882908 - 2026-06-11 - AI：生成流程稳定性增强与测试整理
3ae0696 - 2026-06-11 - AI：提交env配置
0cb314b - 2026-06-10 - AI:前端优化
4c19217 - 2026-06-10 - AI:交互优化P0P1
5ae044d - 2026-06-08 - AI：PDF解析增强MarkItDown
4a1fc2a - 2026-06-08 - AI：安全修复+缓存持久化
bafd711 - 2026-06-08 - AI：输出文件加用户隔离
bcf4fb3 - 2026-06-08 - AI：并发生成提速2.3x
5104a71 - 2026-06-08 - AI：移动端体验优化
ce5ec0c - 2026-06-06 - AI：密码校验+限流+404页面
e5bf4bc - 2026-06-06 - AI：数据面板改金融终端风格
ae882bd - 2026-06-06 - AI：添加管理员数据面板
35e17ba - 2026-06-06 - AI：确认书加加密存储说明
1a267bd - 2026-06-06 - AI：优化验证码邮件为HTML格式
ee2ef61 - 2026-06-06 - AI：添加多语言生成偏好功能
8b4fe2b - 2026-06-06 - AI：修复安全漏洞+路径遍历防护
aa5ac61 - 2026-06-06 - AI：生成前费用确认+lifespan迁移
1547387 - 2026-06-06 - AI：移除数据库文件从git
495e97f - 2026-06-06 - AI：未配APIKey时提醒跳转设置
d726072 - 2026-06-06 - AI：关闭累计费用显示
7c10bb6 - 2026-06-06 - AI：添加计费+自带APIKey功能
8137d98 - 2026-06-06 - AI：知识库文案去技术术语
a66b8a9 - 2026-06-06 - AI：文案改通俗易懂
1fb6687 - 2026-06-06 - AI：生成舱简化+侧栏显示邮箱
1a8bb08 - 2026-06-06 - AI：侧栏副标题改技术描述
3c69d11 - 2026-06-06 - AI：首页改项目介绍+token校验
513fff1 - 2026-06-06 - AI：登录改为邮箱密码直登
465a18b - 2026-06-06 - AI：添加邮箱验证码登录系统
57cadeb - 2026-06-06 - AI：适配新版前端测试
cd6088b - 2026-06-05 - AI：补充空白表格
c046a48 - 2026-06-05 - AI：优化表格理解
21cc299 - 2026-06-05 - AI：完善字体保留
acab6ce - 2026-06-05 - AI：切换qwen3.7
58dddd9 - 2026-06-05 - AI：修复字体保留
9a58a70 - 2026-06-05 - AI：清理本地IDE文件并完善忽略规则
7caebc8 - 2026-06-05 - AI：统一模型路由并切换新版前端
a8541f9 - 2026-06-04 - test: add evaluation loop and clean generated artifacts
1626fc8 - 2026-06-04 - fix frontend API endpoint configuration
666c27d - 2026-06-04 - feat: 新增独立 TypeScript 前端（React + Tailwind + Vite）
3ad641c - 2026-06-04 - feat: 全量召回模式 + template_analyzer章节补全 + guidance_filter
c1b4247 - 2026-05-24 - 最终版
ae1488f - 2026-05-22 - feat: 通用模板回填增强（摘要/创新点表/扫槽合并）
8bba41e - 2026-05-21 - AI:优化
db4bc04 - 2026-05-21 - feat: 模型评分榜与复星网关选型配置
db2edeb - 2026-05-21 - merge: 合并 origin/master（远程第一版/第er版 + 本地优化）
6762ba0 - 2026-05-21 - AI:优化
8182140 - 2026-05-21 - AI:优化
bc81153 - 2026-05-21 - AI:优化
8c15f67 - 2026-05-16 - AI：第er版
d3d18e7 - 2026-05-16 - AI：第一版
064ebfd - 2026-05-15 - AI:新的
dc8971e - 2026-05-15 - fix(chroma): 补交 Chroma 遥测空实现模块
cc3a722 - 2026-05-15 - AI:新的
d270d80 - 2026-05-15 - AI:新的
e7ce5d9 - 2026-05-14 - AI:优化
1e05e7e - 2026-05-14 - AI:优化
20234e5 - 2026-05-14 - feat: 表格上下文与批量生成、向量检索修复、Streamlit 状态区展示
32e9393 - 2026-05-14 - AI:优化
1cf31bf - 2026-05-13 - AI:修改
95db8c6 - 2026-05-09 - Initial commit
```