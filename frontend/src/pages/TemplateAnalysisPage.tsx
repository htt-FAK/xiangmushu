import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  FileUp,
  ListChecks,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteTemplate,
  fetchActiveTemplateAnalysisSession,
  fetchApiKeyStatus,
  fetchModelOptions,
  fetchTemplates,
  fetchTemplateAnalysisSession,
  startTemplateAnalysisSession,
  startTemplateReanalysisSession,
  streamTemplateAnalysisSession,
} from "../api";
import { Button, DetailOverlay, EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { normalizeErrorMessage } from "../errors";
import { useI18n } from "../i18n";
import type {
  BillingRecord,
  FillTask,
  ModelModuleConfig,
  ModelOption,
  TemplateAnalysisEvent,
  TemplateAnalysisSessionSnapshot,
  TemplateItem,
} from "../types";
import { clsx } from "../utils";

function taskLabel(task: FillTask, index: number, fallback: string) {
  return task.target_chapter || `${fallback} ${index + 1}`;
}

function taskBody(task: FillTask, fallback: string) {
  return task.description || task.prompt || fallback;
}

function flattenModelOptions(config?: ModelModuleConfig) {
  const out: ModelOption[] = [];
  const seen = new Set<string>();
  for (const group of Object.values(config?.tiers ?? {})) {
    for (const item of group) {
      if (!item.model || seen.has(item.model)) continue;
      seen.add(item.model);
      out.push(item);
    }
  }
  for (const item of config?.options ?? []) {
    if (!item.model || seen.has(item.model)) continue;
    seen.add(item.model);
    out.push(item);
  }
  return out;
}

function pickModel(options: ModelOption[], current = "") {
  if (current && options.some((item) => item.model === current)) return current;
  return options.find((item) => item.recommended)?.model || options[0]?.model || "";
}

function formatTime(mtime?: number) {
  if (!mtime) return "-";
  return new Date(mtime * 1000).toLocaleString();
}

function mergeBilling(current: TemplateAnalysisSessionSnapshot["billing"], record: BillingRecord) {
  const existing = current ?? { records: [], input_tokens: 0, output_tokens: 0, cost_cny: 0 };
  return {
    records: [...(existing.records ?? []), record],
    input_tokens: (existing.input_tokens ?? 0) + (record.input_tokens ?? 0),
    output_tokens: (existing.output_tokens ?? 0) + (record.output_tokens ?? 0),
    cost_cny: Number(((existing.cost_cny ?? 0) + (record.cost_cny ?? 0)).toFixed(8)),
  };
}

function sessionStatusTone(status: string) {
  if (status === "done") return "border-signal-lime/40 bg-signal-lime/10 text-signal-lime";
  if (status === "error") return "border-signal-rose/40 bg-signal-rose/10 text-signal-rose";
  return "border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan";
}

function ModelSelect({
  label,
  value,
  options,
  onChange,
  warning,
}: {
  label: string;
  value: string;
  options: ModelOption[];
  onChange: (value: string) => void;
  warning?: string;
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
            {item.label || item.model}
            {item.provider_name ? ` (${item.provider_name})` : ""}
            {item.recommended ? " *" : ""}
          </option>
        ))}
      </select>
      {warning ? <p className="mt-2 text-xs text-signal-amber">{warning}</p> : null}
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
      <Stat label="Cost CNY" value={cost.toFixed(6)} tone="amber" />
    </div>
  );
}

