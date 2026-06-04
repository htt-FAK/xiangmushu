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

export type GenerateEvent =
  | { type: "task"; index: number; total: number; chapter: string }
  | { type: "chunk"; index: number; text: string }
  | { type: "progress"; index: number; total: number }
  | { type: "done"; filename: string; download: string }
  | { type: "error"; index?: number; error: string };

export type GenerateParams = {
  slug: string;
  template: string;
  wordLimit: number;
  topK: number;
  maxDistance: number;
  enableWeb: boolean;
  useStream: boolean;
};
