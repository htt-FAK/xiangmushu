import {
  BookOpen,
  CheckCircle2,
  Cpu,
  Download,
  FileCheck2,
  FileText,
  Gauge,
  Layers3,
  Loader2,
  MessageSquareText,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
} from "lucide-react";
import { lazy, Suspense, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { downloadUrl, fetchApiKeyStatus, fetchBillingSummary, fetchKnowledgeBases, fetchTemplates, streamGenerate } from "../api";
import { Button, EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { useI18n } from "../i18n";
import type { BillingSummary, GenerateEvent, GenerationBilling, KnowledgeBase, PostFillChecks, TemplateItem } from "../types";
import { clsx } from "../utils";
import type { OutputBlockData } from "../components/OutputBlock";

const LazyOutputBlock = lazy(() => import("../components/OutputBlock").then((m) => ({ default: m.OutputBlock })));

type OutputBlock = OutputBlockData;

function formatCny(value?: number | null) {
  if (typeof value !== "number") return "-";
  return `¥${value.toFixed(4)}`;
}

function SectionTitle({
  icon,
  title,
  hint,
  action,
}: {
  icon: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-signal-cyan/25 bg-signal-cyan/10 text-signal-cyan">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="break-words font-display text-lg font-semibold leading-tight text-white">{title}</p>
          {hint && <p className="mt-1 break-words text-xs leading-5 text-slate-500">{hint}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

function OptionRail({
  items,
  value,
  onChange,
  empty,
  emptyLink,
  tone = "cyan",
  compact = false,
}: {
  items: Array<{ value: string; title: string; meta?: string }>;
  value: string;
  onChange: (value: string) => void;
  empty: string;
  emptyLink?: { to: string; label: string };
  tone?: "cyan" | "lime";
  compact?: boolean;
}) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col gap-2 border border-dashed border-white/15 bg-night-950/60 px-3 py-3">
        <span className="text-sm text-slate-500">{empty}</span>
        {emptyLink && (
          <Link
            to={emptyLink.to}
            className="inline-flex w-fit items-center gap-1.5 text-xs font-semibold text-signal-cyan hover:underline"
          >
            {emptyLink.label} →
          </Link>
        )}
      </div>
    );
  }

  return (
    <div className={clsx("grid overflow-y-auto pr-1", compact ? "max-h-52 gap-1.5" : "max-h-64 gap-2")}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            onClick={() => onChange(item.value)}
            className={clsx(
              "group flex items-center justify-between gap-3 border px-3 text-left transition active:scale-[0.98] active:brightness-90",
              compact ? "min-h-[54px] py-2" : "min-h-[64px] py-2.5",
              active
                ? tone === "lime"
                  ? "border-signal-lime/60 bg-signal-lime/10 text-signal-lime"
                  : "border-signal-cyan/60 bg-signal-cyan/10 text-signal-cyan"
                : "border-white/10 bg-night-950/70 text-slate-300 hover:border-white/25 hover:text-white",
            )}
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold">{item.title}</span>
              {item.meta && <span className="mt-1 block truncate text-xs text-slate-500">{item.meta}</span>}
            </span>
            {active && <CheckCircle2 className="shrink-0" size={17} />}
          </button>
        );
      })}
    </div>
  );
}

function TextArea({
  value,
  onChange,
  placeholder,
  compact = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  compact?: boolean;
}) {
  return (
    <textarea
      className={clsx(
        "w-full resize-y scroll-mb-32 border border-white/10 bg-night-950/70 px-3 text-sm leading-6 text-white outline-none transition placeholder:text-slate-600 focus:border-signal-cyan/70 focus:scroll-mt-4",
        compact ? "min-h-28 py-2.5" : "min-h-32 py-3",
      )}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      maxLength={1200}
    />
  );
}

function SetupField({
  label,
  children,
  compact = false,
}: {
  label: string;
  children: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className="block">
      <span
        className={clsx(
          "block text-xs uppercase text-slate-500",
          compact ? "mb-1.5 font-medium tracking-[0.1em]" : "mb-2 font-semibold tracking-[0.16em]",
        )}
      >
        {label}
      </span>
      {children}
    </div>
  );
}

