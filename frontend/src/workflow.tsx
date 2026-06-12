import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type {
  GenerateParams,
  GenerationSessionSnapshot,
  KnowledgeSourceStats,
  UploadResult,
} from "./types";

const WORKFLOW_KEY = "xiangmushu.workflow.state";

type WorkflowState = {
  generate: {
    slug: string;
    template: string;
    generationBrief: string;
    qualityMode: "balanced" | "quality" | "speed";
    session: GenerationSessionSnapshot | null;
  };
  knowledge: {
    selectedSlug: string;
    uploadResults: UploadResult[];
    stats: KnowledgeSourceStats | null;
  };
};

type WorkflowContextValue = {
  state: WorkflowState;
  setGenerateSelections: (patch: Partial<WorkflowState["generate"]>) => void;
  setGenerateSession: (session: GenerationSessionSnapshot | null) => void;
  setKnowledgeState: (patch: Partial<WorkflowState["knowledge"]>) => void;
  clearGenerateSession: () => void;
};

const defaultState: WorkflowState = {
  generate: {
    slug: "",
    template: "",
    generationBrief: "",
    qualityMode: "balanced",
    session: null,
  },
  knowledge: {
    selectedSlug: "",
    uploadResults: [],
    stats: null,
  },
};

const WorkflowContext = createContext<WorkflowContextValue | null>(null);

function loadState(): WorkflowState {
  try {
    const raw = window.localStorage.getItem(WORKFLOW_KEY);
    if (!raw) return defaultState;
    const parsed = JSON.parse(raw) as Partial<WorkflowState>;
    return {
      generate: { ...defaultState.generate, ...(parsed.generate ?? {}) },
      knowledge: { ...defaultState.knowledge, ...(parsed.knowledge ?? {}) },
    };
  } catch {
    return defaultState;
  }
}

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkflowState>(() => loadState());

  useEffect(() => {
    window.localStorage.setItem(WORKFLOW_KEY, JSON.stringify(state));
  }, [state]);

  const setGenerateSelections = useCallback((patch: Partial<WorkflowState["generate"]>) => {
    setState((prev) => ({
      ...prev,
      generate: { ...prev.generate, ...patch },
    }));
  }, []);

  const setGenerateSession = useCallback((session: GenerationSessionSnapshot | null) => {
    setState((prev) => ({
      ...prev,
      generate: { ...prev.generate, session },
    }));
  }, []);

  const setKnowledgeState = useCallback((patch: Partial<WorkflowState["knowledge"]>) => {
    setState((prev) => ({
      ...prev,
      knowledge: { ...prev.knowledge, ...patch },
    }));
  }, []);

  const clearGenerateSession = useCallback(() => {
    setState((prev) => ({
      ...prev,
      generate: { ...prev.generate, session: null },
    }));
  }, []);

  const value = useMemo<WorkflowContextValue>(
    () => ({
      state,
      setGenerateSelections,
      setGenerateSession,
      setKnowledgeState,
      clearGenerateSession,
    }),
    [clearGenerateSession, setGenerateSelections, setGenerateSession, setKnowledgeState, state],
  );

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>;
}

export function useWorkflow() {
  const value = useContext(WorkflowContext);
  if (!value) throw new Error("useWorkflow must be used inside WorkflowProvider");
  return value;
}

export function deriveGenerateReadiness(params: {
  hasValidatedKey: boolean;
  hasKnowledgeBase: boolean;
  hasKnowledgeSources: boolean;
  hasTemplate: boolean;
}) {
  if (!params.hasValidatedKey) return { ready: false, reason: "missing_key" as const };
  if (!params.hasKnowledgeBase || !params.hasKnowledgeSources) return { ready: false, reason: "missing_knowledge" as const };
  if (!params.hasTemplate) return { ready: false, reason: "missing_template" as const };
  return { ready: true, reason: "ready" as const };
}