function TaskCard({
  task,
  index,
  compact = false,
  fallbackTaskLabel,
  fallbackPromptLabel,
  wordUnitLabel,
}: {
  task: FillTask;
  index: number;
  compact?: boolean;
  fallbackTaskLabel: string;
  fallbackPromptLabel: string;
  wordUnitLabel: string;
}) {
  return (
    <article className="border border-white/10 bg-night-850/70 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <p className={clsx("break-words font-display font-semibold text-white", compact ? "text-lg" : "text-xl")}>
            {taskLabel(task, index, fallbackTaskLabel)}
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-400">{taskBody(task, fallbackPromptLabel)}</p>
          {!compact && task.location_hint ? (
            <pre className="mt-3 max-h-32 overflow-auto border border-white/10 bg-night-950/70 px-3 py-2 text-xs text-slate-500">
              {JSON.stringify(task.location_hint, null, 2)}
            </pre>
          ) : null}
        </div>
        <div className="flex shrink-0 gap-2">
          <span className="border border-signal-cyan/30 px-2 py-1 text-xs text-signal-cyan">
            {task.word_limit || 0} {wordUnitLabel}
          </span>
          <span className="border border-white/10 px-2 py-1 text-xs text-slate-400">
            {task.task_type || task.replace_mode || "paragraph"}
          </span>
        </div>
      </div>
    </article>
  );
}

