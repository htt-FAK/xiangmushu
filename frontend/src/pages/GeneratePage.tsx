import { AlertTriangle, Loader2, Play, ShieldCheck, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchKnowledgeBases,
  fetchKnowledgeSources,
  fetchTemplates,
  fetchUserPreferences,
} from "../api";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import type { GenerateParams, KnowledgeBase, KnowledgeSourceStats, TemplateItem } from "../types";
import { useApiKeyStatus } from "../useApiKeyStatus";
import { deriveGenerateReadiness, useWorkflow } from "../workflow";
import { ConfirmModal, QuotaSwitchModal } from "./generate/modals";
import { OutputList } from "./generate/OutputList";
import { RunOverview } from "./generate/RunOverview";
import { SetupPanel, type RecommendedConfig } from "./generate/SetupPanel";
import { NoticeBanner } from "./generate/ui";
import { useGenerationSession } from "./generate/useGenerationSession";

type RailItem = { value: string; title: string; meta?: string };

const VISUAL_TARGET = 80;

function paramsByQuality(qualityMode: "balanced" | "quality" | "speed") {
  switch (qualityMode) {
    case "quality":
      return { topK: 6, maxDistance: 1.0, wordLimit: 500 };
    case "speed":
      return { topK: 2, maxDistance: 1.5, wordLimit: 200 };
    default:
      return { topK: 4, maxDistance: 1.25, wordLimit: 300 };
  }
}

