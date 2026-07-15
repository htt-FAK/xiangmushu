import type {
  AnalyzeResult,
  ApiKeyValidationResult,
  ApiKeyStatus,
  AssignRolesResponse,
  BillingSummary,
  CreateCustomModelRequest,
  CustomAuditModelError,
  CustomAuditModelStatus,
  CustomModel,
  CustomModelError,
  CustomModelsListResponse,
  GenerateEvent,
  GenerateParams,
  HistoryArticlesResponse,
  GenerationSessionEnvelope,
  GenerationSessionStartResult,
  HistoryArticle,
  KnowledgeBase,
  KnowledgeSourceStats,
  ModelOptionsMap,
  TemplateAnalysisEvent,
  TemplateAnalysisSessionEnvelope,
  TemplateAnalysisSessionStartResult,
  TemplateItem,
  TestResult,
  UpdateCustomModelRequest,
  UploadResult,
  UserPreferences,
} from "./types";
import { apiUrl } from "./apiBase";
import { buildAuthHeaders, clearStoredToken } from "./auth";
import { parseApiErrorMessage } from "./errors";

const TOKEN_EXPIRED_MESSAGE = "登录已过期，请重新登录";

/**
 * Centralized 401 handling: clear the token and redirect to the auth page
 * (unless we are already there). Used by every authenticated request path.
 */
function handleUnauthorized() {
  clearStoredToken();
  const currentPath = window.location.pathname;
  if (!currentPath.startsWith("/auth")) {
    window.location.href = `/auth?next=${encodeURIComponent(currentPath)}`;
  }
}

/**
 * Perform an authenticated fetch with merged auth headers and shared 401
 * handling. Returns the raw Response for callers that need streaming/blobs.
 */
export async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      ...buildAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 401) {
    handleUnauthorized();
    throw new Error(TOKEN_EXPIRED_MESSAGE);
  }
  return response;
}

/**
 * JSON request helper.
 * - allowError=false (default): throws on non-OK with a translated message.
 * - allowError=true: returns the parsed body even on error status (used for
 *   validate/start-session endpoints that carry meaningful error payloads).
 */