export default function TemplateAnalysisPage() {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [visionConfig, setVisionConfig] = useState<ModelModuleConfig | undefined>();
  const [plannerConfig, setPlannerConfig] = useState<ModelModuleConfig | undefined>();
  const [visionModels, setVisionModels] = useState<ModelOption[]>([]);
  const [plannerModels, setPlannerModels] = useState<ModelOption[]>([]);
  const [visionModel, setVisionModel] = useState("");
  const [plannerModel, setPlannerModel] = useState("");
  const [session, setSession] = useState<TemplateAnalysisSessionSnapshot | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [deleting, setDeleting] = useState("");
  const [error, setError] = useState("");
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);

  const tasks = session?.tasks ?? [];
  const logs = session?.logs ?? [];
  const billingRecords = session?.billing?.records ?? [];
  const previewTasks = useMemo(() => tasks.slice(0, 3), [tasks]);
  const previewLogs = useMemo(() => logs.slice(-4), [logs]);
  const totalWords = useMemo(
    () => tasks.reduce((sum, task) => sum + Math.max(0, task.word_limit || 0), 0),
    [tasks],
  );
  const sessionRunning = session?.status === "running";

  const applySessionSnapshot = useCallback((next: TemplateAnalysisSessionSnapshot | null) => {
    setSession(next);
    if (!next) return;
    if (next.template) setSelectedTemplate(next.template);
    if (next.vision_model) setVisionModel(next.vision_model);
    if (next.planner_model) setPlannerModel(next.planner_model);
  }, []);

  const applySessionEvent = useCallback((event: TemplateAnalysisEvent) => {
    if (event.type === "heartbeat") return;
    setSession((prev) => {
      if (!prev) return prev;
      const base = {
        ...prev,
        last_seq: event.seq ?? prev.last_seq,
        updated_at: new Date().toISOString(),
      };
      if (event.type === "status") {
        return {
          ...base,
          status: "running",
          currentPhase: event.phase,
          statusMessage: event.message,
          logs: [...prev.logs, { phase: event.phase, message: event.message, created_at: new Date().toISOString() }],
        };
      }
      if (event.type === "billing") {
        return {
          ...base,
          billing: mergeBilling(prev.billing, event.billing),
        };
      }
      if (event.type === "done") {
        return {
          ...base,
          status: "done",
          currentPhase: "done",
          statusMessage: event.message || "Analysis complete",
          template: event.template || prev.template,
          mode: event.mode || prev.mode,
          vision_status: event.vision_status || prev.vision_status,
          tasks: event.tasks ?? prev.tasks,
          billing: event.billing ?? prev.billing,
          logs: [
            ...prev.logs,
            { phase: "done", message: event.message || "Analysis complete", created_at: new Date().toISOString() },
          ],
        };
      }
      const payload = typeof event.error === "string" ? { code: "template_analysis_error", message: event.error } : event.error;
      return {
        ...base,
        status: "error",
        currentPhase: "error",
        statusMessage: payload.message || "Template analysis failed",
        last_error: payload,
        logs: [
          ...prev.logs,
          { phase: "error", message: payload.message || "Template analysis failed", created_at: new Date().toISOString() },
        ],
      };
    });
  }, []);

  const refreshTemplates = useCallback(async () => {
    setListLoading(true);
    try {
      const next = await fetchTemplates();
      setTemplates(next);
      setSelectedTemplate((current) => current || next[0]?.name || "");
    } catch (err) {
      setError(normalizeErrorMessage(err, "Failed to load templates."));
    } finally {
      setListLoading(false);
    }
  }, []);

  const subscribeSession = useCallback(
    async (sessionId: string, afterSeq = 0) => {
      streamAbortRef.current?.abort();
      const controller = new AbortController();
      streamAbortRef.current = controller;
      try {
        await streamTemplateAnalysisSession(sessionId, applySessionEvent, controller.signal, afterSeq);
        if (!controller.signal.aborted) {
          const latest = await fetchTemplateAnalysisSession(sessionId);
          applySessionSnapshot(latest.session);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(normalizeErrorMessage(err, "Failed to stream template analysis."));
        }
      } finally {
        if (streamAbortRef.current === controller) {
          streamAbortRef.current = null;
        }
      }
    },
    [applySessionEvent, applySessionSnapshot],
  );

  useEffect(() => {
    void refreshTemplates();
    fetchApiKeyStatus()
      .then((status) => {
        const dashscope = status.providers?.dashscope;
        setHasApiKey(Boolean(dashscope?.has_key && dashscope?.validated));
      })
      .catch(() => setHasApiKey(null));
    fetchModelOptions()
      .then((options) => {
        const nextVisionConfig = options.vision_layout ?? options.vision;
        const nextPlannerConfig = options.template_planner;
        const nextVisionModels = flattenModelOptions(nextVisionConfig);
        const nextPlannerModels = flattenModelOptions(nextPlannerConfig);
        setVisionConfig(nextVisionConfig);
        setPlannerConfig(nextPlannerConfig);
        setVisionModels(nextVisionModels);
        setPlannerModels(nextPlannerModels);
        setVisionModel((current) => pickModel(nextVisionModels, current));
        setPlannerModel((current) => pickModel(nextPlannerModels, current));
      })
      .catch((err: unknown) => setError(normalizeErrorMessage(err, "Failed to load model options.")));
    fetchActiveTemplateAnalysisSession()
      .then((result) => {
        if (!result.session) return;
        applySessionSnapshot(result.session);
        if (result.session.status === "running") {
          void subscribeSession(result.session.session_id, result.session.last_seq);
        }
      })
      .catch(() => undefined);
    return () => {
      streamAbortRef.current?.abort();
    };
  }, [applySessionSnapshot, refreshTemplates, subscribeSession]);

  async function startSession(request: Promise<Awaited<ReturnType<typeof startTemplateAnalysisSession>>>) {
    setLoading(true);
    setError("");
    try {
      const result = await request;
      if (result.session) {
        applySessionSnapshot(result.session);
      }
      if (!result.ok || !result.session_id) {
        if (result.session_id && result.session?.status === "running") {
          void subscribeSession(result.session_id, result.session.last_seq);
        }
        throw new Error(result.message || "Template analysis request was not accepted.");
      }
      setFile(null);
      await refreshTemplates();
      await subscribeSession(result.session_id, result.session?.last_seq ?? 0);
    } catch (err) {
      setError(normalizeErrorMessage(err, t("template.analyze")));
    } finally {
      setLoading(false);
    }
  }

  async function onAnalyzeUpload() {
    if (!file) return;
    await startSession(startTemplateAnalysisSession(file, visionModel, plannerModel));
  }

  async function onReanalyze(template = selectedTemplate) {
    if (!template) return;
    setSelectedTemplate(template);
    await startSession(startTemplateReanalysisSession(template, visionModel, plannerModel));
  }

  async function onDelete(template: string) {
    setDeleting(template);
    setError("");
    try {
      await deleteTemplate(template);
      setTemplates((prev) => prev.filter((item) => item.name !== template));
      setSelectedTemplate((current) => (current === template ? "" : current));
      setSession((prev) => (prev?.template === template ? null : prev));
    } catch (err) {
      setError(normalizeErrorMessage(err, "Failed to delete template."));
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
            Template analysis requires a validated BYOK API key before it can run.
          </p>
          <Link
            to="/settings"
            className="inline-flex min-h-11 items-center justify-center border border-signal-amber bg-signal-amber px-4 text-xs font-bold text-night-950 transition hover:bg-white sm:w-auto"
          >
            Open settings
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
                label="Vision model"
                value={visionModel}
                options={visionModels}
                onChange={setVisionModel}
                warning={visionConfig?.warning}
              />
              <ModelSelect
                label="Planner model"
                value={plannerModel}
                options={plannerModels}
                onChange={setPlannerModel}
                warning={plannerConfig?.warning}
              />
            </div>

            <div className="mt-5">
              <Button
                className="w-full"
                onClick={onAnalyzeUpload}
                disabled={!file || !visionModel || !plannerModel || loading || hasApiKey === false}
              >
                {loading ? <Loader2 className="animate-spin" size={17} /> : <ListChecks size={17} />}
                {loading ? t("template.analyzing") : t("template.analyze")}
              </Button>
            </div>
          </Panel>

          <Panel>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="font-display text-xl font-semibold text-white">Saved templates</p>
                <p className="text-sm text-slate-500">Pick a template and rerun analysis with the current model pair.</p>
              </div>
              <FileText className="text-signal-lime" size={22} />
            </div>

            {listLoading ? (
              <div className="flex min-h-24 items-center justify-center text-slate-500">
                <Loader2 className="mr-2 animate-spin" size={16} /> Loading templates...
              </div>
            ) : templates.length === 0 ? (
              <EmptyState title="No templates yet" body="Upload a docx template to start analysis." />
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
                          {active ? " · selected" : ""}
                        </span>
                      </button>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void onReanalyze(template.name)}
                          disabled={loading || !visionModel || !plannerModel || hasApiKey === false}
                          className="inline-flex h-10 items-center gap-2 border border-white/10 px-3 text-sm text-slate-300 hover:border-signal-cyan/50 hover:text-signal-cyan disabled:opacity-50"
                          title="Reanalyze"
                        >
                          {loading && active ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                          Reanalyze
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDelete(template.name)}
                          disabled={Boolean(deleting)}
                          className="inline-flex h-10 items-center gap-2 border border-white/10 px-3 text-sm text-slate-300 hover:border-signal-rose/50 hover:text-signal-rose disabled:opacity-50"
                          title="Delete template"
                        >
                          {deleting === template.name ? <Loader2 className="animate-spin" size={16} /> : <Trash2 size={16} />}
                          Delete
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
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="font-display text-2xl font-semibold text-white">{t("template.results")}</p>
              <p className="text-sm text-slate-500">{t("template.resultsHint")}</p>
            </div>
            {session ? (
              <span className={clsx("border px-3 py-1 text-xs font-semibold", sessionStatusTone(session.status))}>
                {session.status}
              </span>
            ) : null}
          </div>

          {!session ? (
            <EmptyState title={t("template.empty")} body={t("template.emptyBody")} />
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Stat label={t("template.taskCount")} value={tasks.length} />
                <Stat label={t("template.wordTarget")} value={totalWords} tone="lime" />
                <Stat label={t("template.mode")} value={session.mode || "-"} tone="amber" />
                <Stat label="Phase" value={session.currentPhase || "-"} tone="cyan" />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 border border-white/10 bg-night-900/60 px-4 py-3 text-sm text-slate-200">
                <div className="min-w-0">
                  <p className="break-words font-semibold">{session.statusMessage || "Template analysis ready."}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {session.template || selectedTemplate || "-"} · {logs.length} log entries
                  </p>
                </div>
                <Button variant="ghost" className="min-h-10 gap-2 px-4 text-xs" onClick={() => setDetailOpen(true)}>
                  <MessageSquareText size={15} />
                  View details
                </Button>
              </div>

              {billingRecords.length > 0 ? <BillingStrip records={billingRecords} /> : null}

              {session.vision_status ? (
                <div className="border border-white/10 bg-night-950/70 px-3 py-2 text-xs leading-6 text-slate-400">
                  {session.vision_status}
                </div>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <MessageSquareText size={16} className="text-signal-cyan" />
                    Recent trace
                  </div>
                  {previewLogs.length === 0 ? (
                    <div className="border border-dashed border-white/15 bg-night-950/60 px-4 py-5 text-sm text-slate-500">
                      Waiting for session logs.
                    </div>
                  ) : (
                    <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
                      {previewLogs.map((log, index) => (
                        <div key={`${log.created_at}-${index}`} className="border border-white/10 bg-night-950/70 px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-signal-cyan">{log.phase}</p>
                          <p className="mt-2 text-sm text-slate-300">{log.message}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    {session.status === "error" ? (
                      <AlertTriangle size={16} className="text-signal-rose" />
                    ) : sessionRunning ? (
                      <Loader2 size={16} className="animate-spin text-signal-cyan" />
                    ) : (
                      <CheckCircle2 size={16} className="text-signal-lime" />
                    )}
                    Task overview
                  </div>
                  {previewTasks.length === 0 ? (
                    <div className="border border-dashed border-white/15 bg-night-950/60 px-4 py-5 text-sm text-slate-500">
                      Waiting for identified fill tasks.
                    </div>
                  ) : (
                    <div className="max-h-[360px] space-y-3 overflow-y-auto pr-1">
                      {previewTasks.map((task, index) => (
                        <TaskCard
                          key={`${task.target_chapter}-${index}`}
                          task={task}
                          index={index}
                          compact={true}
                          fallbackTaskLabel={t("template.taskFallback")}
                          fallbackPromptLabel={t("template.noPrompt")}
                          wordUnitLabel={t("template.wordUnit")}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </Panel>
      </div>

      {detailOpen && session ? (
        <DetailOverlay
          title={session.template || t("template.results")}
          subtitle={session.statusMessage || session.currentPhase || ""}
          icon={<MessageSquareText size={18} />}
          onClose={() => setDetailOpen(false)}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <Stat label={t("template.taskCount")} value={tasks.length} />
            <Stat label={t("template.wordTarget")} value={totalWords} tone="lime" />
            <Stat label={t("template.mode")} value={session.mode || "-"} tone="amber" />
            <Stat label="Status" value={session.status} tone={session.status === "error" ? "rose" : session.status === "done" ? "lime" : "cyan"} />
          </div>

          {billingRecords.length > 0 ? <BillingStrip records={billingRecords} /> : null}

          <Panel className="min-w-0">
            <div className="mb-3 flex items-center gap-2">
              <MessageSquareText size={17} className="text-signal-cyan" />
              <p className="font-display text-xl font-semibold text-white">Full trace</p>
            </div>
            {logs.length === 0 ? (
              <EmptyState title="No trace yet" body="The analysis stream will appear here as events arrive." />
            ) : (
              <div className="space-y-3">
                {logs.map((log, index) => (
                  <div key={`${log.created_at}-${index}`} className="border border-white/10 bg-night-950/70 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold uppercase tracking-[0.12em] text-signal-cyan">{log.phase}</span>
                      <span className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{log.message}</p>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel className="min-w-0">
            <div className="mb-3 flex items-center gap-2">
              <ListChecks size={17} className="text-signal-lime" />
              <p className="font-display text-xl font-semibold text-white">All fill tasks</p>
            </div>
            {tasks.length === 0 ? (
              <EmptyState title={t("template.empty")} body={t("template.emptyBody")} />
            ) : (
              <div className="space-y-3">
                {tasks.map((task, index) => (
                  <TaskCard
                    key={`${task.target_chapter}-${index}`}
                    task={task}
                    index={index}
                    fallbackTaskLabel={t("template.taskFallback")}
                    fallbackPromptLabel={t("template.noPrompt")}
                    wordUnitLabel={t("template.wordUnit")}
                  />
                ))}
              </div>
            )}
          </Panel>
        </DetailOverlay>
      ) : null}
    </>
  );
}
