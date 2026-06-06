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
      filename: string;
      download: string;
      report_download?: string;
      report_summary?: string;
      post_fill_checks?: PostFillChecks;
      visual_score?: number | null;
      billing?: GenerationBilling;
      billing_summary?: BillingSummary;
    }
  | { type: "error"; index?: number; error: string };

export type GenerateParams = {
  slug: string;
  template: string;
  wordLimit: number;
  topK: number;
  maxDistance: number;
  enableWeb: boolean;
  useStream: boolean;
  enableAudit: boolean;
  enableVisualAudit: boolean;
};
