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
};

export type FillTask = {
  target_chapter: string;
  prompt: string;
  word_limit: number;
  location_hint?: Record<string, unknown>;
  replace_mode?: string;
};

export type AnalyzeResult = {
  ok: boolean;
  tasks?: FillTask[];
  count?: number;
  mode?: "anchor" | "infer" | string;
  error?: string;
};

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

export type ApiKeyStatus = {
  has_key: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  key_preview?: string | null;
  validated?: boolean;
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
  probes: ValidationProbe[];
};

export interface ModelOption {
  model: string;
  recommended?: boolean;
}

export interface ModelModuleConfig {
  label: string;
  description?: string;
  tiers?: Record<string, ModelOption[]>;
  options?: ModelOption[];
  config_keys?: string[];
}

export type ModelOptionsMap = Record<string, ModelModuleConfig>;

export type UserPreferences = {
  language: "zh" | "en";
  model_choices?: Record<string, string>;
};

export type GenerateEvent =
  | { type: "task"; index: number; total: number; chapter: string }
  | {
      type: "route";
      index: number;
      model: string;
      tier?: string;
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
    }
  | { type: "billing"; index: number; billing: BillingRecord }
  | { type: "progress"; index: number; total: number }
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
  | { type: "error"; seq?: number; index?: number; terminal?: boolean; error: string | { code: string; message: string; retryable?: boolean; detail?: string } }
  | { type: "heartbeat"; seq?: number };

export type GenerationSessionSnapshot = {
  session_id: string;
  user_id: number;
  status: "running" | "done" | "error" | string;
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
};

export type OutputBlockSnapshot = {
  chapter: string;
  text: string;
  model?: string | null;
  tier?: string | null;
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
