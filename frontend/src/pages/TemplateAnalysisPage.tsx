import { FileText, FileUp, ListChecks, Loader2, RefreshCw, Trash2, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  analyzeTemplate,
  deleteTemplate,
  fetchApiKeyStatus,
  fetchModelOptions,
  fetchTemplates,
  reanalyzeTemplate,
} from "../api";
import { Button, EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { normalizeErrorMessage } from "../errors";
import { useI18n } from "../i18n";
import type { AnalyzeResult, BillingRecord, FillTask, ModelOption, TemplateItem } from "../types";
import { Link } from "react-router-dom";

function taskLabel(task: FillTask, index: number, fallback: string) {
  return task.target_chapter || `${fallback} ${index + 1}`;
}

function taskBody(task: FillTask, fallback: string) {
  return task.description || task.prompt || fallback;
}

function flattenModelOptions(options?: { tiers?: Record<string, ModelOption[]>; options?: ModelOption[] }) {
  const out: ModelOption[] = [];
  const seen = new Set<string>();
  for (const group of Object.values(options?.tiers ?? {})) {
    for (const item of group) {
      if (!item.model || seen.has(item.model)) continue;
      seen.add(item.model);
      out.push(item);
    }
  }
  for (const item of options?.options ?? []) {
    if (!item.model || seen.has(item.model)) continue;
    seen.add(item.model);
    out.push(item);
  }
  return out;
}

function formatTime(mtime?: number) {
  if (!mtime) return "-";
  return new Date(mtime * 1000).toLocaleString();
}

function ModelSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ModelOption[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-12 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
      >
        {options.map((item) => (
          <option key={item.model} value={item.model}>
            {item.model}{item.recommended ? " 推荐" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

function BillingStrip({ records }: { records: BillingRecord[] }) {
  const input = records.reduce((sum, item) => sum + (item.input_tokens || 0), 0);
  const output = records.reduce((sum, item) => sum + (item.output_tokens || 0), 0);
  const cost = records.reduce((sum, item) => sum + (item.cost_cny || 0), 0);
  return (
    <div className="grid grid-cols-3 gap-3">
      <Stat label="Input tokens" value={input} tone="cyan" />
      <Stat label="Output tokens" value={output} tone="lime" />
      <Stat label="费用 CNY" value={cost.toFixed(6)} tone="amber" />
    </div>
  );
}

export default function TemplateAnalysisPage() {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [visionModels, setVisionModels] = useState<ModelOption[]>([]);
  const [visionModel, setVisionModel] = useState("");
  const [plannerModels, setPlannerModels] = useState<ModelOption[]>([]);
  const [plannerModel, setPlannerModel] = useState("");
  const [tasks, setTasks] = useState<FillTask[]>([]);
  const [mode, setMode] = useState("");
  const [visionStatus, setVisionStatus] = useState("");
  const [billingRecords, setBillingRecords] = useState<BillingRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [deleting, setDeleting] = useState("");
  const [error, setError] = useState("");
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);

  const totalWords = useMemo(
    () => tasks.reduce((sum, task) => sum + Math.max(0, task.word_limit || 0), 0),
    [tasks],
  );

  async function refreshTemplates() {
    setListLoading(true);
    try {
      const next = await fetchTemplates();
      setTemplates(next);
      if (!selectedTemplate && next[0]) setSelectedTemplate(next[0].name);
    } catch (err) {
      setError(normalizeErrorMessage(err, "模板列表加载失败，请稍后重试"));
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => {
    void refreshTemplates();
    fetchApiKeyStatus()
      .then((status) => setHasApiKey(Boolean(status.has_key && status.validated)))
      .catch(() => setHasApiKey(null));
    fetchModelOptions()
      .then((options) => {
        const models = flattenModelOptions(options.vision_layout ?? options.vision);
        const planners = flattenModelOptions(options.template_planner);
        setVisionModels(models);
        setVisionModel(models.find((m) => m.recommended)?.model || models[0]?.model || "");
        setPlannerModels(planners);
        setPlannerModel(planners.find((m) => m.recommended)?.model || planners[0]?.model || "");
      })
      .catch((err: unknown) => setError(normalizeErrorMessage(err, "模型选项加载失败，请稍后重试")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function clearResult() {
    setTasks([]);
    setMode("");
    setVisionStatus("");
    setBillingRecords([]);
  }

  function applyResult(result: AnalyzeResult) {
    if (!result.ok) throw new Error(result.error || t("template.analyze"));
    setTasks(result.tasks ?? []);
    setMode(result.mode ?? "");
    setVisionStatus(result.vision_status ?? "");
    setBillingRecords(result.billing?.records ?? []);
    if (result.template) setSelectedTemplate(result.template);
  }

  async function onAnalyzeUpload() {
    if (!file) return;
    setLoading(true);
    setError("");
    clearResult();
    try {
      applyResult(await analyzeTemplate(file, visionModel, plannerModel));
      await refreshTemplates();
    } catch (err) {
      setError(normalizeErrorMessage(err, t("template.analyze")));
    } finally {
      setLoading(false);
    }
  }

  async function onReanalyze(template = selectedTemplate) {
    if (!template) return;
    setSelectedTemplate(template);
    setLoading(true);
    setError("");
    clearResult();
    try {
      applyResult(await reanalyzeTemplate(template, visionModel, plannerModel));
      await refreshTemplates();
    } catch (err) {
      setError(normalizeErrorMessage(err, t("template.analyze")));
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(template: string) {
    setDeleting(template);
    setError("");
    try {
      await deleteTemplate(template);
      if (selectedTemplate === template) {
        setSelectedTemplate("");
        clearResult();
      }
      await refreshTemplates();
    } catch (err) {
      setError(normalizeErrorMessage(err, "模板删除失败，请稍后重试"));
    } finally {
      setDeleting("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={t("template.eyebrow")}
        title={t("template.title")}
        description={t("template.description")}
      />
      <ErrorBanner message={error} />
      {hasApiKey === false && (
        <div className="mb-6 flex flex-col gap-4 border border-signal-amber/40 bg-signal-amber/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between md:px-5">
          <p className="min-w-0 break-words text-sm font-semibold text-amber-100">
            模板分析已启用严格 BYOK。请先在设置页保存你自己的 API Key。
          </p>
          <Link
            to="/settings"
            className="inline-flex min-h-11 items-center justify-center border border-signal-amber bg-signal-amber px-4 text-xs font-bold text-night-950 transition hover:bg-white sm:w-auto"
          >
            去设置
          </Link>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-6">
          <Panel>
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="font-display text-2xl font-semibold text-white">{t("template.upload")}</p>
                <p className="text-sm text-slate-500">{t("template.uploadHint")}</p>
              </div>
              <UploadCloud className="text-signal-cyan" size={25} />
            </div>

            <label className="flex min-h-40 cursor-pointer flex-col items-center justify-center border border-dashed border-white/18 bg-night-950/60 px-5 py-8 text-center transition hover:border-signal-cyan/60">
              <FileUp className="mb-4 text-signal-cyan" size={34} />
              <span className="break-all font-display text-xl font-semibold text-white">
                {file ? file.name : t("template.chooseFile")}
              </span>
              <span className="mt-2 text-sm text-slate-500">{t("template.fileHint")}</span>
              <input
                className="sr-only"
                type="file"
                accept=".docx"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>

            <div className="mt-5 space-y-5">
              <ModelSelect
                label="视觉模型"
                value={visionModel}
                options={visionModels}
                onChange={setVisionModel}
              />
              <ModelSelect
                label="模板拆解模型"
                value={plannerModel}
                options={plannerModels}
                onChange={setPlannerModel}
              />
            </div>

            <div className="mt-5">
              <Button
                className="w-full"
                onClick={onAnalyzeUpload}
                disabled={!file || !visionModel || !plannerModel || loading || hasApiKey === false}
              >
                {loading ? <Loader2 className="animate-spin" size={17} /> : <ListChecks size={17} />}
                上传并分析
              </Button>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-3">
              <Stat label={t("template.taskCount")} value={tasks.length} />
              <Stat label={t("template.wordTarget")} value={totalWords} tone="lime" />
              <Stat label={t("template.mode")} value={mode || "-"} tone="amber" />
            </div>

            {billingRecords.length > 0 && (
              <div className="mt-5">
                <BillingStrip records={billingRecords} />
                <div className="mt-3 space-y-2">
                  {billingRecords.map((record, index) => (
                    <div
                      key={record.id ?? index}
                      className="flex items-center justify-between gap-3 border border-white/10 bg-night-950/50 px-3 py-2 text-xs text-slate-400"
                    >
                      <span className="break-all text-slate-300">{record.model}</span>
                      <span>{record.input_tokens}/{record.output_tokens} tokens</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {visionStatus && <p className="mt-4 text-xs leading-6 text-slate-500">{visionStatus}</p>}
          </Panel>

          <Panel>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="font-display text-xl font-semibold text-white">已有模板</p>
                <p className="text-sm text-slate-500">选择一个模板后，可用当前模型重新分析。</p>
              </div>
              <FileText className="text-signal-lime" size={22} />
            </div>

            {listLoading ? (
              <div className="flex min-h-24 items-center justify-center text-slate-500">
                <Loader2 className="mr-2 animate-spin" size={16} /> 加载模板...
              </div>
            ) : templates.length === 0 ? (
              <EmptyState title="暂无模板" body="上传 docx 后会出现在这里。" />
            ) : (
              <div className="space-y-2">
                {templates.map((template) => {
                  const active = selectedTemplate === template.name;
                  return (
                    <div
                      key={template.name}
                      className={`grid gap-3 border p-3 md:grid-cols-[1fr_auto] md:items-center ${
                        active ? "border-signal-cyan/50 bg-signal-cyan/10" : "border-white/10 bg-night-950/45"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedTemplate(template.name)}
                        className="min-w-0 text-left"
                      >
                        <span className="block break-all text-sm font-semibold text-white">{template.name}</span>
                        <span className="mt-1 block text-xs text-slate-500">
                          {formatTime(template.mtime)}
                          {active ? " · 已选中" : ""}
                        </span>
                      </button>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void onReanalyze(template.name)}
                          disabled={loading || !visionModel || !plannerModel || hasApiKey === false}
                          className="inline-flex h-10 items-center gap-2 border border-white/10 px-3 text-sm text-slate-300 hover:border-signal-cyan/50 hover:text-signal-cyan disabled:opacity-50"
                          title="重新分析"
                        >
                          {loading && active ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                          重新分析
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDelete(template.name)}
                          disabled={Boolean(deleting)}
                          className="inline-flex h-10 items-center gap-2 border border-white/10 px-3 text-sm text-slate-300 hover:border-signal-rose/50 hover:text-signal-rose disabled:opacity-50"
                          title="删除模板"
                        >
                          {deleting === template.name ? <Loader2 className="animate-spin" size={16} /> : <Trash2 size={16} />}
                          删除
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </div>

        <Panel>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">{t("template.results")}</p>
              <p className="text-sm text-slate-500">{t("template.resultsHint")}</p>
            </div>
            <span className="border border-white/10 px-3 py-1 text-xs text-slate-400">
              {tasks.length} {t("template.items")}
            </span>
          </div>

          {tasks.length === 0 ? (
            <EmptyState title={t("template.empty")} body={t("template.emptyBody")} />
          ) : (
            <div className="space-y-3">
              {tasks.map((task, index) => (
                <article
                  key={`${task.target_chapter}-${index}`}
                  className="border border-white/10 bg-night-850/70 p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <p className="break-words font-display text-xl font-semibold text-white">
                        {taskLabel(task, index, t("template.taskFallback"))}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-400">
                        {taskBody(task, t("template.noPrompt"))}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <span className="border border-signal-cyan/30 px-2 py-1 text-xs text-signal-cyan">
                        {task.word_limit || 0} {t("template.wordUnit")}
                      </span>
                      <span className="border border-white/10 px-2 py-1 text-xs text-slate-400">
                        {task.task_type || task.replace_mode || "paragraph"}
                      </span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
