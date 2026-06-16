export type TemplateItem = {
  name: string;
  mtime?: number;
};

export type KnowledgeBase = {
  slug: string;
  label?: string;
  name?: string;
  source_dir?: string;
};

export type KnowledgeSourceStats = {
  sources: string[];
  chunk_count: number;
  source_count: number;
  integrity?: {
    collection_exists?: boolean;
    vector_count?: number;
    missing_collection?: boolean;
    count_mismatch?: boolean;
    missing_source_rows?: number[];
  };
};

export type FillTask = {
  target_chapter: string;
  prompt?: string;
  description?: string;
  task_type?: string;
  word_limit: number;
  location_hint?: Record<string, unknown>;
  replace_mode?: string;
};

export type AnalyzeResult = {
  ok: boolean;
  template?: string;
  tasks?: FillTask[];
  count?: number;
  mode?: "anchor" | "infer" | string;
  vision_model?: string;
  planner_model?: string;
  vision_status?: string;
  billing?: GenerationBilling;
  error?: string;
};

export type TemplateAnalysisLog = {
  phase: string;
  message: string;
  created_at: string;
};

export type TemplateAnalysisSessionSnapshot = {
  session_id: string;
  user_id: number;
  status: "running" | "done" | "error" | string;
  currentPhase: string;
  statusMessage: string;
  template: string;
  vision_model: string;
  planner_model: string;
  mode?: string;
  vision_status?: string;
  tasks: FillTask[];
  billing?: GenerationBilling | null;
  logs: TemplateAnalysisLog[];
  last_error?: { code: string; message: string; retryable?: boolean; detail?: string } | null;
  params: { [key: string]: unknown };
  created_at: string;
  updated_at: string;
  last_seq: number;
};

export type TemplateAnalysisSessionEnvelope = {
  session: TemplateAnalysisSessionSnapshot | null;
};

export type TemplateAnalysisSessionStartResult = {
  ok: boolean;
  session_id?: string;
  session?: TemplateAnalysisSessionSnapshot | null;
  code?: string;
  message?: string;
};

export type TemplateAnalysisEvent =
  | { type: "status"; seq?: number; phase: string; message: string }
  | { type: "billing"; seq?: number; billing: BillingRecord }
  | ({
      type: "done";
      seq?: number;
      message?: string;
    } & AnalyzeResult)
  | {
      type: "error";
      seq?: number;
      terminal?: boolean;
      error: string | { code: string; message: string; retryable?: boolean; detail?: string };
    }
  | { type: "heartbeat"; seq?: number };

export type UploadResult = {
  file: string;
  ok: boolean;
  chunks?: number;
  error?: string;
};

export type PostFillChecks = {
  ok: boolean;
  leftover_placeholders?: string[];
  missing_chapters?: string[];
  protected_issues?: string[];
  cover_modified?: boolean;
  rating_table_modified?: boolean;
  template_words?: number;
  output_words?: number;
  template_tables?: number;
  output_tables?: number;
};

export type BillingRecord = {
  id?: number;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_cny: number;
  created_at?: string;
};

export type BillingSummary = {
  input_tokens: number;
  output_tokens: number;
  cost_cny: number;
  generation_count: number;
};

export type GenerationBilling = {
  records: BillingRecord[];
  input_tokens: number;
  output_tokens: number;
  cost_cny: number;
};

export type ProviderApiKeyStatus = {
  provider_code?: string;
  has_key: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  key_preview?: string | null;
  validated?: boolean;
};

export type ApiKeyStatus = {
  providers: Record<string, ProviderApiKeyStatus>;
};

export type ValidationProbe = {
  ok: boolean;
  model: string;
  code: string;
  message: string;
  detail?: string;
  retryable?: boolean;
};

export type ApiKeyValidationResult = {
  ok: boolean;
  code: string;
  message: string;
  retryable: boolean;
  validated_model?: string | null;
  provider_code?: string;
  search_enabled?: boolean;
  probes: ValidationProbe[];
};

export interface ModelOption {
  model: string;
  recommended?: boolean;
  label?: string;
  provider_code?: string;
  provider_name?: string;
}