export default function GeneratePage() {
  const { t } = useI18n();
  const { state: workflowState, setGenerateSelections, setGenerateSession } = useWorkflow();

  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [template, setTemplate] = useState(workflowState.generate.template);
  const [slug, setSlug] = useState(workflowState.generate.slug);
  const [generationBrief, setGenerationBrief] = useState(workflowState.generate.generationBrief);
  const [qualityMode, setQualityMode] = useState<"balanced" | "quality" | "speed">(workflowState.generate.qualityMode);
  const [enableWeb, setEnableWeb] = useState(false);
  const useStream = true;
  const [enableAudit, setEnableAudit] = useState(false);
  const [enableVisualAudit, setEnableVisualAudit] = useState(true);
  const [selectedKnowledgeStats, setSelectedKnowledgeStats] = useState<KnowledgeSourceStats | null>(workflowState.knowledge.stats);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [preferenceWarnings, setPreferenceWarnings] = useState<Record<string, string>>({});

  const userOverrodeSwitchesRef = useRef(false);

  const taskName = useMemo(() => (index: number) => `${t("generate.taskFallback")} ${index + 1}`, [t]);

  const buildGenerateParams = useMemo(
    () => (): GenerateParams => {
      const params = paramsByQuality(qualityMode);
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
    },
    [enableAudit, enableVisualAudit, enableWeb, generationBrief, qualityMode, slug, template],
  );

  const session = useGenerationSession({
    buildParams: buildGenerateParams,
    taskName,
    donePassLabel: t("generate.pass"),
    streamDisconnectedLabel: t("generate.streamDisconnected"),
    activeSessionLabel: t("generate.activeSessionExists"),
    onSnapshot: setGenerateSession,
  });
  const { busy, running } = session;

  const refreshPreferences = useCallback(() => {
    fetchUserPreferences()
      .then((prefs) => {
        session.setModelChoices(prefs.model_choices ?? {});
        setPreferenceWarnings(prefs.warnings ?? {});
      })
      .catch(() => undefined);
  }, [session]);

  const recommendedConfig = useMemo<RecommendedConfig | null>(() => {
    if (!template || !slug) return null;
    const kb = kbs.find((item) => item.slug === slug) as (KnowledgeBase & { document_count?: number }) | undefined;
    const isComplex = /项目|方案|报告|论文|project|proposal|report|paper/i.test(template);
    const hasRichKB = (kb?.document_count ?? 0) > 10;
    return {
      qualityMode: (isComplex ? "quality" : "balanced") as "balanced" | "quality",
      enableWeb: !hasRichKB,
      enableAudit: isComplex,
    };
  }, [template, slug, kbs]);

  const knowledgeItems = useMemo<RailItem[]>(
    () => kbs.map((kb) => ({ value: kb.slug, title: kb.label || kb.name || kb.slug, meta: kb.slug })),
    [kbs],
  );

  const templateItems = useMemo<RailItem[]>(
    () => templates.map((item) => ({ value: item.name, title: item.name, meta: "DOCX" })),
    [templates],
  );

  const selectedProviderModels = useMemo(() => {
    const choices = session.modelChoices ?? {};
    return [
      choices.main_writer,
      choices.fast_writer,
      enableWeb ? choices.web_search : null,
      enableAudit ? choices.audit_text : null,
    ];
  }, [enableAudit, enableWeb, session.modelChoices]);

  const { hasValidatedKey } = useApiKeyStatus(selectedProviderModels);

  const readiness = useMemo(
    () =>
      deriveGenerateReadiness({
        hasValidatedKey,
        hasKnowledgeBase: kbs.length > 0,
        hasKnowledgeSources: (selectedKnowledgeStats?.source_count ?? 0) > 0,
        hasTemplate: templates.length > 0,
      }),
    [hasValidatedKey, kbs.length, selectedKnowledgeStats?.source_count, templates.length],
  );

  useEffect(() => {
    if (!hasValidatedKey) return;
    if (session.notice?.message === t("generate.providerUnavailableHint")) {
      session.dismissNotice();
    }
    refreshPreferences();
  }, [hasValidatedKey, refreshPreferences, session, t]);

  // Initial load: templates, knowledge bases, user preferences, and active session recovery.
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
      session.reportFailedLoads(failures);
    });

    refreshPreferences();

    session.recoverActiveSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refreshPreferences();
    };
    window.addEventListener("focus", refreshPreferences);
    window.addEventListener("xiangmushu:apikey-status-changed", refreshPreferences);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.removeEventListener("focus", refreshPreferences);
      window.removeEventListener("xiangmushu:apikey-status-changed", refreshPreferences);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [refreshPreferences]);

  useEffect(() => {
    setGenerateSelections({ slug, template, generationBrief, qualityMode });
  }, [generationBrief, qualityMode, setGenerateSelections, slug, template]);

  useEffect(() => {
    if (!slug) {
      setSelectedKnowledgeStats(null);
      return;
    }
    fetchKnowledgeSources(slug)
      .then(setSelectedKnowledgeStats)
      .catch(() => undefined);
  }, [slug]);

  useEffect(() => {
    if (!recommendedConfig || busy) return;
    setQualityMode((current) => (current === recommendedConfig.qualityMode ? current : recommendedConfig.qualityMode));
    if (!userOverrodeSwitchesRef.current) {
      setEnableWeb((current) => (current === recommendedConfig.enableWeb ? current : recommendedConfig.enableWeb));
      setEnableAudit((current) => (current === recommendedConfig.enableAudit ? current : recommendedConfig.enableAudit));
      setEnableVisualAudit((current) => (current ? current : true));
    }
  }, [busy, recommendedConfig]);

  function requestStart() {
    if (!template || !slug || busy || !readiness.ready) return;
    setConfirmOpen(true);
  }

  function confirmStart() {
    setConfirmOpen(false);
    if (!template || !slug) return;
    void session.start();
  }

  const markOverride = (setter: (value: boolean) => void) => (value: boolean) => {
    userOverrodeSwitchesRef.current = true;
    setter(value);
  };

  const providerWarning = useMemo(() => {
    const keys = ["main_writer", "fast_writer", "web_search", "template_planner", "audit_text"];
    for (const key of keys) {
      const text = preferenceWarnings[key];
      if (text) return text;
    }
    return "";
  }, [preferenceWarnings]);

  return (
    <>
      <header className="mb-4 grid gap-3 border-b border-white/10 pb-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
        <div className="min-w-0">
          <p className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-signal-cyan">
            {t("generate.eyebrow")}
          </p>
          <h1 className="mt-1 break-words font-display text-2xl font-semibold leading-tight text-white md:text-3xl">
            {t("generate.title")}
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{t("generate.description")}</p>
        </div>
        <div className="grid grid-cols-[1fr_auto] gap-2 xl:w-[360px]">
          <Button
            className="min-h-12 w-full text-sm font-bold shadow-glow"
            onClick={requestStart}
            disabled={!template || !slug || busy || !readiness.ready}
          >
            {running ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
            {running ? t("generate.running") : t("generate.start")}
          </Button>
          <Button
            className="min-h-12 w-12 px-0 font-bold"
            variant="ghost"
            onClick={session.stop}
            disabled={!busy}
            aria-label={t("generate.stop")}
          >
            <Square size={17} />
          </Button>
        </div>
      </header>

      <NoticeBanner notice={session.notice} retryLabel={t("generate.retry")} onDismiss={session.dismissNotice} />
      {providerWarning ? (
        <div className="mb-4 flex items-start gap-2 border border-signal-amber/40 bg-signal-amber/10 px-4 py-3 text-sm text-amber-100">
          <AlertTriangle className="mt-0.5 shrink-0 text-signal-amber" size={16} />
          <p>{providerWarning}</p>
        </div>
      ) : null}

      {!readiness.ready && (
        <div className="mb-6 flex flex-col gap-4 border border-signal-amber/40 bg-signal-amber/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between md:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <ShieldCheck className="shrink-0 text-signal-amber" size={20} />
            <p className="min-w-0 break-words text-sm font-semibold text-amber-100">
              {readiness.reason === "missing_key"
                ? t("generate.missingKeyHint")
                : readiness.reason === "missing_knowledge"
                  ? t("generate.missingKnowledgeHint")
                  : t("generate.missingTemplateHint")}
            </p>
          </div>
          <Link
            to={readiness.reason === "missing_key" ? "/settings" : readiness.reason === "missing_knowledge" ? "/knowledge" : "/template"}
            className="inline-flex min-h-11 items-center justify-center border border-signal-amber bg-signal-amber px-4 text-xs font-bold text-night-950 transition hover:bg-white sm:w-auto"
          >
            {readiness.reason === "missing_key"
              ? t("generate.goSettings")
              : readiness.reason === "missing_knowledge"
                ? t("generate.goKnowledge")
                : t("generate.goTemplate")}
          </Link>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-5">
          <SetupPanel
            knowledgeItems={knowledgeItems}
            templateItems={templateItems}
            slug={slug}
            template={template}
            qualityMode={qualityMode}
            generationBrief={generationBrief}
            enableWeb={enableWeb}
            enableAudit={enableAudit}
            enableVisualAudit={enableVisualAudit}
            recommendedConfig={recommendedConfig}
            busy={busy}
            onSlugChange={setSlug}
            onTemplateChange={setTemplate}
            onQualityModeChange={setQualityMode}
            onGenerationBriefChange={setGenerationBrief}
            onToggleWeb={markOverride(setEnableWeb)}
            onToggleAudit={markOverride(setEnableAudit)}
            onToggleVisualAudit={markOverride(setEnableVisualAudit)}
          />
        </div>

        <div className="min-w-0 space-y-5">
          <RunOverview
            running={running}
            regeneratingIndex={session.regeneratingIndex}
            busy={busy}
            currentStep={session.currentStep}
            currentTask={session.currentTask}
            progress={session.progress}
            percent={session.percent}
            visualScore={session.visualScore}
            visualTarget={VISUAL_TARGET}
            runBilling={session.runBilling}
            downloadPath={session.downloadPath}
            reportPath={session.reportPath}
            reportSummary={session.reportSummary}
            postFillChecks={session.postFillChecks}
            outputs={session.outputs}
            qualityMode={qualityMode}
            onDownloadError={() => session.setNotice({ kind: "plain", message: t("generate.downloadFailed") })}
          />

          <OutputList
            outputs={session.outputs}
            taskName={taskName}
            regeneratingIndex={session.regeneratingIndex}
            running={running}
            currentTask={session.currentTask}
            busy={busy}
            progress={session.progress}
            onRegenerate={session.regenerateSection}
            traceOpen={traceOpen}
            onOpenTrace={() => setTraceOpen(true)}
            onCloseTrace={() => setTraceOpen(false)}
          />
        </div>
      </div>

      {confirmOpen && (
        <ConfirmModal
          title={t("generate.confirmTitle")}
          body={t("generate.confirmBody")}
          cancelLabel={t("generate.cancel")}
          confirmLabel={t("generate.confirmStart")}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={confirmStart}
        />
      )}

      {session.quotaModalOpen && session.quotaAlertData && (
        <QuotaSwitchModal
          data={session.quotaAlertData}
          title={t("generate.quotaDialogTitle")}
          cancelLabel={t("generate.cancel")}
          saving={session.savingQuotaSwitch}
          onSwitch={(model) => void session.switchQuotaModel(model)}
          onCancel={() => {
            session.closeQuotaModal();
            session.stop();
          }}
        />
      )}
    </>
  );
}
