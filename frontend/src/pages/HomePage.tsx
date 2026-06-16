import { ArrowRight, Database, FileText, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchBillingSummary, fetchKnowledgeBases, fetchKnowledgeSources, fetchTemplates } from "../api";
import { EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { formatDate, useAsyncData } from "../hooks";
import { useI18n } from "../i18n";
import { hasAnyValidatedProvider } from "../models";
import type { BillingSummary } from "../types";
import { useApiKeyStatus } from "../useApiKeyStatus";
import { deriveGenerateReadiness } from "../workflow";

const METRIC_ROTATE_MS = 2800;
const METRIC_TRANSITION_MS = 800;
const METRIC_RESUME_DELAY_MS = 400;
const METRIC_EASING = "cubic-bezier(0.16, 1, 0.3, 1)";
const joinClass = (...parts: Array<string | undefined>) => parts.filter(Boolean).join(" ");

function BillingSummaryStat({
  summary,
  loading,
  t,
  className,
}: {
  summary: BillingSummary | null;
  loading: boolean;
  t: (key: string, ...args: Array<string | number>) => string;
  className?: string;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  const metrics = useMemo(() => {
    if (loading || !summary) {
      return [
        { label: t("home.totalGenerations"), value: "..." },
        { label: t("home.totalTokens"), value: "..." },
        { label: t("home.totalCost"), value: "..." },
      ];
    }
    const totalTokens = Number(summary.input_tokens || 0) + Number(summary.output_tokens || 0);
    const numberFmt = new Intl.NumberFormat("zh-CN");
    const currencyFmt = new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: 4,
      maximumFractionDigits: 4,
    });
    return [
      {
        label: t("home.totalGenerations"),
        value: numberFmt.format(Number(summary.generation_count || 0)),
      },
      {
        label: t("home.totalTokens"),
        value: numberFmt.format(totalTokens),
      },
      {
        label: t("home.totalCost"),
        value: `¥ ${currencyFmt.format(Number(summary.cost_cny || 0))}`,
      },
    ];
  }, [loading, summary, t]);

  useEffect(() => {
    if (loading || !summary || paused) return;
    let rotateTimer = 0;
    const resumeTimer = window.setTimeout(() => {
      rotateTimer = window.setInterval(() => {
        setActiveIndex((idx) => (idx + 1) % metrics.length);
      }, METRIC_ROTATE_MS);
    }, METRIC_RESUME_DELAY_MS);
    return () => {
      window.clearTimeout(resumeTimer);
      if (rotateTimer) window.clearInterval(rotateTimer);
    };
  }, [loading, summary, paused, metrics.length]);

  useEffect(() => {
    setActiveIndex(0);
  }, [loading, summary]);

  return (
    <div
      className={joinClass("min-w-0 border border-white/10 bg-night-850/80 p-3.5 md:p-4", className)}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="relative h-[54px] overflow-hidden md:h-[62px]">
        {metrics.map((item, index) => {
          const prev = (activeIndex + metrics.length - 1) % metrics.length;
          let motionClass = "translate-y-6 opacity-0";
          if (index === activeIndex) motionClass = "translate-y-0 opacity-100";
          else if (index === prev) motionClass = "-translate-y-6 opacity-0";
          return (
            <div
              key={item.label}
              className={joinClass("absolute inset-0 flex flex-col will-change-transform", motionClass)}
              style={{
                transitionDuration: `${METRIC_TRANSITION_MS}ms`,
                transitionTimingFunction: METRIC_EASING,
                transitionProperty: "transform, opacity",
              }}
            >
              <p className="break-words text-[11px] font-medium uppercase tracking-[0.12em] text-slate-500 md:text-xs md:normal-case md:tracking-normal">
                {item.label}
              </p>
              <p className="mt-1.5 truncate font-display text-xl font-semibold leading-tight text-signal-amber md:mt-2 md:text-2xl">
                {item.value}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function HomePage() {
  const { t } = useI18n();
  const templates = useAsyncData(fetchTemplates, []);
  const kbs = useAsyncData(fetchKnowledgeBases, []);
  const billing = useAsyncData(fetchBillingSummary, []);
  const { status: apiKeyStatus, hasValidatedKey } = useApiKeyStatus();
  const [hasKnowledgeSources, setHasKnowledgeSources] = useState(false);

  const error = templates.error || kbs.error || billing.error;
  const templateItems = templates.data ?? [];
  const kbItems = kbs.data ?? [];
  const readiness = deriveGenerateReadiness({
    hasValidatedKey,
    hasKnowledgeBase: kbItems.length > 0,
    hasKnowledgeSources,
    hasTemplate: templateItems.length > 0,
  });

  useEffect(() => {
    const firstSlug = kbItems[0]?.slug;
    if (!firstSlug) {
      setHasKnowledgeSources(false);
      return;
    }
    fetchKnowledgeSources(firstSlug)
      .then((stats) => setHasKnowledgeSources((stats.source_count ?? 0) > 0))
      .catch(() => setHasKnowledgeSources(false));
  }, [kbItems]);

  return (
    <>
      <PageHeader
        eyebrow={t("home.eyebrow")}
        title={t("home.title")}
        description={t("home.description")}
        action={
          <Link
            to="/generate"
            className="inline-flex min-h-12 w-full items-center justify-center gap-2 border border-signal-cyan bg-signal-cyan px-5 text-sm font-bold text-night-950 shadow-glow transition hover:bg-white sm:min-h-11 sm:w-auto sm:font-semibold"
          >
            {t("home.start")}
            <ArrowRight size={17} />
          </Link>
        }
      />
      <ErrorBanner message={error} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4">
        <Stat label={t("home.templateCount")} value={templates.loading ? "..." : templateItems.length} />
        <Stat label={t("home.knowledgeCount")} value={kbs.loading ? "..." : kbItems.length} tone="lime" />
        <BillingSummaryStat
          className="col-span-2 md:col-span-1"
          summary={billing.data}
          loading={billing.loading}
          t={t}
        />
      </div>

      <div className="mt-5 grid gap-5 md:mt-6 md:gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel>
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <p className="font-display text-xl font-semibold text-white md:text-2xl">{t("home.setupChecklist")}</p>
              <p className="mt-1 text-sm text-slate-400">{t("home.setupChecklistBody")}</p>
            </div>
            <span className={`border px-2 py-1 text-xs font-semibold ${readiness.ready ? "border-signal-lime/40 bg-signal-lime/10 text-signal-lime" : "border-signal-amber/40 bg-signal-amber/10 text-amber-100"}`}>
              {readiness.ready ? t("home.ready") : t("home.notReady")}
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Link to="/settings" className="border border-white/10 bg-night-950/35 p-4 text-sm text-slate-300 hover:border-signal-cyan/40">
              <p className="font-semibold text-white">1. {t("home.stepKey")}</p>
              <p className="mt-1">{hasAnyValidatedProvider(apiKeyStatus) ? t("home.stepDone") : t("home.stepPending")}</p>
            </Link>
            <Link to="/knowledge" className="border border-white/10 bg-night-950/35 p-4 text-sm text-slate-300 hover:border-signal-lime/40">
              <p className="font-semibold text-white">2. {t("home.stepKnowledge")}</p>
              <p className="mt-1">{hasKnowledgeSources ? t("home.stepDone") : t("home.stepPending")}</p>
            </Link>
            <Link to="/template" className="border border-white/10 bg-night-950/35 p-4 text-sm text-slate-300 hover:border-signal-cyan/40">
              <p className="font-semibold text-white">3. {t("home.stepTemplate")}</p>
              <p className="mt-1">{templateItems.length > 0 ? t("home.stepDone") : t("home.stepPending")}</p>
            </Link>
            <Link to="/generate" className="border border-white/10 bg-night-950/35 p-4 text-sm text-slate-300 hover:border-signal-lime/40">
              <p className="font-semibold text-white">4. {t("home.stepGenerate")}</p>
              <p className="mt-1">{readiness.ready ? t("home.readyToGenerate") : t("home.finishSetupFirst")}</p>
            </Link>
          </div>
        </Panel>

        <Panel>
          <div className="mb-3 flex items-start justify-between gap-4 md:mb-4">
            <div className="min-w-0">
              <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("home.uploadedTemplates")}</p>
              <p className="mt-0.5 text-xs text-slate-500 md:text-sm">{t("home.templateSource")}</p>
            </div>
            <FileText className="shrink-0 text-signal-cyan" size={22} />
          </div>
          {templateItems.length === 0 ? (
            <EmptyState title={t("home.noTemplates")} body={t("home.noTemplatesBody")} />
          ) : (
            <div className="divide-y divide-white/10 border border-white/10 bg-night-950/35">
              {templateItems.slice(0, 8).map((item) => (
                <div key={item.name} className="flex items-center justify-between gap-3 px-3.5 py-3 md:p-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{item.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{formatDate(item.mtime)}</p>
                  </div>
                  <span className="shrink-0 border border-signal-cyan/30 bg-signal-cyan/10 px-2 py-1 text-[11px] font-semibold text-signal-cyan">
                    DOCX
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel>
          <div className="mb-3 flex items-start justify-between gap-4 md:mb-4">
            <div className="min-w-0">
              <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("home.knowledgeList")}</p>
              <p className="mt-0.5 text-xs text-slate-500 md:text-sm">{t("home.knowledgeBody")}</p>
            </div>
            <Database className="shrink-0 text-signal-lime" size={22} />
          </div>
          {kbItems.length === 0 ? (
            <EmptyState title={t("home.noKnowledge")} body={t("home.noKnowledgeBody")} />
          ) : (
            <div className="grid gap-2.5 md:gap-3">
              {kbItems.map((kb) => (
                <Link
                  key={kb.slug}
                  to="/knowledge"
                  className="group border border-white/10 bg-night-850/70 px-3.5 py-3 transition hover:border-signal-lime/40 hover:bg-night-800/70 md:p-4"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">
                        {kb.label || kb.name || kb.slug}
                      </p>
                      <p className="mt-1 truncate text-xs text-slate-500">{kb.slug}</p>
                    </div>
                    <RefreshCcw
                      className="text-slate-600 transition group-hover:text-signal-lime"
                      size={17}
                    />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
