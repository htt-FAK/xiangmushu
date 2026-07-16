import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchCustomModels,
  fetchModelOptions,
  startGenerateSession,
  streamGenerate,
  updateUserPreferences,
} from "../../api";
import { useAuth } from "../../auth";
import { useBackgroundSessions } from "../../backgroundSessions";
import type { OutputBlockData } from "../../components/OutputBlock";
import { useCustomModelsCache } from "../../useCustomModels";
import type {
  AuditFallbackEvent,
  CustomModel,
  GenerateEvent,
  GenerateParams,
  GenerationBilling,
  GenerationSessionSnapshot,
  ModelOptionsMap,
  PostFillChecks,
  UserPreferences,
} from "../../types";
import { useWorkflow } from "../../workflow";

export type OutputBlock = OutputBlockData;
export type GenerateStep = "idle" | "retrieval" | "analysis" | "generation" | "audit" | "done";

type QuotaAlertPayload = Extract<GenerateEvent, { type: "quota_alert" }>;
export type QuotaAlertData = Pick<QuotaAlertPayload, "module" | "current_model" | "available_models" | "message">;

/**
 * Strongly-typed user-facing notice, replacing the previous pattern of storing
 * errors as JSON strings and re-parsing them in render.
 */
export type GenerationNotice =
  | null
  | { kind: "plain"; message: string }
  | { kind: "typed"; level: "warning" | "error" | "info"; message: string; retryable: boolean };

export type GenerationSessionApi = ReturnType<typeof useGenerationSession>;

function plain(message: string): GenerationNotice {
  return message ? { kind: "plain", message } : null;
}

function typed(level: "warning" | "error" | "info", message: string, retryable = true): GenerationNotice {
  return { kind: "typed", level, message, retryable };
}

/**
 * Owns the document-generation run: session lifecycle (start/subscribe/resume/
 * terminate), the SSE event reducer, per-chapter outputs, billing, and a typed
 * notice for user-facing messages. UI components consume the returned state.
 */
