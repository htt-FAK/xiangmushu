import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Cpu,
  Database,
  Download,
  FileCheck2,
  FileSearch,
  FileText,
  Gauge,
  Layers3,
  Loader2,
  MessageSquareText,
  PenTool,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
} from "lucide-react";
import { lazy, Suspense, type ReactNode, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { fetchApiKeyStatus, fetchBillingSummary, fetchKnowledgeBases, fetchTemplates, handleDownload, streamGenerate } from "../api";
import type { OutputBlockData } from "../components/OutputBlock";
import { Button, EmptyState, ErrorBanner, Input, PageHeader, Panel, Stat } from "../components/ui";
import { useI18n } from "../i18n";
import type {
  BillingSummary,
  GenerateEvent,
  GenerateParams,
  GenerationBilling,
  KnowledgeBase,
  PostFillChecks,
  TemplateItem,
} from "../types";
import { clsx } from "../utils";

const LazyOutputBlock = lazy(() => import("../components/OutputBlock").then((m) => ({ default: m.OutputBlock })));

type OutputBlock = OutputBlockData;
type RailItem = { value: string; title: string; meta?: string };
type GenerateStep = "idle" | "retrieval" | "analysis" | "generation" | "audit" | "done";

const stepOrder: GenerateStep[] = ["idle", "retrieval", "analysis", "generation", "audit", "done"];

function formatCny(value?: number | null) {
  if (typeof value !== "number") return "-";
  return `¥${value.toFixed(4)}`;
}

function normalizeRailQuery(value: string) {
  return value.trim().toLowerCase();
}

function filterRailItems(items: RailItem[], query: string) {
  const normalized = normalizeRailQuery(query);
  if (!normalized) return items;
  return items.filter((item) => `${item.title} ${item.meta ?? ""}`.toLowerCase().includes(normalized));
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
  emptyFiltered,
  emptyLink,
  tone = "cyan",
  compact = false,
  searchValue,
  onSearchChange,
  searchPlaceholder,
  disabled = false,
}: {
  items: RailItem[];
  value: string;
  onChange: (value: string) => void;
  empty: string;
  emptyFiltered?: string;
  emptyLink?: { to: string; label: string };
  tone?: "cyan" | "lime";
  compact?: boolean;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  disabled?: boolean;
}) {
  const emptyMessage = searchValue ? emptyFiltered || empty : empty;

  return (
    <div className="space-y-3">
      {onSearchChange && (
        <Input
          className="md:hidden"
          value={searchValue ?? ""}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={searchPlaceholder}
        />
      )}

      {items.length === 0 ? (
        <div className="flex flex-col gap-2 border border-dashed border-white/15 bg-night-950/60 px-3 py-3">
          <span className="text-sm text-slate-500">{emptyMessage}</span>
          {emptyLink && !searchValue && (
            <Link
              to={emptyLink.to}
              className="inline-flex w-fit items-center gap-1.5 text-xs font-semibold text-signal-cyan hover:underline"
            >
              {emptyLink.label} →
            </Link>
          )}
        </div>
      ) : (
        <div
          className={clsx(
            "grid overflow-y-auto pr-1",
            compact ? "max-h-52 gap-1.5" : "max-h-64 gap-2",
            "grid-cols-2 md:grid-cols-1",
          )}
        >
          {items.map((item) => {
            const active = item.value === value;
            return (
              <button
                key={item.value}
                type="button"
                disabled={disabled}
                onClick={() => onChange(item.value)}
                className={clsx(
                  "group flex h-full min-w-0 items-start justify-between gap-3 border px-3 text-left transition active:scale-[0.98] active:brightness-90 disabled:pointer-events-none disabled:opacity-45",
                  compact ? "min-h-[72px] py-2.5 md:min-h-[54px] md:py-2" : "min-h-[82px] py-3 md:min-h-[64px] md:py-2.5",
                  active
                    ? tone === "lime"
                      ? "border-signal-lime/60 bg-signal-lime/10 text-signal-lime"
                      : "border-signal-cyan/60 bg-signal-cyan/10 text-signal-cyan"
                    : "border-white/10 bg-night-950/70 text-slate-300 hover:border-white/25 hover:text-white",
                )}
              >
                <span className="min-w-0">
                  <span className="block break-words text-sm font-semibold leading-5 md:truncate">{item.title}</span>
                  {item.meta && <span className="mt-1 block break-all text-xs text-slate-500 md:truncate">{item.meta}</span>}
                </span>
                {active && <CheckCircle2 className="mt-0.5 shrink-0" size={17} />}
              </button>
            );
          })}
        </div>
      )}
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
  const [qualityMode, setQualityMode] = useState<"balanced" | "quality" | "speed">("balanced");
  const [enableWeb] = useState(false);
  const [useStream] = useState(true);
  const [enableAudit] = useState(false);
  const [enableVisualAudit] = useState(true);
  const [currentStep, setCurrentStep] = useState<GenerateStep>("idle");
  const [running, setRunning] = useState(false);
  const [regeneratingIndex, setRegeneratingIndex] = useState<number | null>(null);
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
  const [traceOpen, setTraceOpen] = useState(false);
  const [downloadingDoc, setDownloadingDoc] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [knowledgeSearch, setKnowledgeSearch] = useState("");
  const [templateSearch, setTemplateSearch] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const sectionAbortRef = useRef<AbortController | null>(null);
  const visualTarget = 80;
  const busy = running || regeneratingIndex !== null;
  const deferredKnowledgeSearch = useDeferredValue(knowledgeSearch);
  const deferredTemplateSearch = useDeferredValue(templateSearch);

  const recommendedConfig = useMemo(() => {
    if (!template || !slug) return null;
    const kb = kbs.find((item) => item.slug === slug) as KnowledgeBase & { document_count?: number } | undefined;
    const isComplex = /项目|方案|报告|论文|project|proposal|report|paper/i.test(template);
    const hasRichKB = (kb?.document_count ?? 0) > 10;

    return {
      qualityMode: (isComplex ? "quality" : "balanced") as "balanced" | "quality",
      enableWeb: !hasRichKB,
      enableAudit: isComplex,
    };
  }, [template, slug, kbs]);

  const knowledgeItems = useMemo<RailItem[]>(
    () =>
      kbs.map((kb) => ({
        value: kb.slug,
        title: kb.label || kb.name || kb.slug,
        meta: kb.slug,
      })),
    [kbs],
  );

  const templateItems = useMemo<RailItem[]>(
    () =>
      templates.map((item) => ({
        value: item.name,
        title: item.name,
        meta: "DOCX",
      })),
    [templates],
  );

  const filteredKnowledgeItems = useMemo(
    () => filterRailItems(knowledgeItems, deferredKnowledgeSearch),
    [knowledgeItems, deferredKnowledgeSearch],
  );

  const filteredTemplateItems = useMemo(
    () => filterRailItems(templateItems, deferredTemplateSearch),
    [templateItems, deferredTemplateSearch],
  );

  useEffect(() => {
    Promise.allSettled([fetchTemplates(), fetchKnowledgeBases()]).then(([templateResult, kbResult]) => {
      if (templateResult.status === "fulfilled") {
        setTemplates(templateResult.value);
        setTemplate((current) => current || templateResult.value[0]?.name || "");
      }
      if (kbResult.status === "fulfilled") {
        setKbs(kbResult.value);
        setSlug((current) => current || kbResult.value[0]?.slug || "");
      }

      const failures: string[] = [];
      if (templateResult.status === "rejected") failures.push(`Templates: ${templateResult.reason}`);
      if (kbResult.status === "rejected") failures.push(`Knowledge bases: ${kbResult.reason}`);
      if (failures.length > 0) {
        setError(JSON.stringify({ level: "warning", message: failures.join("; "), retryable: true }));
      }
    });

    fetchBillingSummary()
      .then(setBillingSummary)
      .catch(() => undefined);
    fetchApiKeyStatus()
      .then((status) => setHasApiKey(status.has_key))
      .catch(() => setHasApiKey(null));
  }, []);

  useEffect(() => {
    if (recommendedConfig && !busy) {
      setQualityMode(recommendedConfig.qualityMode);
    }
  }, [recommendedConfig, busy]);

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

  function StepIndicator({ step, label, icon }: { step: GenerateStep; label: string; icon: ReactNode }) {
    const isActive = currentStep === step;
    const isCompleted = stepOrder.indexOf(currentStep) > stepOrder.indexOf(step);

    return (
      <div
        className={clsx(
          "flex items-center gap-2 rounded-lg border px-3 py-2 transition-all",
          isActive
            ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
            : isCompleted
              ? "border-signal-lime/50 bg-signal-lime/5 text-signal-lime"
              : "border-white/10 bg-night-950/50 text-slate-500",
        )}
      >
        <div className="shrink-0">{icon}</div>
        <span className="text-xs font-medium">{label}</span>
        {isActive && <Loader2 className="ml-auto animate-spin" size={14} />}
        {isCompleted && <CheckCircle2 className="ml-auto" size={14} />}
      </div>
    );
  }

  function taskName(index: number) {
    return `${t("generate.taskFallback")} ${index + 1}`;
  }

  function createOutputShell(index: number, chapter?: string): OutputBlock {
    return {
      chapter: chapter || taskName(index),
      text: "",
      evidenceRefs: [],
      auditIssues: [],
    };
  }

  function updateOutput(index: number, patch: Partial<OutputBlock>) {
    setOutputs((prev) => {
      const next = [...prev];
      const existing = next[index] ?? createOutputShell(index);
      next[index] = { ...existing, ...patch };
      return next;
    });
  }

  function appendOutputChunk(index: number, text: string, chapter?: string) {
    setOutputs((prev) => {
      const next = [...prev];
      const existing = next[index] ?? createOutputShell(index, chapter);
      next[index] = { ...existing, chapter: chapter || existing.chapter, text: `${existing.text}${text}` };
      return next;
    });
  }

  function refreshBillingSummary() {
    fetchBillingSummary()
      .then(setBillingSummary)
      .catch(() => undefined);
  }

  function getParamsByQuality() {
    switch (qualityMode) {
      case "quality":
        return { topK: 6, maxDistance: 1.0, wordLimit: 500 };
      case "speed":
        return { topK: 2, maxDistance: 1.5, wordLimit: 200 };
      default:
        return { topK: 4, maxDistance: 1.25, wordLimit: 300 };
    }
  }

  function buildGenerateParams(): GenerateParams {
    const params = getParamsByQuality();
    return {
      slug,
      template,
      customInstructions: generationBrief.trim(),
      wordLimit: params.wordLimit,
      topK: params.topK,
      maxDistance: params.maxDistance,
      enableWeb,
      useStream,
      enableAudit,
      enableVisualAudit,
    };
  }

  function handleStreamError(message: string) {
    setError(JSON.stringify({ level: "error", message, retryable: true }));
  }

  function stop() {
    abortRef.current?.abort();
    sectionAbortRef.current?.abort();
    abortRef.current = null;
    sectionAbortRef.current = null;
    setRunning(false);
    setRegeneratingIndex(null);
  }

  function requestStart() {
    if (!template || !slug || busy) return;
    setConfirmOpen(true);
  }

  async function start() {
    setConfirmOpen(false);
    if (!template || !slug) return;

    const controller = new AbortController();
    const chapters: Record<number, string> = {};

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
    setCurrentStep("retrieval");

    try {
      await streamGenerate(
        buildGenerateParams(),
        (event) => {
          if (event.type === "task") {
            chapters[event.index] = event.chapter;
            setCurrentTask(event.chapter);
            setCurrentStep("generation");
            setProgress((prev) => ({ done: prev.done, total: event.total }));
            updateOutput(event.index, {
              chapter: event.chapter,
              text: "",
              model: undefined,
              tier: undefined,
              kbHits: undefined,
              evidenceRefs: [],
              auditVerdict: undefined,
              auditIssues: [],
              revised: false,
            });
            return;
          }

          if (event.type === "route") {
            setCurrentStep("retrieval");
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
            appendOutputChunk(event.index, event.text, chapters[event.index]);
            return;
          }

          if (event.type === "audit") {
            setCurrentStep("audit");
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
            setCurrentStep("done");
            setDownloadPath(event.download);
            setReportPath(event.report_download ?? "");
            setReportSummary(event.report_summary ?? "");
            setPostFillChecks(event.post_fill_checks ?? null);
            setVisualScore(event.visual_score ?? null);
            setRunBilling(event.billing ?? null);
            if (event.billing_summary) {
              setBillingSummary(event.billing_summary);
            }
            refreshBillingSummary();
            setCurrentTask(t("generate.pass"));
            return;
          }

          if (event.type === "error") {
            handleStreamError(event.error);
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      abortRef.current = null;
      setRunning(false);
    }
  }

  async function regenerateSection(index: number) {
    if (!template || !slug || running || regeneratingIndex !== null) return;

    const previousBlock = outputs[index];
    if (!previousBlock) return;

    const controller = new AbortController();
    const chapters: Record<number, string> = {};
    let failed = false;

    sectionAbortRef.current = controller;
    setRegeneratingIndex(index);
    setError("");

    try {
      await streamGenerate(
        buildGenerateParams(),
        (event) => {
          if (event.type === "task") {
            chapters[event.index] = event.chapter;
            if (event.index !== index) return;
            updateOutput(index, {
              chapter: event.chapter,
              text: "",
              model: undefined,
              tier: undefined,
              kbHits: undefined,
              evidenceRefs: [],
              auditVerdict: undefined,
              auditIssues: [],
              revised: false,
            });
            return;
          }

          if (event.type === "route" && event.index === index) {
            updateOutput(index, {
              chapter: chapters[event.index] || previousBlock.chapter || taskName(index),
              model: event.model,
              tier: event.tier,
              kbHits: event.kb_hits,
              evidenceRefs: event.evidence_refs ?? [],
            });
            return;
          }

          if (event.type === "chunk" && event.index === index) {
            appendOutputChunk(index, event.text, chapters[event.index] || previousBlock.chapter);
            return;
          }

          if (event.type === "audit" && event.index === index) {
            updateOutput(index, {
              auditVerdict: event.verdict,
              auditIssues: event.issues,
              revised: event.revised,
            });
            return;
          }

          if (event.type === "done") {
            refreshBillingSummary();
            return;
          }

          if (event.type === "error") {
            failed = true;
            handleStreamError(event.error);
            controller.abort();
          }
        },
        controller.signal,
      );
    } catch (err) {
      failed = true;
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if ((failed || controller.signal.aborted) && previousBlock) {
        setOutputs((prev) => {
          const next = [...prev];
          next[index] = previousBlock;
          return next;
        });
      }
      sectionAbortRef.current = null;
      setRegeneratingIndex(null);
    }
  }

  function renderOutputBlocks(actionsEnabled: boolean) {
    return outputs.map((block, index) => (
      <Suspense
        key={`${block.chapter}-${index}`}
        fallback={<div className="min-h-24 border border-white/10 bg-night-950/70 p-4 text-sm text-slate-500">Loading...</div>}
      >
        <LazyOutputBlock
          block={block}
          fallbackName={taskName(index)}
          waitingText={t("generate.waitingModel")}
          auditResultLabel={t("generate.auditResult")}
          revisedLabel={t("generate.revised")}
          busy={regeneratingIndex === index}
          busyLabel={t("generate.regenerating")}
          action={
            actionsEnabled ? (
              <Button
                variant="ghost"
                className="min-h-10 gap-2 px-3 text-xs"
                disabled={busy}
                onClick={() => regenerateSection(index)}
              >
                {regeneratingIndex === index ? <Loader2 className="animate-spin" size={15} /> : <RotateCcw size={15} />}
                {regeneratingIndex === index ? t("generate.regenerating") : t("generate.regenerateChapter")}
              </Button>
            ) : undefined
          }
        />
      </Suspense>
    ));
  }

  return (
    <>
      <PageHeader eyebrow={t("generate.eyebrow")} title={t("generate.title")} description={t("generate.description")} />

      {error &&
        (() => {
          try {
            const errorObj = JSON.parse(error);
            const isTypedError = typeof errorObj === "object" && errorObj?.level;
            if (!isTypedError) return <ErrorBanner message={error} />;

            const { level, message, retryable } = errorObj as { level: "warning" | "error" | "info"; message: string; retryable?: boolean };
            const styles = {
              warning: "border-signal-amber/40 bg-signal-amber/10 text-amber-100",
              error: "border-rose-500/40 bg-rose-500/10 text-rose-100",
              info: "border-signal-cyan/40 bg-signal-cyan/10 text-cyan-100",
            };
            const icons = {
              warning: <AlertTriangle className="shrink-0" size={20} />,
              error: <AlertTriangle className="shrink-0" size={20} />,
              info: <MessageSquareText className="shrink-0" size={20} />,
            };

            return (
              <div
                className={clsx(
                  "mb-6 flex flex-col gap-4 border px-4 py-4 sm:flex-row sm:items-center sm:justify-between md:px-5",
                  styles[level] || styles.error,
                )}
              >
                <div className="flex min-w-0 items-center gap-3">
                  {icons[level] || icons.error}
                  <p className="min-w-0 break-words text-sm font-semibold">{message}</p>
                </div>
                {retryable && (
                  <button
                    onClick={() => setError("")}
                    className="inline-flex min-h-11 items-center justify-center border border-current px-4 text-xs font-bold transition hover:bg-white/10 sm:w-auto"
                  >
                    重试
                  </button>
                )}
              </div>
            );
          } catch {
            return <ErrorBanner message={error} />;
          }
        })()}

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
            <SectionTitle icon={<Sparkles size={18} />} title={t("generate.setupTitle")} hint={t("generate.setupHint")} />

            <div className="space-y-3 transition-all duration-200">
              <SetupField label={t("generate.knowledge")} compact={true}>
                <OptionRail
                  value={slug}
                  onChange={setSlug}
                  empty={t("generate.noKnowledge")}
                  emptyFiltered={t("generate.noMatchingKnowledgeBase")}
                  emptyLink={{ to: "/knowledge", label: t("generate.goKnowledge") }}
                  compact={true}
                  disabled={busy}
                  items={filteredKnowledgeItems}
                  searchValue={knowledgeSearch}
                  onSearchChange={setKnowledgeSearch}
                  searchPlaceholder={t("generate.searchKnowledgeBase")}
                />
              </SetupField>

              <SetupField label={t("generate.template")} compact={true}>
                <OptionRail
                  value={template}
                  onChange={setTemplate}
                  empty={t("generate.noTemplates")}
                  emptyFiltered={t("generate.noMatchingTemplate")}
                  emptyLink={{ to: "/template", label: t("generate.goTemplate") }}
                  tone="lime"
                  compact={true}
                  disabled={busy}
                  items={filteredTemplateItems}
                  searchValue={templateSearch}
                  onSearchChange={setTemplateSearch}
                  searchPlaceholder={t("generate.searchTemplate")}
                />
              </SetupField>

              {recommendedConfig && !busy && (
                <div className="mb-2 flex items-start gap-2 border border-dashed border-signal-cyan/30 bg-signal-cyan/5 px-3 py-2.5 text-xs">
                  <Sparkles className="mt-0.5 shrink-0 text-signal-cyan" size={14} />
                  <div className="min-w-0">
                    <p className="font-semibold text-signal-cyan">Smart defaults active</p>
                    <p className="mt-0.5 break-words text-slate-400">
                      {recommendedConfig.qualityMode === "quality" ? "Quality first" : "Balanced mode"}
                      {recommendedConfig.enableWeb ? " + web enrichment" : ""}
                      {recommendedConfig.enableAudit ? " + content audit" : ""}
                    </p>
                  </div>
                </div>
              )}

              <SetupField label={t("generate.qualityMode")} compact={true}>
                <div className="grid grid-cols-3 gap-2">
                  {(["speed", "balanced", "quality"] as const).map((mode) => {
                    const labels = {
                      speed: "速度优先",
                      balanced: "平衡模式",
                      quality: "质量优先",
                    };
                    const descriptions = {
                      speed: "更快完成基础草稿。",
                      balanced: "兼顾速度和质量。",
                      quality: "更适合复杂文档。",
                    };

                    return (
                      <button
                        key={mode}
                        type="button"
                        disabled={busy}
                        onClick={() => setQualityMode(mode)}
                        className={clsx(
                          "border px-3 py-2.5 text-left transition hover:border-white/25 disabled:pointer-events-none disabled:opacity-45",
                          qualityMode === mode
                            ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
                            : "border-white/10 bg-night-950/70 text-slate-300",
                        )}
                      >
                        <span className="block text-xs font-semibold">{labels[mode]}</span>
                        <span className="mt-0.5 block text-[10px] text-slate-500">{descriptions[mode]}</span>
                      </button>
                    );
                  })}
                </div>
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
              <Button className="min-h-14 w-full text-base font-bold shadow-glow" onClick={requestStart} disabled={!template || !slug || busy}>
                {running ? <Loader2 className="animate-spin" size={19} /> : <Play size={19} />}
                {running ? t("generate.running") : t("generate.start")}
              </Button>
              <Button
                className="min-h-14 w-full font-bold sm:w-12 sm:px-0"
                variant="ghost"
                onClick={stop}
                disabled={!busy}
                aria-label={t("generate.stop")}
              >
                <Square size={17} />
              </Button>
            </div>
          </Panel>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel className="min-w-0">
            {running && (
              <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
                <StepIndicator step="retrieval" label={t("generate.stepRetrieval")} icon={<Database size={16} />} />
                <StepIndicator step="analysis" label={t("generate.stepAnalysis")} icon={<FileSearch size={16} />} />
                <StepIndicator step="generation" label={t("generate.stepGeneration")} icon={<PenTool size={16} />} />
                <StepIndicator step="audit" label={t("generate.stepAudit")} icon={<ShieldCheck size={16} />} />
                <StepIndicator step="done" label={t("generate.stepDone")} icon={<CheckCircle2 size={16} />} />
              </div>
            )}

            <SectionTitle
              icon={<Gauge size={18} />}
              title={t("generate.runOverview")}
              hint={t("generate.runOverviewHint")}
              action={
                <span
                  className={clsx(
                    "shrink-0 border px-2.5 py-1 text-xs font-semibold",
                    busy ? "border-signal-lime/40 bg-signal-lime/10 text-signal-lime" : "border-white/10 bg-white/[0.035] text-slate-500",
                  )}
                >
                  {running ? t("generate.running") : regeneratingIndex !== null ? t("generate.regenerating") : t("generate.idle")}
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
              <div className="h-2 bg-[linear-gradient(90deg,#36f2e6,#b8ff5e)] transition-all" style={{ width: `${percent}%` }} />
            </div>
          </Panel>

          <Panel className="min-w-0">
            <SectionTitle icon={<BookOpen size={18} />} title={t("generate.outputTitle")} hint={t("generate.outputHint")} />
            {outputs.length === 0 ? (
              <EmptyState title={t("generate.waitingOutput")} body={t("generate.waitingOutputBody")} />
            ) : (
              <div className="space-y-4">
                {downloadPath && !running && (
                  <div className="flex justify-center py-1">
                    <Button
                      variant="ghost"
                      className="min-h-11 gap-2 border border-white/10 bg-white/[0.035] px-5 text-sm font-semibold text-slate-200 hover:border-white/25 hover:text-white"
                      onClick={() => setTraceOpen(true)}
                    >
                      <MessageSquareText size={17} />
                      {t("generate.viewTrace")}
                    </Button>
                  </div>
                )}
                {renderOutputBlocks(true)}
              </div>
            )}
          </Panel>

          {(downloadPath || reportPath || reportSummary || postFillChecks) && (
            <Panel className="min-w-0">
              <SectionTitle icon={<FileCheck2 size={18} />} title={t("generate.acceptance")} hint={t("generate.acceptanceHint")} />

              {(downloadPath || reportPath) && (
                <div className="mb-5 flex flex-wrap gap-3">
                  {downloadPath && (
                    <button
                      type="button"
                      disabled={downloadingDoc}
                      className="inline-flex min-h-12 w-full items-center justify-center gap-2 border border-signal-lime bg-signal-lime px-4 text-sm font-bold text-night-950 transition hover:bg-signal-lime/90 disabled:opacity-60 sm:min-h-11 sm:w-auto sm:font-semibold"
                      onClick={async () => {
                        setDownloadingDoc(true);
                        try {
                          await handleDownload(downloadPath);
                        } catch {
                          setError(t("generate.downloadFailed"));
                        } finally {
                          setDownloadingDoc(false);
                        }
                      }}
                    >
                      {downloadingDoc ? <Loader2 className="animate-spin" size={17} /> : <Download size={17} />}
                      {t("generate.downloadDoc")}
                    </button>
                  )}
                  {reportPath && (
                    <button
                      type="button"
                      disabled={downloadingReport}
                      className="inline-flex min-h-12 w-full items-center justify-center gap-2 border border-white/10 bg-white/[0.055] px-4 text-sm font-bold text-slate-100 transition hover:bg-white/10 disabled:opacity-60 sm:min-h-11 sm:w-auto sm:font-semibold"
                      onClick={async () => {
                        setDownloadingReport(true);
                        try {
                          await handleDownload(reportPath);
                        } catch {
                          setError(t("generate.downloadFailed"));
                        } finally {
                          setDownloadingReport(false);
                        }
                      }}
                    >
                      {downloadingReport ? <Loader2 className="animate-spin" size={17} /> : <FileText size={17} />}
                      {t("generate.downloadReport")}
                    </button>
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
                      template words {postFillChecks.template_words ?? "-"} / output words {postFillChecks.output_words ?? "-"}
                    </p>
                  </div>
                  <div className="min-w-0 border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{t("generate.structure")}</p>
                    <p className="mt-2 break-words text-white">
                      template tables {postFillChecks.template_tables ?? "-"} / output tables {postFillChecks.output_tables ?? "-"}
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
              <SectionTitle icon={<Search size={18} />} title={t("generate.auditPanelTitle")} hint={t("generate.auditPanelHint")} />
              <div className="grid gap-3 md:grid-cols-3">
                <div className="border border-white/10 bg-night-950/70 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.visualTarget")}</p>
                  <p className="mt-2 font-display text-2xl font-semibold text-signal-cyan">{visualTarget}</p>
                </div>
                <div className="border border-white/10 bg-night-950/70 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.auditIssues")}</p>
                  <p
                    className={clsx(
                      "mt-2 font-display text-2xl font-semibold",
                      hasAuditIssues || checkHighlights.length ? "text-signal-amber" : "text-signal-lime",
                    )}
                  >
                    {outputs.reduce((sum, block) => sum + (block.auditIssues?.length ?? 0), 0) + checkHighlights.length}
                  </p>
                </div>
                <div className="border border-white/10 bg-night-950/70 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.qualityMode")}</p>
                  <p className="mt-2 font-display text-lg font-semibold text-signal-lime">
                    {qualityMode === "quality" ? "质量优先" : qualityMode === "speed" ? "速度优先" : "平衡模式"}
                  </p>
                </div>
              </div>
              {checkHighlights.length > 0 && (
                <div className="mt-3 space-y-2">
                  {checkHighlights.map((item) => (
                    <div key={item} className="break-words border border-signal-amber/30 bg-signal-amber/10 px-3 py-2 text-sm text-amber-100">
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {(runBilling || billingSummary) && (
            <Panel className="min-w-0">
              <SectionTitle icon={<Cpu size={18} />} title={t("generate.billingTitle")} hint={t("generate.billingHint")} />
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

      {traceOpen && (
        <div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-night-950/95 backdrop-blur">
          <div className="flex shrink-0 items-center justify-between border-b border-white/10 px-4 py-3 md:px-6">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan">
                <MessageSquareText size={18} />
              </div>
              <h3 className="font-display text-lg font-semibold text-white">{t("generate.traceTitle")}</h3>
            </div>
            <button
              type="button"
              onClick={() => setTraceOpen(false)}
              className="flex h-9 w-9 items-center justify-center border border-white/10 text-slate-400 transition hover:border-white/25 hover:text-white"
              aria-label="Close"
            >
              <span className="text-xl leading-none">&times;</span>
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
            <div className="mx-auto max-w-4xl space-y-4">{renderOutputBlocks(false)}</div>
          </div>
        </div>
      )}

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
