# 多模型管理 / Multi-Model Management

> **功能版本**: v2.0.0 | **最后更新**: 2026-07-14

---

## 什么是多模型管理？ / What Is Multi-Model Management?

**中文**：多模型管理让你在一个界面里配置、测试、分配多个 OpenAI 兼容的自定义模型。不再局限于单个审核模型，你可以同时接入文本生成、视觉理解、向量嵌入等不同能力的模型，按需分配到写作、审核、嵌入等系统角色。

**English**: Multi-model management lets you configure, test, and assign multiple OpenAI-compatible custom models from a single interface. Instead of being limited to one audit model, you can connect models with different capabilities (text generation, vision, embedding) and assign them to system roles (writing, audit, embedding) as needed.

![settings](../screenshots/custom-models-settings.png)
> *截图占位：UI 定稿后替换为实际截图 / Screenshot placeholder: replace after UI freeze*

---

## 快速开始 / Quick Start

### 添加你的第一个模型 / Add Your First Model

1. **打开设置页** / Open Settings
   进入「设置」页面，找到「自定义模型」区域。
   Navigate to the Settings page and find the "Custom Models" section.

2. **点击「添加模型」** / Click "Add Model"
   填写以下信息：
   Fill in the following:
   - **名称 / Name**：给模型起个容易辨认的名字，例如 "DeepSeek Chat"
   - **Base URL**：OpenAI 兼容接口地址，例如 `https://api.deepseek.com/v1`
   - **Model ID**：模型标识符，多个用逗号分隔，例如 `deepseek-chat,deepseek-coder`
   - **API Key**：你的模型 API 密钥（至少 8 位）
   - **Default Model ID**：（可选）从 Model ID 列表中选择一个作为默认

3. **保存并测试** / Save & Test
   保存后，点击「测试」按钮，系统会自动检测模型的文本、视觉、嵌入能力。
   After saving, click the "Test" button. The system will automatically detect text, vision, and embedding capabilities.

![add-model](../screenshots/add-model-dialog.png)
> *截图占位 / Screenshot placeholder*

---

## 能力测试 / Capability Testing

系统通过向模型发送特定请求来检测能力：
The system detects capabilities by sending targeted requests:

| 能力 / Capability | 测试方式 / Test Method | 超时 / Timeout |
|:---|:---|:---|
| **文本 / Text** | 发送简单文本生成请求 | 30 秒 |
| **视觉 / Vision** | 发送带 base64 小图片的多模态请求 | 60 秒 |
| **嵌入 / Embedding** | 发送 `/embeddings` 请求 | 30 秒 |

**"测试" vs "重新测试"** / **"Test" vs "Re-test"**：
- 如果模型在 5 分钟内已测试过，按钮显示「重新测试」
- 超过 5 分钟或从未测试，按钮显示「测试」
- 后端每次都执行真实测试，缓存仅在前端生效

测试结果会显示每个能力的通过/失败状态、延迟和错误详情。
Test results show pass/fail status, latency, and error details for each capability.

![test-results](../screenshots/test-result-panel.png)
> *截图占位 / Screenshot placeholder*

---

## 角色分配 / Role Assignment

系统有 5 个角色，每个角色对应不同的能力需求：
The system has 5 roles, each with different capability requirements:

| 角色 / Role | 系统用途 / System Use | 需要的能力 / Required Capability |
|:---|:---|:---|
| **text-gen** | 主写作模型（大 LLM） | `text` |
| **vision** | 视觉理解（模板分析等） | `text` + `vision` |
| **embedding** | 向量嵌入（知识库索引） | `embedding` |
| **audit** | 内容审核（质量检查） | `text` |
| **small-llm** | 轻量任务（模板结构分析） | `text` |

**分配方式** / **Assignment**:
- 测试完成后，系统会建议角色（`suggested_roles`），点击「接受建议」一键分配
- 也可以手动选择角色，即使能力未测试也可以分配（会有警告提示）
- 多个模型可以分配到同一个角色，系统使用默认模型或第一个可用模型

---

## 在生成页使用自定义模型 / Using Custom Models on the Generation Page

配置好模型并分配角色后，自定义模型会出现在生成页的模型下拉框中。
After configuring models and assigning roles, custom models appear in the generation page dropdowns.

- 自定义模型显示在内置模型之后，带有 ⚙ 图标和「自定义 / Custom」标记
- 选择自定义模型后，系统使用你自己的 API key 调用，不受平台配额限制
- 如果自定义模型调用失败，系统自动回退到平台默认模型
- 当平台模型配额不足时，系统会推荐有匹配能力的自定义模型作为替代

![generate-dropdown](../screenshots/generate-page-custom-model.png)
> *截图占位 / Screenshot placeholder*

