import type {
  AnalyzeResult,
  ApiKeyValidationResult,
  ApiKeyStatus,
  BillingSummary,
  GenerateEvent,
  GenerateParams,
  GenerationSessionEnvelope,
  GenerationSessionStartResult,
  HistoryArticle,
  KnowledgeBase,
  KnowledgeSourceStats,
  ModelOptionsMap,
  TemplateItem,
  UploadResult,
  UserPreferences,
} from "./types";
import { apiUrl } from "./apiBase";
import { buildAuthHeaders } from "./auth";

function parseErrorMessage(raw: string, fallback: string): string {
  let message = raw || fallback;
  try {
    const parsed = JSON.parse(raw) as {
      message?: string;
      detail?: string | { reason?: string; message?: string };
    };
    if (typeof parsed.detail === "string") {
      message = parsed.detail;
    } else if (parsed.detail?.message) {
      message = parsed.detail.message;
    } else if (parsed.message) {
      message = parsed.message;
    }
  } catch {
    // Keep the raw response when the server did not return JSON.
  }
  return message;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      ...buildAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 401) {
    window.localStorage.removeItem("xiangmushu.auth.token");
    const currentPath = window.location.pathname;
    if (!currentPath.startsWith("/auth")) {
      window.location.href = `/auth?next=${encodeURIComponent(currentPath)}`;
    }
    throw new Error("Session expired");
  }
  if (!response.ok) {
    const raw = await response.text();
    const message = parseErrorMessage(raw, `HTTP ${response.status}`);
    throw new Error(message);
  }
  return (await response.json()) as T;
}

async function requestJsonAllowError<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      ...buildAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 401) {
    window.localStorage.removeItem("xiangmushu.auth.token");
    const currentPath = window.location.pathname;
    if (!currentPath.startsWith("/auth")) {
      window.location.href = `/auth?next=${encodeURIComponent(currentPath)}`;
    }
    throw new Error("Session expired");
  }
  const text = await response.text();
  if (!text) return {} as T;
  return JSON.parse(text) as T;
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

export async function validateApiKey(apiKey: string): Promise<ApiKeyValidationResult> {
  return requestJsonAllowError<ApiKeyValidationResult>("/api/user/apikey/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function saveApiKey(apiKey: string): Promise<ApiKeyStatus & { ok: boolean; validation?: ApiKeyValidationResult }> {
  return requestJson<ApiKeyStatus & { ok: boolean; validation?: ApiKeyValidationResult }>("/api/user/apikey", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function deleteApiKey(): Promise<ApiKeyStatus & { ok: boolean }> {
  return requestJson<ApiKeyStatus & { ok: boolean }>("/api/user/apikey", {
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

export async function fetchHistoryArticles(): Promise<HistoryArticle[]> {
  const data = await requestJson<{ articles: HistoryArticle[] }>("/api/history/articles");
  return data.articles ?? [];
}

export function downloadUrl(path: string) {
  return apiUrl(path);
}

export async function handleDownload(path: string) {
  const response = await fetch(apiUrl(path), {
    headers: buildAuthHeaders(),
  });
  if (!response.ok) throw new Error("Download failed");
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

  const response = await fetch(apiUrl("/api/generate"), {
    method: "POST",
    headers: buildAuthHeaders(),
    body: form,
    signal,
  });
  if (!response.ok || !response.body) {
    const message = await response.text();
    throw new Error(parseErrorMessage(message, `HTTP ${response.status}`));
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
      const line = eventText
        .split("\n")
        .find((item) => item.startsWith("data:"));
      if (!line) continue;
      onEvent(JSON.parse(line.slice(5).trim()) as GenerateEvent);
    }
  }
}

async function streamSession(path: string, onEvent: (event: GenerateEvent) => void, signal?: AbortSignal) {
  const response = await fetch(apiUrl(path), {
    method: "GET",
    headers: buildAuthHeaders(),
    signal,
  });
  if (!response.ok || !response.body) {
    const message = await response.text();
    throw new Error(parseErrorMessage(message, `HTTP ${response.status}`));
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
      onEvent(JSON.parse(line.slice(5).trim()) as GenerateEvent);
    }
  }
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

export async function streamGenerationSession(
  sessionId: string,
  onEvent: (event: GenerateEvent) => void,
  signal?: AbortSignal,
  afterSeq = 0,
) {
  return streamSession(`/api/generate/sessions/${encodeURIComponent(sessionId)}/stream?after_seq=${afterSeq}`, onEvent, signal);
}
