import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import { useI18n } from "../i18n";
import { clsx } from "../utils";

type ToastTone = "success" | "error" | "info";

type ToastItem = {
  id: string;
  tone: ToastTone;
  message: string;
};

type ToastContextValue = {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const toneStyles: Record<ToastTone, string> = {
  success: "border-signal-lime/40 bg-signal-lime/10 text-lime-100",
  error: "border-signal-rose/40 bg-signal-rose/10 text-rose-100",
  info: "border-signal-cyan/40 bg-signal-cyan/10 text-cyan-100",
};

function ToastIcon({ tone }: { tone: ToastTone }) {
  if (tone === "success") return <CheckCircle2 className="shrink-0" size={20} />;
  if (tone === "error") return <XCircle className="shrink-0" size={20} />;
  return <Info className="shrink-0" size={20} />;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [items, setItems] = useState<ToastItem[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const trimmed = message.trim();
      if (!trimmed) return;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setItems((prev) => [...prev.slice(-4), { id, tone, message: trimmed }]);
      const timer = setTimeout(() => dismiss(id), 4500);
      timersRef.current.set(id, timer);
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
      info: (message) => push("info", message),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(100vw-2rem,24rem)] flex-col gap-2 md:right-6 md:top-6"
        aria-live="polite"
      >
        {items.map((item) => (
          <div
            key={item.id}
            className={clsx(
              "pointer-events-auto flex items-start gap-3 border px-4 py-3 text-sm shadow-lg backdrop-blur-md",
              toneStyles[item.tone],
            )}
          >
            <ToastIcon tone={item.tone} />
            <p className="min-w-0 flex-1 break-words leading-6">{item.message}</p>
            <button
              type="button"
              className="shrink-0 opacity-70 transition hover:opacity-100"
              onClick={() => dismiss(item.id)}
              aria-label={t("app.close")}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