---

## 常见模型配置 / Common Model Configurations

以下是经过测试的常见配置，可直接使用：
Below are tested configurations you can use directly:

| 名称 / Name | Base URL | Model ID | 能力 / Capabilities | 推荐角色 / Suggested Roles |
|:---|:---|:---|:---|:---|
| Qwen Max | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` | text, vision | text-gen, audit |
| Qwen VL Max | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-vl-max` | text, vision | vision |
| DashScope Embedding | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `text-embedding-v3` | embedding | embedding |
| DeepSeek Chat | `https://api.deepseek.com/v1` | `deepseek-chat` | text | text-gen, audit |
| DeepSeek Coder | `https://api.deepseek.com/v1` | `deepseek-coder` | text | text-gen, small-llm |
| MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v1` | text, vision | text-gen, vision |

> [!NOTE]
> Base URL 和 Model ID 可能随服务商更新而变化，请以官方文档为准。
> Base URLs and Model IDs may change as providers update. Check official documentation.

---

## 故障排查 / Troubleshooting

| 错误码 / Error Code | 含义 / Meaning | 建议 / Suggested Fix |
|:---|:---|:---|
| `url_format` | URL 格式无效 | 检查 base_url 是否以 `https://` 开头，无多余空格 |
| `ssrf_rejected` | URL 解析到内网地址 | base_url 必须是公网地址，不支持 localhost 或私有 IP |
| `auth` | API key 无效或过期 | 确认 API key 正确，检查是否过期或被撤销 |
| `network` | 网络连接失败 | 检查网络是否正常，base_url 是否可达 |
| `timeout` | 请求超时 | 模型响应慢，可重试或检查模型服务状态 |
| `model_not_found` | 模型 ID 不存在 | 检查 model_id 拼写，确认模型在服务商处已开通 |
| `bad_response` | 模型返回异常响应 | 可能是模型服务临时故障，稍后重试 |
| `limit_exceeded` | 已达 20 个模型上限 | 删除不用的模型后再添加新模型 |
| `rate_limited` | 请求频率超限 | 等待后重试（创建：10 次/小时，测试：5 次/模型/小时） |
| `api_key_length` | API key 太短 | API key 至少需要 8 个字符 |

---

## 常见问题 / FAQ

### 多个模型能共享同一个角色吗？ / Can multiple models share a role?

**中文**：可以。多个模型可以分配到同一个角色。系统会使用 `default_model_id` 对应的模型，如果没有设置则使用第一个可用模型。

**English**: Yes. Multiple models can be assigned to the same role. The system uses the model matching `default_model_id`, or the first available model if not set.

### 为什么视觉测试失败？ / Why does my vision test fail?

**中文**：视觉测试需要模型支持多模态输入（图片）。纯文本模型（如 deepseek-chat）不支持图片输入，测试会返回 422 错误。这是正常的，不代表模型有问题。

**English**: Vision testing requires the model to support multimodal input (images). Text-only models (like deepseek-chat) don't support image input and will return a 422 error. This is normal and doesn't indicate a problem with the model.

### 20 个模型上限是怎么回事？ / What's the 20-model limit?

**中文**：每个用户最多可以配置 20 个自定义模型，这是为了防止滥用。如果达到上限，需要删除不用的模型后才能添加新模型。

**English**: Each user can configure up to 20 custom models to prevent abuse. If you hit the limit, delete unused models before adding new ones.

### 如何迁移旧的单模型配置？ / How do I migrate my old single-model config?

**中文**：系统会在启动时自动迁移旧的 `user_custom_audit_models` 数据到新的 `user_custom_models` 表。你不需要手动操作。迁移后，旧的审核模型会保留在新表中，状态为 `validated`，并自动分配 `audit` 角色。详见 [迁移指南](../migration-guide-v2.md)。

**English**: The system automatically migrates old `user_custom_audit_models` data to the new `user_custom_models` table on startup. No manual action needed. After migration, your old audit model is preserved with `validated` status and assigned the `audit` role. See the [migration guide](../migration-guide-v2.md).

### 自定义模型会消耗平台配额吗？ / Do custom models use platform quota?

**中文**：不会。自定义模型使用你自己的 API key，不受平台配额限制。当平台模型配额不足时，系统还会推荐自定义模型作为替代方案。

**English**: No. Custom models use your own API key and are not subject to platform quota limits. When platform model quota runs low, the system even recommends custom models as alternatives.

---

## 相关文档 / Related Documentation

- [API 参考 / API Reference](../api-custom-models.md)
- [迁移指南 / Migration Guide](../migration-guide-v2.md)
- [测试与验收 / Testing & Acceptance](../测试与验收.md)
