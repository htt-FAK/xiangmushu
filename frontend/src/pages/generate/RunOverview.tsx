import { ChevronDown } from "lucide-react";
import { useState } from "react";
import {
  CheckCircle2,
  Database,
  Download,
  FileCheck2,
  FileSearch,
  FileText,
  Gauge,
  Loader2,
  PenTool,
  Search,
  ShieldCheck,
} from "lucide-react";
import { handleDownload } from "../../api";
import { Panel, Stat } from "../../components/ui";
import { useI18n } from "../../i18n";
import type { GenerationBilling, PostFillChecks } from "../../types";
import { clsx } from "../../utils";
import { SectionTitle, StepIndicator } from "./ui";
import type { GenerateStep, OutputBlock } from "./useGenerationSession";

function formatCny(value?: number | null) {
  if (typeof value !== "number") return "-";
  return `¥${value.toFixed(4)}`;
}

function DownloadButton({
  path,
  label,
  variant,
  size = 15,
  onError,
}: {
  path: string;
  label: string;
  variant: "primary" | "ghost";
  size?: number;
  onError: () => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const Icon = variant === "primary" ? Download : FileText;
  const base =
    variant === "primary"
      ? "border border-signal-lime bg-signal-lime text-night-950 hover:bg-signal-lime/90"
      : "border border-white/10 bg-white/[0.055] text-slate-100 hover:bg-white/10";
  return (
    <button
      type="button"
      disabled={downloading}
      className={clsx(
        "inline-flex min-h-10 items-center justify-center gap-2 px-3 text-xs font-bold transition disabled:opacity-60",
        base,
      )}
      onClick={async () => {
        setDownloading(true);
        try {
          await handleDownload(path);
        } catch {
          onError();
        } finally {
          setDownloading(false);
        }
      }}
    >
      {downloading ? <Loader2 className="animate-spin" size={size} /> : <Icon size={size} />}
      {label}
    </button>
  );
}

export function RunOverview({
  running,
  regeneratingIndex,
  busy,
  currentStep,
  currentTask,
  progress,
  percent,
  visualScore,
  visualTarget,
  runBilling,
  downloadPath,
  reportPath,
  reportSummary,
  postFillChecks,
  outputs,
  qualityMode,
  onDownloadError,
  compact = false,
}: {
  running: boolean;
  regeneratingIndex: number | null;
  busy: boolean;
  currentStep: GenerateStep;
  currentTask: string;
  progress: { done: number; total: number };
  percent: number;
  visualScore: number | null;
  visualTarget: number;
  runBilling: GenerationBilling | null;
  downloadPath: string;
  reportPath: string;
  reportSummary: string;
  postFillChecks: PostFillChecks | null;
  outputs: OutputBlock[];
  qualityMode: "balanced" | "quality" | "speed";
  onDownloadError: () => void;
  /** Mobile running layout: tighter stats, collapse secondary panels. */
  compact?: boolean;
}) {
  const { t } = useI18n();

  const hasAuditIssues = outputs.some((block) => (block.auditIssues?.length ?? 0) > 0);
  const checkHighlights = !postFillChecks
    ? []
    : [
        ...(postFillChecks.leftover_placeholders ?? []).slice(0, 3).map((item) => `${t("generate.leftover")}${item}`),
        ...(postFillChecks.missing_chapters ?? []).slice(0, 3).map((item) => `${t("generate.missing")}${item}`),
        ...(postFillChecks.protected_issues ?? []).slice(0, 3),
      ];

  return (
    <>
      <Panel className="min-w-0">
        {running && (
          <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5 max-sm:flex max-sm:overflow-x-auto max-sm:snap-x max-sm:pb-1">
            <StepIndicator className="max-sm:min-w-[160px] max-sm:shrink-0 max-sm:snap-start" currentStep={currentStep} step="retrieval" label={t("generate.stepRetrieval")} icon={<Database size={16} />} />
            <StepIndicator className="max-sm:min-w-[160px] max-sm:shrink-0 max-sm:snap-start" currentStep={currentStep} step="analysis" label={t("generate.stepAnalysis")} icon={<FileSearch size={16} />} />
            <StepIndicator className="max-sm:min-w-[160px] max-sm:shrink-0 max-sm:snap-start" currentStep={currentStep} step="generation" label={t("generate.stepGeneration")} icon={<PenTool size={16} />} />
            <StepIndicator className="max-sm:min-w-[160px] max-sm:shrink-0 max-sm:snap-start" currentStep={currentStep} step="audit" label={t("generate.stepAudit")} icon={<ShieldCheck size={16} />} />
            <StepIndicator className="max-sm:min-w-[160px] max-sm:shrink-0 max-sm:snap-start" currentStep={currentStep} step="done" label={t("generate.stepDone")} icon={<CheckCircle2 size={16} />} />
          </div>
        )}

        <SectionTitle
          icon={<Gauge size={20} />}
          title={t("generate.runOverview")}
          hint={compact ? undefined : t("generate.runOverviewHint")}
          action={
            <span
              className={clsx(
                "shrink-0 border px-2.5 py-1 text-xs font-semibold",
                busy ? "border-signal-lime/40 bg-signal-lime/10 text-signal-lime" : "border-white/10 bg-white/[0.025] text-slate-500",
              )}
            >
              {running ? t("generate.running") : regeneratingIndex !== null ? t("generate.regenerating") : t("generate.idle")}
            </span>
          }
        />

        <div
          className={clsx(
            "grid gap-2",
            compact ? "grid-cols-3" : "grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5",
          )}
        >
          <Stat label={t("generate.progress")} value={`${percent}%`} />
          <Stat label={t("generate.doneTasks")} value={`${progress.done}/${progress.total || "-"}`} tone="lime" />
          <Stat
            className={compact ? undefined : "col-span-2 md:col-span-1"}
            label={t("generate.currentTask")}
            value={currentTask || "-"}
            tone="amber"
          />
          {!compact && (
            <>
              <Stat
                label={t("generate.visualScore")}
                value={visualScore === null ? "-" : visualScore}
                tone={visualScore !== null && visualScore < visualTarget ? "rose" : "cyan"}
              />
              <Stat label={t("generate.runCost")} value={formatCny(runBilling?.cost_cny)} tone="lime" />
            </>
          )}
        </div>

        {runBilling && !compact ? (
          <p className="mt-3 break-words border border-white/10 bg-night-950 px-3 py-2 text-xs leading-5 text-slate-400">
            {t("generate.tokenSummaryLine")
              .replace("{0}", String(runBilling.input_tokens ?? 0))
              .replace("{1}", String(runBilling.output_tokens ?? 0))}
          </p>
        ) : null}

        {(downloadPath || reportPath) && !compact && (
          <div className="mt-3 flex flex-wrap gap-2">
            {downloadPath && (
              <DownloadButton path={downloadPath} label={t("generate.downloadDoc")} variant="primary" onError={onDownloadError} />
            )}
            {reportPath && (
              <DownloadButton path={reportPath} label={t("generate.downloadReport")} variant="ghost" onError={onDownloadError} />
            )}
          </div>
        )}

        <div className={clsx("border border-white/10 bg-night-950 p-1", compact ? "mt-3" : "mt-5")}>
          <div className="h-2 bg-[linear-gradient(90deg,#36f2e6,#b8ff5e)] transition-all duration-500" style={{ width: `${percent}%` }} />
        </div>
      </Panel>

      {(downloadPath || reportPath || reportSummary || postFillChecks) &&
        (compact ? (
          <details className="group min-w-0 border border-white/10 bg-white/[0.045] shadow-panel backdrop-blur">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm">
              <span className="flex min-w-0 items-center gap-2 font-semibold text-white">
                <FileCheck2 size={16} className="shrink-0 text-signal-cyan" />
                {t("generate.acceptance")}
              </span>
              <ChevronDown size={16} className="shrink-0 text-slate-400 transition group-open:rotate-180" />
            </summary>
            <div className="space-y-4 border-t border-white/10 p-4">
              {(downloadPath || reportPath) && (
                <div className="flex flex-wrap gap-3">
                  {downloadPath && (
                    <DownloadButton path={downloadPath} label={t("generate.downloadDoc")} variant="primary" size={16} onError={onDownloadError} />
                  )}
                  {reportPath && (
                    <DownloadButton path={reportPath} label={t("generate.downloadReport")} variant="ghost" size={16} onError={onDownloadError} />
                  )}
                </div>
              )}
              {reportSummary && <p className="break-words text-sm leading-7 text-slate-300">{reportSummary}</p>}
              {postFillChecks && (
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="min-w-0 border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{t("generate.checkResult")}</p>
                    <p className="mt-2 text-white">{postFillChecks.ok ? t("generate.pass") : t("generate.review")}</p>
                    <p className="mt-2 break-words text-xs text-slate-400">
                      {t("generate.templateWordsSummary")
                        .replace("{0}", String(postFillChecks.template_words ?? "-"))
                        .replace("{1}", String(postFillChecks.output_words ?? "-"))}
                    </p>
                  </div>
                  <div className="min-w-0 border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{t("generate.structure")}</p>
                    <p className="mt-2 break-words text-white">
                      {t("generate.tableCountSummary")
                        .replace("{0}", String(postFillChecks.template_tables ?? "-"))
                        .replace("{1}", String(postFillChecks.output_tables ?? "-"))}
                    </p>
                    <p className="mt-2 break-words text-xs text-slate-400">
                      {t("generate.coverCheck")} {postFillChecks.cover_modified ? t("generate.review") : t("generate.pass")}, {t("generate.ratingTableCheck")}{" "}
                      {postFillChecks.rating_table_modified ? t("generate.review") : t("generate.pass")}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </details>
        ) : (
        <Panel className="min-w-0">
          <SectionTitle icon={<FileCheck2 size={20} />} title={t("generate.acceptance")} hint={t("generate.acceptanceHint")} />

          {(downloadPath || reportPath) && (
            <div className="mb-5 flex flex-wrap gap-3">
              {downloadPath && (
                <DownloadButton path={downloadPath} label={t("generate.downloadDoc")} variant="primary" size={16} onError={onDownloadError} />
              )}
              {reportPath && (
                <DownloadButton path={reportPath} label={t("generate.downloadReport")} variant="ghost" size={16} onError={onDownloadError} />
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
                  {t("generate.templateWordsSummary")
                    .replace("{0}", String(postFillChecks.template_words ?? "-"))
                    .replace("{1}", String(postFillChecks.output_words ?? "-"))}
                </p>
              </div>
              <div className="min-w-0 border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{t("generate.structure")}</p>
                <p className="mt-2 break-words text-white">
                  {t("generate.tableCountSummary")
                    .replace("{0}", String(postFillChecks.template_tables ?? "-"))
                    .replace("{1}", String(postFillChecks.output_tables ?? "-"))}
                </p>
                <p className="mt-2 break-words text-xs text-slate-400">
                  {t("generate.coverCheck")} {postFillChecks.cover_modified ? t("generate.review") : t("generate.pass")}, {t("generate.ratingTableCheck")}{" "}
                  {postFillChecks.rating_table_modified ? t("generate.review") : t("generate.pass")}
                </p>
              </div>
            </div>
          )}
        </Panel>
        ))}

      {(hasAuditIssues || checkHighlights.length > 0 || visualScore !== null) &&
        (compact ? (
          <details className="group min-w-0 border border-white/10 bg-white/[0.045] shadow-panel backdrop-blur">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm">
              <span className="flex min-w-0 items-center gap-2 font-semibold text-white">
                <Search size={16} className="shrink-0 text-signal-cyan" />
                {t("generate.auditPanelTitle")}
              </span>
              <ChevronDown size={16} className="shrink-0 text-slate-400 transition group-open:rotate-180" />
            </summary>
            <div className="space-y-3 border-t border-white/10 p-4">
              <div className="grid gap-3 grid-cols-3">
                <div className="border border-white/10 bg-night-950 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.visualTarget")}</p>
                  <p className="mt-2 font-display text-xl font-semibold text-signal-cyan">{visualTarget}</p>
                </div>
                <div className="border border-white/10 bg-night-950 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.auditIssues")}</p>
                  <p
                    className={clsx(
                      "mt-2 font-display text-xl font-semibold",
                      hasAuditIssues || checkHighlights.length ? "text-signal-amber" : "text-signal-lime",
                    )}
                  >
                    {outputs.reduce((sum, block) => sum + (block.auditIssues?.length ?? 0), 0) + checkHighlights.length}
                  </p>
                </div>
                <div className="border border-white/10 bg-night-950 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.qualityMode")}</p>
                  <p className="mt-2 font-display text-sm font-semibold text-signal-lime">
                    {qualityMode === "quality" ? t("generate.modeQuality") : qualityMode === "speed" ? t("generate.modeSpeed") : t("generate.modeBalanced")}
                  </p>
                </div>
              </div>
              {checkHighlights.length > 0 && (
                <div className="space-y-2">
                  {checkHighlights.map((item) => (
                    <div key={item} className="break-words border border-signal-amber/30 bg-signal-amber/10 px-3 py-2 text-sm text-amber-100">
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </details>
        ) : (
        <Panel className="min-w-0">
          <SectionTitle icon={<Search size={20} />} title={t("generate.auditPanelTitle")} hint={t("generate.auditPanelHint")} />
          <div className="grid gap-3 md:grid-cols-3">
            <div className="border border-white/10 bg-night-950 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.visualTarget")}</p>
              <p className="mt-2 font-display text-2xl font-semibold text-signal-cyan">{visualTarget}</p>
            </div>
            <div className="border border-white/10 bg-night-950 p-3">
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
            <div className="border border-white/10 bg-night-950 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{t("generate.qualityMode")}</p>
              <p className="mt-2 font-display text-lg font-semibold text-signal-lime">
                {qualityMode === "quality" ? t("generate.modeQuality") : qualityMode === "speed" ? t("generate.modeSpeed") : t("generate.modeBalanced")}
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
        ))}
    </>
  );
}