export function useGenerationSession(options: {
  buildParams: () => GenerateParams;
  taskName: (index: number) => string;
  donePassLabel: string;
  streamDisconnectedLabel: string;
  activeSessionLabel: string;
  onSnapshot: (session: GenerationSessionSnapshot) => void;
}) {
  const { buildParams, taskName, donePassLabel, streamDisconnectedLabel, activeSessionLabel, onSnapshot } = options;

  const { state: workflowState } = useWorkflow();
  const { ensureGenerationStream, abortGenerationStream } = useBackgroundSessions();

  const [currentStep, setCurrentStep] = useState<GenerateStep>("idle");
  const [running, setRunning] = useState(false);
  const [regeneratingIndex, setRegeneratingIndex] = useState<number | null>(null);
  const [notice, setNotice] = useState<GenerationNotice>(null);
  const [currentTask, setCurrentTask] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [outputs, setOutputs] = useState<OutputBlock[]>([]);
  const [downloadPath, setDownloadPath] = useState("");
  const [reportPath, setReportPath] = useState("");
  const [reportSummary, setReportSummary] = useState("");
  const [postFillChecks, setPostFillChecks] = useState<PostFillChecks | null>(null);
  const [visualScore, setVisualScore] = useState<number | null>(null);
  const [runBilling, setRunBilling] = useState<GenerationBilling | null>(null);
  const [auditFallbackEvents, setAuditFallbackEvents] = useState<AuditFallbackEvent[]>([]);
  const [modelChoices, setModelChoices] = useState<UserPreferences["model_choices"]>({});
  const [quotaAlertData, setQuotaAlertData] = useState<QuotaAlertData | null>(null);
  const [quotaModalOpen, setQuotaModalOpen] = useState(false);
  const [savingQuotaSwitch, setSavingQuotaSwitch] = useState(false);
  const [customModels, setCustomModels] = useState<CustomModel[]>([]);
  const [modelOptions, setModelOptions] = useState<ModelOptionsMap | null>(null);

  const { userEmail } = useAuth();
  const { getModels, setModels } = useCustomModelsCache(userEmail || null);

  const abortRef = useRef<AbortController | null>(null);
  const sectionAbortRef = useRef<AbortController | null>(null);
  const activeSessionIdRef = useRef<string>("");

  const busy = running || regeneratingIndex !== null;

  const createOutputShell = useCallback(
    (index: number, chapter?: string): OutputBlock => ({
      chapter: chapter || taskName(index),
      text: "",
      evidenceRefs: [],
      auditIssues: [],
    }),
    [taskName],
  );

  const updateOutput = useCallback(
    (index: number, patch: Partial<OutputBlock>) => {
      setOutputs((prev) => {
        const next = [...prev];
        const existing = next[index] ?? createOutputShell(index);
        next[index] = { ...existing, ...patch };
        return next;
      });
    },
    [createOutputShell],
  );

  const appendOutputChunk = useCallback(
    (index: number, text: string, chapter?: string) => {
      setOutputs((prev) => {
        const next = [...prev];
        const existing = next[index] ?? createOutputShell(index, chapter);
        next[index] = { ...existing, chapter: chapter || existing.chapter, text: `${existing.text}${text}` };
        return next;
      });
    },
    [createOutputShell],
  );

  const handleQuotaAlert = useCallback((event: QuotaAlertPayload) => {
    abortRef.current?.abort();
    sectionAbortRef.current?.abort();
    abortRef.current = null;
    sectionAbortRef.current = null;
    setQuotaAlertData({
      module: event.module,
      current_model: event.current_model,
      available_models: event.available_models,
      message: event.message,
    });
    setQuotaModalOpen(true);
    setRunning(false);
    setRegeneratingIndex(null);
    setNotice(null);
  }, []);

  const applyLocalFromSnapshot = useCallback((session: GenerationSessionSnapshot) => {
    activeSessionIdRef.current = session.session_id;
    setCurrentTask(session.currentTask || "");
    setProgress(session.progress ?? { done: 0, total: 0 });
    setOutputs((session.outputs as OutputBlock[]) ?? []);
    setDownloadPath(session.download || "");
    setReportPath(session.report_download || "");
    setReportSummary(session.report_summary || "");
    setPostFillChecks(session.post_fill_checks ?? null);
    setVisualScore(session.visual_score ?? null);
    setRunBilling(session.billing ?? null);
    setAuditFallbackEvents(session.audit_fallback_events ?? []);
    setCurrentStep(((session.currentStep as GenerateStep) || "idle") as GenerateStep);
    setRunning(session.status === "running");
    if (session.last_error?.message) {
      setNotice(typed("error", session.last_error.message, Boolean(session.last_error.retryable)));
    }
  }, []);

  const applySessionSnapshot = useCallback(
    (session: GenerationSessionSnapshot) => {
      applyLocalFromSnapshot(session);
      onSnapshot(session);
    },
    [applyLocalFromSnapshot, onSnapshot],
  );

  useEffect(() => {
    const session = workflowState.generate.session;
    if (!session) return;
    applyLocalFromSnapshot(session);
  }, [applyLocalFromSnapshot, workflowState.generate.session]);

  const handleEvent = useCallback(
    (event: GenerateEvent) => {
      if (event.type === "heartbeat") return;
      if (event.type === "quota_alert") {
        handleQuotaAlert(event);
        return;
      }
      if (event.type === "task") {
        setCurrentTask(event.chapter);
        setCurrentStep("generation");
        setProgress((prev) => ({ done: prev.done, total: event.total }));
        updateOutput(event.index, {
          chapter: event.chapter,
          text: "",
          model: undefined,
          tier: undefined,
          role: undefined,
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
          model: event.model,
          tier: event.tier,
          role: event.role,
          kbHits: event.kb_hits,
          evidenceRefs: event.evidence_refs ?? [],
        });
        return;
      }
      if (event.type === "chunk") {
        appendOutputChunk(event.index, event.text);
        return;
      }
      if (event.type === "audit") {
        if (event.is_model_audit !== false) {
          setCurrentStep("audit");
        }
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
      if (event.type === "audit_fallback") {
        setAuditFallbackEvents((prev) => [
          ...prev,
          {
            segment_index: event.segment_index ?? event.index ?? prev.length,
            custom_model_id: event.custom_model_id,
            fallback_model_id: event.fallback_model_id,
            error_kind: event.error_kind,
            error_detail: event.error_detail,
            occurred_at: event.occurred_at ?? new Date().toISOString(),
          },
        ]);
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
        if (event.audit_fallback_events?.length) {
          setAuditFallbackEvents(event.audit_fallback_events);
        }
        setCurrentTask(donePassLabel);
        setRunning(false);
        return;
      }
      if (event.type === "error") {
        const payload = typeof event.error === "string" ? { message: event.error, retryable: true } : event.error;
        setNotice(typed("error", payload.message, true));
        if (event.terminal) setRunning(false);
      }
    },
    [appendOutputChunk, donePassLabel, handleQuotaAlert, updateOutput],
  );

  const subscribeSession = useCallback(
    (sessionId: string, afterSeq = 0) => {
      setRunning(true);
      ensureGenerationStream(sessionId, afterSeq);
    },
    [ensureGenerationStream],
  );

  const start = useCallback(async () => {
    setQuotaModalOpen(false);
    setQuotaAlertData(null);
    setRunning(true);
    setNotice(null);
    setOutputs([]);
    setDownloadPath("");
    setReportPath("");
    setReportSummary("");
    setPostFillChecks(null);
    setVisualScore(null);
    setRunBilling(null);
    setAuditFallbackEvents([]);
    setCurrentTask("");
    setProgress({ done: 0, total: 0 });
    setCurrentStep("retrieval");

    try {
      const result = await startGenerateSession(buildParams());
      if (!result.ok || !result.session_id || !result.session) {
        if (result.session) {
          applySessionSnapshot(result.session);
        }
        setNotice(typed("warning", result.message || activeSessionLabel, true));
        setRunning(Boolean(result.session?.status === "running"));
        if (result.session_id && result.session?.status === "running") {
          void subscribeSession(result.session_id, result.session.last_seq);
        }
        return;
      }
      applySessionSnapshot(result.session);
      subscribeSession(result.session_id, result.session.last_seq);
    } catch (err) {
      setNotice(plain(err instanceof Error ? err.message : String(err)));
      setRunning(false);
    }
  }, [activeSessionLabel, applySessionSnapshot, buildParams, subscribeSession]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    sectionAbortRef.current?.abort();
    abortRef.current = null;
    sectionAbortRef.current = null;
    abortGenerationStream();
    setRegeneratingIndex(null);
    setRunning(false);
    setNotice(typed("info", streamDisconnectedLabel, true));
  }, [abortGenerationStream, streamDisconnectedLabel]);

  const switchQuotaModel = useCallback(
    async (model: string) => {
      if (!quotaAlertData?.module) {
        setNotice(typed("error", "Missing quota module.", true));
        return;
      }
      const nextChoices = { ...(modelChoices ?? {}), [quotaAlertData.module]: model };
      setSavingQuotaSwitch(true);
      try {
        const updated = await updateUserPreferences({ model_choices: nextChoices });
        setModelChoices(updated.model_choices ?? nextChoices);
        setQuotaModalOpen(false);
        setQuotaAlertData(null);
        await start();
      } catch (err) {
        setNotice(typed("error", err instanceof Error ? err.message : String(err), true));
      } finally {
        setSavingQuotaSwitch(false);
      }
    },
    [modelChoices, quotaAlertData, start],
  );

  const regenerateSection = useCallback(
    async (index: number) => {
      if (running || regeneratingIndex !== null) return;
      let previousBlock: OutputBlock | undefined;
      setOutputs((prev) => {
        previousBlock = prev[index];
        return prev;
      });
      if (!previousBlock) return;

      const controller = new AbortController();
      const chapters: Record<number, string> = {};
      let failed = false;

      sectionAbortRef.current = controller;
      setRegeneratingIndex(index);
      setNotice(null);

      try {
        await streamGenerate(
          buildParams(),
          (event) => {
            if (event.type === "heartbeat") return;
            if (event.type === "task") {
              chapters[event.index] = event.chapter;
              if (event.index !== index) return;
              updateOutput(index, {
                chapter: event.chapter,
                text: "",
                model: undefined,
                tier: undefined,
                role: undefined,
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
                chapter: chapters[event.index] || previousBlock?.chapter || taskName(index),
                model: event.model,
                tier: event.tier,
                role: event.role,
                kbHits: event.kb_hits,
                evidenceRefs: event.evidence_refs ?? [],
              });
              return;
            }
            if (event.type === "chunk" && event.index === index) {
              appendOutputChunk(index, event.text, chapters[event.index] || previousBlock?.chapter);
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
              return;
            }
            if (event.type === "quota_alert") {
              failed = true;
              handleQuotaAlert(event);
              controller.abort();
              return;
            }
            if (event.type === "error") {
              failed = true;
              setNotice(typed("error", typeof event.error === "string" ? event.error : event.error.message, true));
              controller.abort();
            }
          },
          controller.signal,
        );
      } catch (err) {
        failed = true;
        if (!controller.signal.aborted) {
          setNotice(plain(err instanceof Error ? err.message : String(err)));
        }
      } finally {
        if ((failed || controller.signal.aborted) && previousBlock) {
          const restore = previousBlock;
          setOutputs((prev) => {
            const next = [...prev];
            next[index] = restore;
            return next;
          });
        }
        sectionAbortRef.current = null;
        setRegeneratingIndex(null);
      }
    },
    [appendOutputChunk, buildParams, handleQuotaAlert, regeneratingIndex, running, taskName, updateOutput],
  );

  const recoverActiveSession = useCallback(() => {
    // Background fetch custom models with caching
    const cached = getModels();
    if (cached) setCustomModels(cached);
    fetchCustomModels().then((models) => {
      setCustomModels(models);
      setModels(models);
    }).catch(() => {});

    // Fetch model options for selectors
    fetchModelOptions().then(setModelOptions).catch(() => {});

    const session = workflowState.generate.session;
    if (session) {
      applyLocalFromSnapshot(session);
      if (session.status === "running") {
        ensureGenerationStream(session.session_id, session.last_seq);
      }
    }
  }, [applyLocalFromSnapshot, ensureGenerationStream, workflowState.generate.session]);

  const reportFailedLoads = useCallback((failures: string[]) => {
    if (failures.length > 0) {
      setNotice(typed("warning", failures.join("; "), true));
    }
  }, []);

  const dismissNotice = useCallback(() => setNotice(null), []);
  const closeQuotaModal = useCallback(() => {
    setQuotaModalOpen(false);
    setQuotaAlertData(null);
  }, []);

  const percent = useMemo(() => {
    if (!progress.total) return 0;
    return Math.round((progress.done / progress.total) * 100);
  }, [progress]);

  return {
    // state
    currentStep,
    running,
    regeneratingIndex,
    busy,
    notice,
    currentTask,
    progress,
    percent,
    outputs,
    downloadPath,
    reportPath,
    reportSummary,
    postFillChecks,
    visualScore,
    runBilling,
    auditFallbackEvents,
    modelChoices,
    customModels,
    modelOptions,
    quotaAlertData,
    quotaModalOpen,
    savingQuotaSwitch,
    // setters / actions
    setModelChoices,
    setModelOptions,
    setNotice,
    dismissNotice,
    start,
    stop,
    regenerateSection,
    switchQuotaModel,
    closeQuotaModal,
    recoverActiveSession,
    reportFailedLoads,
    refreshModelOptions: () => fetchModelOptions().then(setModelOptions).catch(() => {}),
  };
}
