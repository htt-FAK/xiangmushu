import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { useLocation } from "react-router-dom";
import {
  fetchActiveGenerationSession,
  fetchActiveTemplateAnalysisSession,
  fetchGenerationSession,
  fetchTemplateAnalysisSession,
  streamGenerationSession,
  streamTemplateAnalysisSession,
} from "./api";
import { useAuth } from "./auth";
import { useToast } from "./components/Toast";
import { useI18n } from "./i18n";
import { reduceTemplateAnalysisSession } from "./templateAnalysisReducer";
import type { GenerateEvent, TemplateAnalysisEvent } from "./types";
import { useWorkflow } from "./workflow";

type BackgroundSessionsContextValue = {
  ensureTemplateStream: (sessionId: string, afterSeq?: number) => void;
  ensureGenerationStream: (sessionId: string, afterSeq?: number) => void;
  abortGenerationStream: () => void;
};

const BackgroundSessionsContext = createContext<BackgroundSessionsContextValue | null>(null);

export function useBackgroundSessions() {
  const value = useContext(BackgroundSessionsContext);
  if (!value) throw new Error("useBackgroundSessions must be used inside BackgroundSessionsProvider");
  return value;
}

export function BackgroundSessionsProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const location = useLocation();
  const {
    state,
    setGenerateSession,
    setTemplateAnalysisSession,
    clearGenerateSession,
    clearTemplateAnalysisSession,
  } = useWorkflow();

  const templateAbortRef = useRef<AbortController | null>(null);
  const generationAbortRef = useRef<AbortController | null>(null);
  const templateSubIdRef = useRef<string | null>(null);
  const generationSubIdRef = useRef<string | null>(null);
  const templateSessionRef = useRef(state.templateAnalysis.session);
  const generationSessionRef = useRef(state.generate.session);
  const prevTemplateStatusRef = useRef<string | null>(null);
  const prevGenerationStatusRef = useRef<string | null>(null);
  const genFetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    templateSessionRef.current = state.templateAnalysis.session;
  }, [state.templateAnalysis.session]);

  useEffect(() => {
    generationSessionRef.current = state.generate.session;
  }, [state.generate.session]);

  const refreshGenerationSnapshot = useCallback(
    async (sessionId: string) => {
      try {
        const result = await fetchGenerationSession(sessionId);
        if (result.session) {
          setGenerateSession(result.session);
        }
      } catch {
        // Ignore transient fetch failures during streaming.
      }
    },
    [setGenerateSession],
  );

  const scheduleGenerationRefresh = useCallback(
    (sessionId: string) => {
      if (genFetchTimerRef.current) clearTimeout(genFetchTimerRef.current);
      genFetchTimerRef.current = setTimeout(() => {
        void refreshGenerationSnapshot(sessionId);
      }, 300);
    },
    [refreshGenerationSnapshot],
  );

  const ensureTemplateStream = useCallback(
    (sessionId: string, afterSeq = 0) => {
      if (templateSubIdRef.current === sessionId && templateAbortRef.current) return;

      templateAbortRef.current?.abort();
      const controller = new AbortController();
      templateAbortRef.current = controller;
      templateSubIdRef.current = sessionId;

      void (async () => {
        try {
          await streamTemplateAnalysisSession(
            sessionId,
            (event: TemplateAnalysisEvent) => {
              if (controller.signal.aborted) return;
              const current = templateSessionRef.current;
              if (!current || current.session_id !== sessionId) return;
              const next = reduceTemplateAnalysisSession(current, event, {
                statusComplete: t("template.statusComplete"),
                statusFailed: t("template.statusFailed"),
              });
              templateSessionRef.current = next;
              setTemplateAnalysisSession(next);
            },
            controller.signal,
            afterSeq,
          );
          if (!controller.signal.aborted) {
            const latest = await fetchTemplateAnalysisSession(sessionId);
            if (latest.session) {
              templateSessionRef.current = latest.session;
              setTemplateAnalysisSession(latest.session);
            }
          }
        } catch {
          // Ignore abort errors.
        } finally {
          if (templateAbortRef.current === controller) {
            templateAbortRef.current = null;
            if (templateSubIdRef.current === sessionId) {
              templateSubIdRef.current = null;
            }
          }
        }
      })();
    },
    [setTemplateAnalysisSession, t],
  );

  const ensureGenerationStream = useCallback(
    (sessionId: string, afterSeq = 0) => {
      if (generationSubIdRef.current === sessionId && generationAbortRef.current) return;

      generationAbortRef.current?.abort();
      const controller = new AbortController();
      generationAbortRef.current = controller;
      generationSubIdRef.current = sessionId;

      void (async () => {
        try {
          await streamGenerationSession(
            sessionId,
            (event: GenerateEvent) => {
              if (controller.signal.aborted) return;
              if (event.type === "heartbeat") return;
              scheduleGenerationRefresh(sessionId);
            },
            controller.signal,
            afterSeq,
          );
          if (!controller.signal.aborted) {
            await refreshGenerationSnapshot(sessionId);
          }
        } catch {
          // Ignore abort errors.
        } finally {
          if (generationAbortRef.current === controller) {
            generationAbortRef.current = null;
            if (generationSubIdRef.current === sessionId) {
              generationSubIdRef.current = null;
            }
          }
        }
      })();
    },
    [refreshGenerationSnapshot, scheduleGenerationRefresh],
  );

  const abortGenerationStream = useCallback(() => {
    if (genFetchTimerRef.current) {
      clearTimeout(genFetchTimerRef.current);
      genFetchTimerRef.current = null;
    }
    generationAbortRef.current?.abort();
    generationAbortRef.current = null;
    generationSubIdRef.current = null;
  }, []);

  const recoverSessions = useCallback(async () => {
    const [templateResult, generationResult] = await Promise.allSettled([
      fetchActiveTemplateAnalysisSession(),
      fetchActiveGenerationSession(),
    ]);

    if (templateResult.status === "fulfilled" && templateResult.value.session) {
      const session = templateResult.value.session;
      templateSessionRef.current = session;
      setTemplateAnalysisSession(session);
      if (session.status === "running") {
        ensureTemplateStream(session.session_id, session.last_seq);
      }
    } else {
      templateAbortRef.current?.abort();
      templateAbortRef.current = null;
      templateSubIdRef.current = null;
      templateSessionRef.current = null;
      clearTemplateAnalysisSession();
    }

    if (generationResult.status === "fulfilled" && generationResult.value.session) {
      const session = generationResult.value.session;
      generationSessionRef.current = session;
      setGenerateSession(session);
      if (session.status === "running") {
        ensureGenerationStream(session.session_id, session.last_seq);
      }
    } else {
      if (genFetchTimerRef.current) {
        clearTimeout(genFetchTimerRef.current);
        genFetchTimerRef.current = null;
      }
      generationAbortRef.current?.abort();
      generationAbortRef.current = null;
      generationSubIdRef.current = null;
      generationSessionRef.current = null;
      clearGenerateSession();
    }
  }, [clearGenerateSession, clearTemplateAnalysisSession, ensureGenerationStream, ensureTemplateStream, setGenerateSession, setTemplateAnalysisSession]);

  useEffect(() => {
    if (!auth.isAuthenticated) {
      templateAbortRef.current?.abort();
      generationAbortRef.current?.abort();
      templateAbortRef.current = null;
      generationAbortRef.current = null;
      templateSubIdRef.current = null;
      generationSubIdRef.current = null;
      prevTemplateStatusRef.current = null;
      prevGenerationStatusRef.current = null;
      clearGenerateSession();
      clearTemplateAnalysisSession();
      return;
    }
    void recoverSessions();
  }, [auth.isAuthenticated, clearGenerateSession, clearTemplateAnalysisSession, recoverSessions]);

  useEffect(() => {
    const session = state.templateAnalysis.session;
    if (!session) {
      prevTemplateStatusRef.current = null;
      return;
    }
    const prev = prevTemplateStatusRef.current;
    if (prev === "running" && (session.status === "done" || session.status === "error")) {
      if (location.pathname !== "/template") {
        const name = session.template || session.statusMessage || t("template.results");
        if (session.status === "done") {
          toast.success(t("template.toastDone", name));
        } else {
          toast.error(t("template.toastError", name));
        }
      }
    }
    prevTemplateStatusRef.current = session.status;
  }, [location.pathname, state.templateAnalysis.session, t, toast]);

  useEffect(() => {
    const session = state.generate.session;
    if (!session) {
      prevGenerationStatusRef.current = null;
      return;
    }
    const prev = prevGenerationStatusRef.current;
    if (prev === "running" && (session.status === "done" || session.status === "error")) {
      if (location.pathname !== "/generate") {
        if (session.status === "done") {
          toast.success(t("generate.toastDone"));
        } else {
          toast.error(session.last_error?.message || t("generate.streamDisconnected"));
        }
      }
    }
    prevGenerationStatusRef.current = session.status;
  }, [location.pathname, state.generate.session, t, toast]);

  const value = useMemo<BackgroundSessionsContextValue>(
    () => ({
      ensureTemplateStream,
      ensureGenerationStream,
      abortGenerationStream,
    }),
    [abortGenerationStream, ensureGenerationStream, ensureTemplateStream],
  );

  return <BackgroundSessionsContext.Provider value={value}>{children}</BackgroundSessionsContext.Provider>;
}