async function request<T>(
  path: string,
  init?: RequestInit,
  options?: { allowError?: boolean },
): Promise<T> {
  const response = await authedFetch(path, init);
  if (options?.allowError) {
    const text = await response.text();
    if (!text) return {} as T;
    return JSON.parse(text) as T;
  }
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${response.status}`));
  }
  return (await response.json()) as T;
}

function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init);
}

function requestJsonAllowError<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init, { allowError: true });
}

/**
 * Generic Server-Sent-Events reader. Performs an authenticated request, then
 * decodes the body stream, splits on the SSE record separator ("\n\n"), and
 * dispatches each `data:` payload as a parsed JSON event.
 */
async function streamSSE<TEvent>(
  path: string,
  onEvent: (event: TEvent) => void,
  init?: RequestInit,
): Promise<void> {
  const response = await authedFetch(path, init);
  if (!response.ok || !response.body) {
    const message = await response.text();
    throw new Error(parseApiErrorMessage(message, `HTTP ${response.status}`));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const eventText of events) {
      const line = eventText.split("\n").find((item) => item.startsWith("data:"));
      if (!line) continue;
      onEvent(JSON.parse(line.slice(5).trim()) as TEvent);
    }
  }
}

export async function fetchTemplates(): Promise<TemplateItem[]> {
  const data = await requestJson<{ templates: TemplateItem[] }>("/api/template/list");
  return data.templates ?? [];
}

export async function analyzeTemplate(file: File, visionModel?: string, plannerModel?: string): Promise<AnalyzeResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("vision_model", visionModel ?? "");
  form.append("planner_model", plannerModel ?? "");
  form.append("force_refresh", "true");
  return requestJson<AnalyzeResult>("/api/template/analyze", {
    method: "POST",
    body: form,
  });
}

export async function reanalyzeTemplate(template: string, visionModel?: string, plannerModel?: string): Promise<AnalyzeResult> {
  const form = new FormData();
  form.append("template", template);
  form.append("vision_model", visionModel ?? "");
  form.append("planner_model", plannerModel ?? "");
  return requestJson<AnalyzeResult>("/api/template/reanalyze", {
    method: "POST",
    body: form,
  });
}

export async function deleteTemplate(template: string): Promise<{ ok: boolean; template: string }> {
  const form = new FormData();
  form.append("template", template);
  return requestJson<{ ok: boolean; template: string }>("/api/template/delete", {
    method: "POST",
    body: form,
  });
}

export async function startTemplateAnalysisSession(
  file: File,
  visionModel?: string,
  plannerModel?: string,
  forceRefresh = true,
): Promise<TemplateAnalysisSessionStartResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("vision_model", visionModel ?? "");
  form.append("planner_model", plannerModel ?? "");
  form.append("force_refresh", String(forceRefresh));
  return requestJsonAllowError<TemplateAnalysisSessionStartResult>("/api/template/analyze/sessions", {
    method: "POST",
    body: form,
  });
}

export async function startTemplateReanalysisSession(
  template: string,
  visionModel?: string,
  plannerModel?: string,
  forceRefresh = true,
): Promise<TemplateAnalysisSessionStartResult> {
  const form = new FormData();
  form.append("template", template);
  form.append("vision_model", visionModel ?? "");
  form.append("planner_model", plannerModel ?? "");
  form.append("force_refresh", String(forceRefresh));
  return requestJsonAllowError<TemplateAnalysisSessionStartResult>("/api/template/reanalyze/sessions", {
    method: "POST",
    body: form,
  });
}

export async function fetchActiveTemplateAnalysisSession(): Promise<TemplateAnalysisSessionEnvelope> {
  return requestJson<TemplateAnalysisSessionEnvelope>("/api/template/analyze/sessions/active");
}

export async function fetchTemplateAnalysisSession(sessionId: string): Promise<TemplateAnalysisSessionEnvelope> {
  return requestJson<TemplateAnalysisSessionEnvelope>(`/api/template/analyze/sessions/${encodeURIComponent(sessionId)}`);
}

export async function fetchKnowledgeBases(): Promise<KnowledgeBase[]> {
  const data = await requestJson<KnowledgeBase[]>("/api/kb/list");
  return Array.isArray(data) ? data : [];
}

export async function createKnowledgeBase(label: string, slug?: string) {
  const form = new FormData();
  form.append("label", label);
  form.append("slug", slug ?? "");
  return requestJson<{ ok: boolean; slug?: string; error?: string }>("/api/kb/create", {
    method: "POST",
    body: form,
  });
}

export async function deleteKnowledgeBase(slug: string) {
  const form = new FormData();
  form.append("slug", slug);
  return requestJson<{ ok: boolean; error?: string }>("/api/kb/delete", {
    method: "POST",
    body: form,
  });
}

export async function fetchKnowledgeSources(slug: string): Promise<KnowledgeSourceStats> {
  return requestJson<KnowledgeSourceStats>(`/api/kb/sources?slug=${encodeURIComponent(slug)}`);
}

export async function uploadKnowledgeDocuments(
  slug: string,
  files: File[],
): Promise<UploadResult[]> {
  const form = new FormData();
  form.append("slug", slug);
  files.forEach((file) => form.append("files", file));
  const data = await requestJson<{ results: UploadResult[] }>("/api/kb/upload", {
    method: "POST",
    body: form,
  });
  return data.results ?? [];
}

export async function removeKnowledgeSource(slug: string, source: string) {
  const form = new FormData();
  form.append("slug", slug);
  form.append("source", source);
  return requestJson<{ ok: boolean }>("/api/kb/remove-source", {
    method: "POST",
    body: form,
  });
}

export async function fetchApiKeyStatus(): Promise<ApiKeyStatus> {
  return requestJson<ApiKeyStatus>("/api/user/apikey");
}

export async function validateApiKey(apiKey: string, providerCode = "dashscope"): Promise<ApiKeyValidationResult> {
  return requestJsonAllowError<ApiKeyValidationResult>("/api/user/apikey/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, provider_code: providerCode }),
  });
}

export async function saveApiKey(apiKey: string, providerCode = "dashscope"): Promise<ApiKeyStatus & { ok: boolean; validation?: ApiKeyValidationResult }> {
  return requestJson<ApiKeyStatus & { ok: boolean; validation?: ApiKeyValidationResult }>("/api/user/apikey", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, provider_code: providerCode }),
  });
}

export async function testApiKey(providerCode = "dashscope"): Promise<ApiKeyStatus & { ok: boolean; validation?: ApiKeyValidationResult }> {
  return requestJsonAllowError<ApiKeyStatus & { ok: boolean; validation?: ApiKeyValidationResult }>("/api/user/apikey/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_code: providerCode }),
  });
}

export async function deleteApiKey(providerCode = "dashscope"): Promise<ApiKeyStatus & { ok: boolean }> {
  return requestJson<ApiKeyStatus & { ok: boolean }>(`/api/user/apikey?provider_code=${encodeURIComponent(providerCode)}`, {
    method: "DELETE",
  });
}

export async function fetchModelOptions(): Promise<ModelOptionsMap> {
  return requestJson<ModelOptionsMap>("/api/user/model-options");
}

export async function fetchUserPreferences(): Promise<UserPreferences> {
  return requestJson<UserPreferences>("/api/user/preferences");
}

export async function updateUserPreferences(data: {
  language?: string;
  model_choices?: Record<string, string>;
}): Promise<UserPreferences> {
  return requestJson<UserPreferences>("/api/user/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function saveUserPreferences(language: UserPreferences["language"]): Promise<UserPreferences> {
  return updateUserPreferences({ language });
}

export async function fetchBillingSummary(): Promise<BillingSummary> {
  return requestJson<BillingSummary>("/api/billing/summary");
}

export const ADMIN_FORBIDDEN = "ADMIN_FORBIDDEN" as const;

/**
 * Fetch admin dashboard stats. Throws an Error whose message is
 * `ADMIN_FORBIDDEN` when the server denies access (HTTP 403) so the page can
 * render its dedicated forbidden state.
 */
export async function fetchAdminStats<T>(): Promise<T> {
  const response = await authedFetch("/api/admin/stats");
  if (response.status === 403) {
    throw new Error(ADMIN_FORBIDDEN);
  }
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${response.status}`));
  }
  return (await response.json()) as T;
}