export interface ModelModuleConfig {
  label: string;
  description?: string;
  tiers?: Record<string, ModelOption[]>;
  options?: ModelOption[];
  config_keys?: string[];
  selected_unavailable?: { model: string; reason: string };
  source?: string;
  warning?: string;
}

export type ModelOptionsMap = Record<string, ModelModuleConfig>;

export type UserPreferences = {
  language: "zh" | "en";
  model_choices?: Record<string, string>;
  warnings?: Record<string, string>;
};

export type GenerateEvent =
  | { type: "task"; index: number; total: number; chapter: string }
  | {
      type: "route";
      index: number;
      model: string;
      tier?: string;
      role?: string;
      kb_hits?: number;
      evidence_refs?: string[];
    }
  | { type: "chunk"; index: number; text: string }
  | {
      type: "audit";
      index: number;
      verdict: string;
      issues: string[];
      revised: boolean;
      is_model_audit?: boolean;
    }
  | { type: "billing"; index: number; billing: BillingRecord }
  | { type: "progress"; index: number; total: number }
  | {
      type: "quota_alert";
      seq?: number;
      module?: string;
      current_model: string;
      available_models: string[];
      message: string;
    }
  | {
      type: "done";
      seq?: number;
      filename: string;
      download: string;
      report_download?: string;
      report_summary?: string;
      post_fill_checks?: PostFillChecks;
      visual_score?: number | null;
      billing?: GenerationBilling;
      billing_summary?: BillingSummary;
    }
  | { type: "terminated"; seq?: number; message?: string }
  | { type: "error"; seq?: number; index?: number; terminal?: boolean; error: string | { code: string; message: string; retryable?: boolean; detail?: string } }
  | { type: "heartbeat"; seq?: number };

export type GenerationSessionSnapshot = {
  session_id: string;
  user_id: number;
  status: "running" | "done" | "error" | "terminated" | string;
  currentStep: string;
  currentTask: string;
  progress: { done: number; total: number };
  outputs: OutputBlockSnapshot[];
  download: string;
  report_download: string;
  report_summary: string;
  post_fill_checks?: PostFillChecks | null;
  visual_score?: number | null;
  billing?: GenerationBilling | null;
  billing_summary?: BillingSummary | null;
  last_error?: { code: string; message: string; retryable?: boolean; detail?: string } | null;
  params: GenerateParams & { [key: string]: unknown };
  created_at: string;
  updated_at: string;
  last_seq: number;
  terminate_requested?: boolean;
};

export type OutputBlockSnapshot = {
  chapter: string;
  text: string;
  model?: string | null;
  tier?: string | null;
  role?: string | null;
  kbHits?: number | null;
  evidenceRefs?: string[];
  auditVerdict?: string | null;
  auditIssues?: string[];
  revised?: boolean;
};

export type GenerationSessionEnvelope = {
  session: GenerationSessionSnapshot | null;
};

export type GenerationSessionStartResult = {
  ok: boolean;
  session_id?: string;
  session?: GenerationSessionSnapshot | null;
  code?: string;
  message?: string;
};

export type GenerateParams = {
  slug: string;
  template: string;
  customInstructions?: string;
  wordLimit: number;
  topK: number;
  maxDistance: number;
  enableWeb: boolean;
  useStream: boolean;
  enableAudit: boolean;
  enableVisualAudit: boolean;
};

export type HistoryArticleStatus = "completed" | "review" | "failed";

export type HistoryModelUsage = {
  model: string;
  inputTokens: number;
  outputTokens: number;
  costCny: number;
};

export type HistoryArticle = {
  id: string;
  title: string;
  template: string;
  knowledgeBase: string;
  createdAt: string;
  status: HistoryArticleStatus;
  documentUrl?: string;
  reportUrl?: string;
  inputTokens: number;
  outputTokens: number;
  costCny: number;
  modelUsage: HistoryModelUsage[];
};

export type HistoryAvailability = {
  available: boolean;
  source: "backend" | "unavailable" | "legacy_fallback" | string;
  warning?: string;
};

export type HistorySummary = {
  count: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  costCny: number;
  modelUsage: HistoryModelUsage[];
};

export type HistoryArticlesResponse = {
  articles: HistoryArticle[];
  summary: HistorySummary;
  availability: HistoryAvailability;
};