export default function GeneratePage() {
  const { t } = useI18n();
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [template, setTemplate] = useState("");
  const [slug, setSlug] = useState("");
  const [generationBrief, setGenerationBrief] = useState("");
  const [wordLimit] = useState(300);
  const [topK] = useState(4);
  const [maxDistance] = useState(1.25);
  const [visualTarget] = useState(80);
  const [enableWeb] = useState(false);
  const [useStream] = useState(true);
  const [enableAudit] = useState(false);
  const [enableVisualAudit] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [currentTask, setCurrentTask] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [outputs, setOutputs] = useState<OutputBlock[]>([]);
  const [downloadPath, setDownloadPath] = useState("");
  const [reportPath, setReportPath] = useState("");
  const [reportSummary, setReportSummary] = useState("");
  const [postFillChecks, setPostFillChecks] = useState<PostFillChecks | null>(null);
  const [visualScore, setVisualScore] = useState<number | null>(null);
  const [runBilling, setRunBilling] = useState<GenerationBilling | null>(null);
  const [billingSummary, setBillingSummary] = useState<BillingSummary | null>(null);
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    Promise.allSettled([fetchTemplates(), fetchKnowledgeBases()])
      .then(([tmplResult, kbResult]) => {
        if (tmplResult.status === "fulfilled") {
          setTemplates(tmplResult.value);
          setTemplate((current) => current || tmplResult.value[0]?.name || "");
        }
        if (kbResult.status === "fulfilled") {
          setKbs(kbResult.value);
          setSlug((current) => current || kbResult.value[0]?.slug || "");
        }
        const failures: string[] = [];
        if (tmplResult.status === "rejected") failures.push(`Templates: ${tmplResult.reason}`);
        if (kbResult.status === "rejected") failures.push(`Knowledge bases: ${kbResult.reason}`);
        if (failures.length > 0) setError(failures.join("; "));
      });
    fetchBillingSummary()
      .then(setBillingSummary)
      .catch(() => undefined);
    fetchApiKeyStatus()
      .then((s) => setHasApiKey(s.has_key))
      .catch(() => setHasApiKey(null));
  }, []);

  const percent = useMemo(() => {
    if (!progress.total) return 0;
    return Math.round((progress.done / progress.total) * 100);
  }, [progress]);

  const hasAuditIssues = outputs.some((block) => (block.auditIssues?.length ?? 0) > 0);

  const checkHighlights = useMemo(() => {
    if (!postFillChecks) return [];
    return [
      ...(postFillChecks.leftover_placeholders ?? []).slice(0, 3).map((item) => `${t("generate.leftover")}${item}`),
      ...(postFillChecks.missing_chapters ?? []).slice(0, 3).map((item) => `${t("generate.missing")}${item}`),
      ...(postFillChecks.protected_issues ?? []).slice(0, 3),
    ];
  }, [postFillChecks, t]);

  function taskName(index: number) {
    return `${t("generate.taskFallback")} ${index + 1}`;
  }

  function updateOutput(index: number, patch: Partial<OutputBlock>) {
    setOutputs((prev) => {
      const next = [...prev];
      const existing = next[index] ?? {
        chapter: taskName(index),
        text: "",
        evidenceRefs: [],
        auditIssues: [],
      };
      next[index] = { ...existing, ...patch };
      return next;
    });
  }

  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
  }

  function requestStart() {
    if (!template || !slug) return;
    setConfirmOpen(true);
  }

  async function start() {
    setConfirmOpen(false);
    if (!template || !slug) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setError("");
    setOutputs([]);
    setDownloadPath("");
    setReportPath("");
    setReportSummary("");
    setPostFillChecks(null);
    setVisualScore(null);
    setRunBilling(null);
    setCurrentTask("");
    setProgress({ done: 0, total: 0 });

    const chapters: Record<number, string> = {};

    try {
      await streamGenerate(
        {
          slug,
          template,
          customInstructions: generationBrief.trim(),
          wordLimit,
          topK,
          maxDistance,
          enableWeb,
          useStream,
          enableAudit,
          enableVisualAudit,
        },
        (event: GenerateEvent) => {
          if (event.type === "task") {
            chapters[event.index] = event.chapter;
            setCurrentTask(event.chapter);
            setProgress((prev) => ({ done: prev.done, total: event.total }));
            updateOutput(event.index, { chapter: event.chapter });
            return;
          }

          if (event.type === "route") {
            updateOutput(event.index, {
              chapter: chapters[event.index] || taskName(event.index),
              model: event.model,
              tier: event.tier,
              kbHits: event.kb_hits,
              evidenceRefs: event.evidence_refs ?? [],
            });
            return;
          }

          if (event.type === "chunk") {
            setOutputs((prev) => {
              const next = [...prev];
              const existing = next[event.index] ?? {
                chapter: chapters[event.index] || taskName(event.index),
                text: "",
                evidenceRefs: [],
                auditIssues: [],
              };
              next[event.index] = { ...existing, text: `${existing.text}${event.text}` };
              return next;
            });
            return;
          }

          if (event.type === "audit") {
            updateOutput(event.index, {
              auditVerdict: event.verdict,
              auditIssues: event.issues,
              revised: event.revised,
            });
            return;
          }

          if (event.type === "billing") {
            setRunBilling((prev) => ({
              records: [...(prev?.records ?? []), event.billing],
              input_tokens: (prev?.input_tokens ?? 0) + event.billing.input_tokens,
              output_tokens: (prev?.output_tokens ?? 0) + event.billing.output_tokens,
              cost_cny: Number(((prev?.cost_cny ?? 0) + event.billing.cost_cny).toFixed(8)),
            }));
            return;
          }

          if (event.type === "progress") {
            setProgress({ done: event.index + 1, total: event.total });
            return;
          }

          if (event.type === "done") {
            setDownloadPath(event.download);
            setReportPath(event.report_download ?? "");
            setReportSummary(event.report_summary ?? "");
            setPostFillChecks(event.post_fill_checks ?? null);
            setVisualScore(event.visual_score ?? null);
            setRunBilling(event.billing ?? null);
            if (event.billing_summary) {
              setBillingSummary(event.billing_summary);
            }
            fetchBillingSummary()
              .then(setBillingSummary)
              .catch(() => undefined);
            setCurrentTask(t("generate.pass"));
            return;
          }

          if (event.type === "error") {
            setError(event.error);
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={t("generate.eyebrow")}
        title={t("generate.title")}
        description={t("generate.description")}
      />

      <ErrorBanner message={error} />

      {hasApiKey === false && (
        <div className="mb-6 flex flex-col gap-4 border border-signal-amber/40 bg-signal-amber/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between md:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <ShieldCheck className="shrink-0 text-signal-amber" size={20} />
            <p className="min-w-0 break-words text-sm font-semibold text-amber-100">{t("generate.noApiKeyHint")}</p>
          </div>
          <Link
            to="/settings"
            className="inline-flex min-h-11 items-center justify-center border border-signal-amber bg-signal-amber px-4 text-xs font-bold text-night-950 transition hover:bg-white sm:w-auto"
          >
            {t("generate.goSettings")}
          </Link>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[430px_minmax(0,1fr)]">
        <div className="space-y-5">
          <Panel className="min-w-0">
            <SectionTitle
              icon={<Sparkles size={18} />}
              title={t("generate.setupTitle")}
              hint={t("generate.setupHint")}
            />

            <div className="space-y-3 transition-all duration-200">
              <SetupField label={t("generate.knowledge")} compact={true}>
                <OptionRail
                  value={slug}
                  onChange={setSlug}
                  empty={t("generate.noKnowledge")}
                  emptyLink={{ to: "/knowledge", label: t("generate.goKnowledge") }}
                  compact={true}
                  items={kbs.map((kb) => ({
                    value: kb.slug,
                    title: kb.label || kb.name || kb.slug,
                    meta: kb.slug,
                  }))}
                />
              </SetupField>

              <SetupField label={t("generate.template")} compact={true}>
                <OptionRail
                  value={template}
                  onChange={setTemplate}
                  empty={t("generate.noTemplates")}
                  emptyLink={{ to: "/template", label: t("generate.goTemplate") }}
                  tone="lime"
                  compact={true}
                  items={templates.map((item) => ({
                    value: item.name,
                    title: item.name,
                    meta: "DOCX",
                  }))}
                />
              </SetupField>

              <SetupField label={t("generate.instructions")} compact={true}>
                <TextArea
                  value={generationBrief}
                  onChange={setGenerationBrief}
                  placeholder={t("generate.instructionsPlaceholder")}
                  compact={true}
                />
                <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span className="flex min-w-0 items-center gap-2">
                    <MessageSquareText className="shrink-0 text-signal-cyan" size={15} />
                    <span className="break-words">{t("generate.instructionsHint")}</span>
                  </span>
                  <span className="shrink-0">{generationBrief.length}/1200</span>
                </div>
              </SetupField>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]">
              <Button
                className="min-h-14 w-full text-base font-bold shadow-glow"
                onClick={requestStart}
                disabled={!template || !slug || running}
              >
                {running ? <Loader2 className="animate-spin" size={19} /> : <Play size={19} />}
                {running ? t("generate.running") : t("generate.start")}
              </Button>
              <Button
                className="min-h-14 w-full font-bold sm:w-12 sm:px-0"
                variant="ghost"
                onClick={stop}
                disabled={!running}
                aria-label={t("generate.stop")}
              >
                <Square size={17} />
              </Button>
            </div>
          </Panel>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel className="min-w-0">
            <SectionTitle
              icon={<Gauge size={18} />}
              title={t("generate.runOverview")}
              hint={t("generate.runOverviewHint")}
              action={
                <span className={clsx("shrink-0 border px-2.5 py-1 text-xs font-semibold", running ? "border-signal-lime/40 bg-signal-lime/10 text-signal-lime" : "border-white/10 bg-white/[0.035] text-slate-500")}>
                  {running ? t("generate.running") : t("generate.idle")}
                </span>
              }
            />

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              <Stat label={t("generate.progress")} value={`${percent}%`} />
              <Stat label={t("generate.doneTasks")} value={`${progress.done}/${progress.total || "-"}`} tone="lime" />
              <Stat className="col-span-2 md:col-span-1" label={t("generate.currentTask")} value={currentTask || "-"} tone="amber" />
              <Stat
                label={t("generate.visualScore")}
                value={visualScore === null ? "-" : visualScore}
                tone={visualScore !== null && visualScore < visualTarget ? "rose" : "cyan"}
              />
              <Stat label={t("generate.runCost")} value={formatCny(runBilling?.cost_cny)} tone="lime" />
            </div>

            <div className="mt-5 border border-white/10 bg-night-950 p-1">
              <div
                className="h-2 bg-[linear-gradient(90deg,#36f2e6,#b8ff5e)] transition-all"
                style={{ width: `${percent}%` }}
              />
            </div>
          </Panel>

          <Panel className="min-w-0">
            <SectionTitle
              icon={<BookOpen size={18} />}
              title={t("generate.outputTitle")}
              hint={t("generate.outputHint")}
            />
            {outputs.length === 0 ? (
              <EmptyState title={t("generate.waitingOutput")} body={t("generate.waitingOutputBody")} />
            ) : (
              <div className="space-y-4">
                {outputs.map((block, index) => (
                  <Suspense key={`${block.chapter}-${index}`} fallback={<div className="min-h-24 border border-white/10 bg-night-950/70 p-4 text-sm text-slate-500">Loading...</div>}>
                    <LazyOutputBlock
                      block={block}
                      fallbackName={taskName(index)}
                      waitingText={t("generate.waitingModel")}
                      auditResultLabel={t("generate.auditResult")}
                      revisedLabel={t("generate.revised")}
                    />
                  </Suspense>
                ))}
              </div>
            )}
          </Panel>

          {(downloadPath || reportPath || reportSummary || postFillChecks) && (
            <Panel className="min-w-0">
              <SectionTitle
                icon={<FileCheck2 size={18} />}
                title={t("generate.acceptance")}
                hint={t("generate.acceptanceHint")}
              />

              {(downloadPath || reportPath) && (
                <div className="mb-5 flex flex-wrap gap-3">
                  {downloadPath && (
                    <a
                      className="inline-flex min-h-12 w-full items-center justify-center gap-2 border border-signal-lime bg-signal-lime px-4 text-sm font-bold text-night-950 sm:min-h-11 sm:w-auto sm:font-semibold"
                      href={downloadUrl(downloadPath)}
                    >
                      <Download size={17} />
                      {t("generate.downloadDoc")}
                    </a>
                  )}
                  {reportPath && (
                    <a
                      className="inline-flex min-h-12 w-full items-center justify-center gap-2 border border-white/10 bg-white/[0.055] px-4 text-sm font-bold text-slate-100 sm:min-h-11 sm:w-auto sm:font-semibold"
                      href={downloadUrl(reportPath)}
                    >
                      <FileText size={17} />
                      {t("generate.downloadReport")}
                    </a>
                  )}
                </div>
              )}

              {reportSummary && <p className="mb-4 break-words text-sm leading-7 text-slate-300">{reportSummary}</p>}

              {postFillChecks && (
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="min-w-0 border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{t("generate.checkResult")}</p>
                    <p className="mt-2 text-white">{postFillChecks.ok ? t("generate.pass") : t("generate.review")}</p>
                    <p className="mt-2 break-words text-xs text-slate-400">
                      template words {postFillChecks.template_words ?? "-"} / output words{" "}
                      {postFillChecks.output_words ?? "-"}
                    </p>
                  </div>
                  <div className="min-w-0 border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{t("generate.structure")}</p>
                    <p className="mt-2 break-words text-white">
                      template tables {postFillChecks.template_tables ?? "-"} / output tables{" "}
                      {postFillChecks.output_tables ?? "-"}
                    </p>
                    <p className="mt-2 break-words text-xs text-slate-400">
                      cover {postFillChecks.cover_modified ? t("generate.review") : t("generate.pass")}, rating table{" "}
                      {postFillChecks.rating_table_modified ? t("generate.review") : t("generate.pass")}
                    </p>
                  </div>
                </div>
              )}
            </Panel>
          )}

          {(hasAuditIssues || checkHighlights.length > 0 || visualScore !== null) && (
            <Panel className="min-w-0">
              <SectionTitle
                icon={<Search size={18} />}
                title={t("generate.auditPanelTitle")}
                hint={t("generate.auditPanelHint")}
              />
              <div className="grid gap-3 md:grid-cols-3">
                <div className="border border-white/10 bg-night-950/70 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.visualTarget")}</p>
                  <p className="mt-2 font-display text-2xl font-semibold text-signal-cyan">{visualTarget}</p>
                </div>
                <div className="border border-white/10 bg-night-950/70 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.auditIssues")}</p>
                  <p className={clsx("mt-2 font-display text-2xl font-semibold", hasAuditIssues || checkHighlights.length ? "text-signal-amber" : "text-signal-lime")}>
                    {outputs.reduce((sum, block) => sum + (block.auditIssues?.length ?? 0), 0) + checkHighlights.length}
                  </p>
                </div>
                <div className="border border-white/10 bg-night-950/70 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.retrievalProfile")}</p>
                  <p className="mt-2 font-display text-2xl font-semibold text-signal-lime">
                    {topK}/{maxDistance}
                  </p>
                </div>
              </div>
              {checkHighlights.length > 0 && (
                <div className="mt-3 space-y-2">
                  {checkHighlights.map((item) => (
                    <div
                      key={item}
                      className="break-words border border-signal-amber/30 bg-signal-amber/10 px-3 py-2 text-sm text-amber-100"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {(runBilling || billingSummary) && (
            <Panel className="min-w-0">
              <SectionTitle
                icon={<Cpu size={18} />}
                title={t("generate.billingTitle")}
                hint={t("generate.billingHint")}
              />
              <div className="grid gap-3 md:grid-cols-3">
                <Stat label={t("generate.runCost")} value={formatCny(runBilling?.cost_cny)} tone="lime" />
                <Stat label={t("generate.inputTokens")} value={runBilling?.input_tokens ?? "-"} />
                <Stat label={t("generate.outputTokens")} value={runBilling?.output_tokens ?? "-"} tone="amber" />
              </div>
              {billingSummary && (
                <p className="mt-3 break-words border border-white/10 bg-night-950/70 px-3 py-2 text-xs leading-5 text-slate-500">
                  {t("generate.totalCost")}: {formatCny(billingSummary.cost_cny)} · {billingSummary.generation_count} runs
                </p>
              )}
            </Panel>
          )}
        </div>
      </div>

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-night-950/90 px-4 py-6 backdrop-blur">
          <div className="w-full max-w-md border border-white/10 bg-night-900 p-5 shadow-panel md:p-6">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan">
                <Layers3 size={19} />
              </div>
              <h3 className="font-display text-xl font-semibold text-white">{t("generate.confirmTitle")}</h3>
            </div>
            <p className="text-sm leading-7 text-slate-300">{t("generate.confirmBody")}</p>
            <div className="mt-5 grid gap-3 sm:flex sm:justify-end">
              <Button className="min-h-12 w-full sm:w-auto" variant="ghost" onClick={() => setConfirmOpen(false)}>
                {t("generate.cancel")}
              </Button>
              <Button className="min-h-12 w-full font-bold sm:w-auto" onClick={start}>
                <Play size={17} />
                {t("generate.confirmStart")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