export async function fetchHistoryArticles(params?: {
  query?: string;
  status?: "all" | "completed" | "review" | "failed";
}): Promise<HistoryArticlesResponse> {
  const search = new URLSearchParams();
  if (params?.query) search.set("query", params.query);
  if (params?.status) search.set("status_filter", params.status);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<HistoryArticlesResponse>(`/api/history/articles${suffix}`);
}

export function downloadUrl(path: string) {
  return apiUrl(path);
}

export async function handleDownload(path: string) {
  const response = await authedFetch(path);
  if (!response.ok) throw new Error("下载失败，请稍后重试");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = path.split("/").pop() || "document.docx";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function streamGenerate(
  params: GenerateParams,
  onEvent: (event: GenerateEvent) => void,
  signal?: AbortSignal,
) {
  const form = new FormData();
  form.append("slug", params.slug);
  form.append("template", params.template);
  form.append("custom_instructions", params.customInstructions ?? "");
  form.append("word_limit", String(params.wordLimit));
  form.append("top_k", String(params.topK));
  form.append("max_distance", String(params.maxDistance));
  form.append("enable_web", String(params.enableWeb));
  form.append("use_stream", String(params.useStream));
  form.append("enable_audit", String(params.enableAudit));
  form.append("enable_visual_audit", String(params.enableVisualAudit));
  if (params.format_overrides) {
    form.append("format_overrides", params.format_overrides);
  }

  return streamSSE<GenerateEvent>("/api/generate", onEvent, {
    method: "POST",
    body: form,
    signal,
  });
}

export async function startGenerateSession(params: GenerateParams): Promise<GenerationSessionStartResult> {
  const form = new FormData();
  form.append("slug", params.slug);
  form.append("template", params.template);
  form.append("custom_instructions", params.customInstructions ?? "");
  form.append("word_limit", String(params.wordLimit));
  form.append("top_k", String(params.topK));
  form.append("max_distance", String(params.maxDistance));
  form.append("enable_web", String(params.enableWeb));
  form.append("use_stream", String(params.useStream));
  form.append("enable_audit", String(params.enableAudit));
  form.append("enable_visual_audit", String(params.enableVisualAudit));
  if (params.format_overrides) {
    form.append("format_overrides", params.format_overrides);
  }

  return requestJsonAllowError<GenerationSessionStartResult>("/api/generate/sessions", {
    method: "POST",
    body: form,
  });
}

export async function fetchActiveGenerationSession(): Promise<GenerationSessionEnvelope> {
  return requestJson<GenerationSessionEnvelope>("/api/generate/sessions/active");
}

export async function fetchGenerationSession(sessionId: string): Promise<GenerationSessionEnvelope> {
  return requestJson<GenerationSessionEnvelope>(`/api/generate/sessions/${encodeURIComponent(sessionId)}`);
}

export async function terminateGenerationSession(sessionId: string): Promise<GenerationSessionStartResult> {
  return requestJson<GenerationSessionStartResult>(`/api/generate/sessions/${encodeURIComponent(sessionId)}/terminate`, {
    method: "POST",
  });
}

export async function streamGenerationSession(
  sessionId: string,
  onEvent: (event: GenerateEvent) => void,
  signal?: AbortSignal,
  afterSeq = 0,
) {
  return streamSSE<GenerateEvent>(
    `/api/generate/sessions/${encodeURIComponent(sessionId)}/stream?after_seq=${afterSeq}`,
    onEvent,
    { method: "GET", signal },
  );
}

export async function streamTemplateAnalysisSession(
  sessionId: string,
  onEvent: (event: TemplateAnalysisEvent) => void,
  signal?: AbortSignal,
  afterSeq = 0,
) {
  return streamSSE<TemplateAnalysisEvent>(
    `/api/template/analyze/sessions/${encodeURIComponent(sessionId)}/stream?after_seq=${afterSeq}`,
    onEvent,
    { method: "GET", signal },
  );
}

// ---------------------------------------------------------------------------
// Custom (user-supplied) OpenAI-compatible content audit model
//
// Independent of provider_credentials; one record per user. Probe runs
// BEFORE persisting; backend returns 422 with a structured {error:{code,message}}
// body on failure. On success the POST returns the saved record (api_key
// redacted to api_key_preview).
// ---------------------------------------------------------------------------

const CUSTOM_AUDIT_ENDPOINT = "/api/user/custom-audit-model";

export async function fetchCustomAuditModel(): Promise<CustomAuditModelStatus | null> {
  const response = await authedFetch(apiUrl(CUSTOM_AUDIT_ENDPOINT));
  if (response.status === 404) return null;
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${response.status}`));
  }
  return (await response.json()) as CustomAuditModelStatus;
}

export async function saveCustomAuditModel(data: {
  name: string;
  base_url: string;
  model_id: string;
  api_key: string;
}): Promise<CustomAuditModelStatus> {
  const response = await authedFetch(apiUrl(CUSTOM_AUDIT_ENDPOINT), {
    method: "POST",
    headers: {
      ...buildAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  const text = await response.text();
  let parsed: unknown = {};
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = {};
    }
  }
  if (!response.ok) {
    // 422 path: backend returns { error: { code, message } }.
    const body = (parsed && typeof parsed === "object" ? parsed : {}) as {
      error?: { code?: string; message?: string };
    };
    const structured = body.error;
    const err = new Error(
      structured?.message || parseApiErrorMessage(text, `HTTP ${response.status}`),
    ) as Error & { customAuditError?: CustomAuditModelError };
    if (structured?.code) {
      err.customAuditError = {
        code: structured.code,
        message: structured.message || err.message,
      };
    }
    throw err;
  }
  return parsed as CustomAuditModelStatus;
}

export async function deleteCustomAuditModel(): Promise<void> {
  const response = await authedFetch(apiUrl(CUSTOM_AUDIT_ENDPOINT), {
    method: "DELETE",
    headers: buildAuthHeaders(),
  });
  if (!response.ok && response.status !== 204) {
    const raw = await response.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${response.status}`));
  }
}

