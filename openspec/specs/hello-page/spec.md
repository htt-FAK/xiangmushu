# hello-page

Streamlit 应用首页：欢迎说明、推荐工作流与环境状态只读摘要。

## Requirements

### Requirement: Home tab is the first main tab

The application SHALL expose a main tab labeled「首页」as the first tab before「知识库管理」「模板配置」「生成预览」.

#### Scenario: User opens the app

- **WHEN** the Streamlit app loads the main tab bar
- **THEN** the first visible tab label is「首页」

### Requirement: Home tab shows product overview and workflow

The home tab SHALL display a short product description and a numbered recommended workflow that references the three existing feature tabs.

#### Scenario: User reads onboarding on home tab

- **WHEN** the user selects the「首页」tab
- **THEN** the UI shows what the product does and ordered steps: configure KB → ingest in「知识库管理」→ template in「模板配置」→ generate in「生成预览」

### Requirement: Home tab shows read-only environment summary

The home tab SHALL display read-only status for embedding and chat API configuration, the active knowledge base identifier, and the current generation intensity mode without duplicating sidebar controls.

#### Scenario: APIs configured

- **WHEN** `embedding_llm_configured()` and `chat_llm_configured()` return true
- **THEN** the home tab indicates both channels are ready

#### Scenario: Missing embedding key

- **WHEN** `embedding_llm_configured()` returns false
- **THEN** the home tab shows a warning that ingestion requires DashScope/OpenAI compatible key

#### Scenario: Missing chat key

- **WHEN** `chat_llm_configured()` returns false
- **THEN** the home tab shows a warning that generation requires Fosun gateway or DashScope key

### Requirement: Core generation pipeline unchanged

Adding the home tab SHALL NOT change retrieval, generation routing, template analysis, or Word fill behavior in other tabs.

#### Scenario: User generates from preview tab

- **WHEN** the user completes generation from「生成预览」without visiting「首页」
- **THEN** generation behavior matches the pre-change application