// ---------------------------------------------------------------------------
// Multi Custom Models
//
// CRUD + capability testing + role assignment for user-supplied OpenAI-
// compatible models. Mirrors the custom-audit pattern above but supports
// multiple records per user.
// ---------------------------------------------------------------------------

const CUSTOM_MODELS_ENDPOINT = "/api/user/custom-models";

export async function fetchCustomModels(): Promise<CustomModel[]> {
  const res = await authedFetch(apiUrl(CUSTOM_MODELS_ENDPOINT));
  if (res.status === 401) return []; // unauthenticated edge case
  if (!res.ok) {
    const raw = await res.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${res.status}`));
  }
  const data: CustomModelsListResponse = await res.json();
  return data.models || [];
}

export async function createCustomModel(
  data: CreateCustomModelRequest,
): Promise<CustomModel> {
  const res = await fetch(apiUrl(CUSTOM_MODELS_ENDPOINT), {
    method: "POST",
    headers: { ...buildAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const raw = await res.text();
    let parsed: Record<string, unknown> = {};
    try { parsed = JSON.parse(raw); } catch { /* not JSON */ }
    const structured = (parsed as { error?: CustomModelError }).error;
    const err = new Error(
      structured?.message || parseApiErrorMessage(raw, `HTTP ${res.status}`),
    ) as Error & { customModelError?: CustomModelError };
    if (structured) err.customModelError = structured;
    throw err;
  }
  return res.json() as Promise<CustomModel>;
}

export async function updateCustomModel(
  id: number,
  data: UpdateCustomModelRequest,
): Promise<CustomModel> {
  const res = await authedFetch(`${apiUrl(CUSTOM_MODELS_ENDPOINT)}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (res.status === 404) throw new Error("Model not found");
  if (!res.ok) {
    const raw = await res.text();
    let parsed: Record<string, unknown> = {};
    try { parsed = JSON.parse(raw); } catch { /* not JSON */ }
    const structured = (parsed as { error?: CustomModelError }).error;
    const err = new Error(
      structured?.message || parseApiErrorMessage(raw, `HTTP ${res.status}`),
    ) as Error & { customModelError?: CustomModelError };
    if (structured) err.customModelError = structured;
    throw err;
  }
  return res.json() as Promise<CustomModel>;
}

export async function deleteCustomModel(id: number): Promise<void> {
  const res = await authedFetch(`${apiUrl(CUSTOM_MODELS_ENDPOINT)}/${id}`, {
    method: "DELETE",
  });
  if (res.status === 404) throw new Error("Model not found");
  if (!res.ok && res.status !== 204) {
    const raw = await res.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${res.status}`));
  }
}

export async function testModelCapabilities(
  id: number,
  testTypes?: string[],
): Promise<TestResult> {
  const res = await authedFetch(`${apiUrl(CUSTOM_MODELS_ENDPOINT)}/${id}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ test_types: testTypes }),
  });
  if (!res.ok) {
    const raw = await res.text();
    let parsed: Record<string, unknown> = {};
    try { parsed = JSON.parse(raw); } catch { /* not JSON */ }
    const structured = (parsed as { error?: CustomModelError }).error;
    const err = new Error(
      structured?.message || parseApiErrorMessage(raw, `HTTP ${res.status}`),
    ) as Error & { customModelError?: CustomModelError };
    if (structured) err.customModelError = structured;
    throw err;
  }
  return res.json() as Promise<TestResult>;
}

export async function assignModelRoles(
  id: number,
  roles: string[],
  defaultModelId?: string,
): Promise<AssignRolesResponse> {
  const res = await authedFetch(`${apiUrl(CUSTOM_MODELS_ENDPOINT)}/${id}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assigned_roles: roles, default_model_id: defaultModelId }),
  });
  if (!res.ok) {
    const raw = await res.text();
    let parsed: Record<string, unknown> = {};
    try { parsed = JSON.parse(raw); } catch { /* not JSON */ }
    const structured = (parsed as { error?: CustomModelError }).error;
    throw new Error(
      structured?.message || parseApiErrorMessage(raw, `HTTP ${res.status}`),
    );
  }
  return res.json() as Promise<AssignRolesResponse>;
}

