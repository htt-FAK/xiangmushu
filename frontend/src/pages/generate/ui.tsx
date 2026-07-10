import { AlertTriangle, CheckCircle2, Loader2, MessageSquareText } from "lucide-react";
import type { ReactNode } from "react";
import { ErrorBanner } from "../../components/ui";
import { clsx } from "../../utils";
import type { GenerateStep, GenerationNotice } from "./useGenerationSession";

const stepOrder: GenerateStep[] = ["idle", "retrieval", "analysis", "generation", "audit", "done"];

export function SectionTitle({
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

export function TextArea({
  value,
  onChange,
  placeholder,
  compact = false,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  compact?: boolean;
  disabled?: boolean;
}) {
  return (
    <textarea
      className={clsx(
        "w-full resize-y scroll-mb-32 border border-white/10 bg-night-950 px-3 text-sm leading-6 text-white outline-none transition placeholder:text-slate-600 focus:border-signal-cyan/70 focus:scroll-mt-4 disabled:opacity-40 disabled:pointer-events-none",
        compact ? "min-h-28 py-2.5" : "min-h-32 py-3",
      )}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      maxLength={1200}
    />
  );
}

export function SetupField({
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

export function StepIndicator({
  step,
  label,
  icon,
  currentStep,
  className,
}: {
  step: GenerateStep;
  label: string;
  icon: ReactNode;
  currentStep: GenerateStep;
  className?: string;
}) {
  const isActive = currentStep === step;
  const isCompleted = stepOrder.indexOf(currentStep) > stepOrder.indexOf(step);

  return (
    <div
      className={clsx(
        "flex items-center gap-2  border px-3 py-2 transition-all",
        isActive
          ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
          : isCompleted
            ? "border-signal-lime/50 bg-signal-lime/5 text-signal-lime"
            : "border-white/10 bg-night-950/50 text-slate-500",
        className,
      )}
    >
      <div className="shrink-0">{icon}</div>
      <span className="text-xs font-medium">{label}</span>
      {isActive && <Loader2 aria-hidden="true" className="ml-auto animate-spin" size={14} />}
      {isCompleted && <CheckCircle2 aria-hidden="true" className="ml-auto" size={14} />}
    </div>
  );
}

/** Renders the generation notice (typed banner with optional retry, or a plain error banner). */
export function NoticeBanner({
  notice,
  retryLabel,
  onDismiss,
}: {
  notice: GenerationNotice;
  retryLabel: string;
  onDismiss: () => void;
}) {
  if (!notice) return null;
  if (notice.kind === "plain") return <ErrorBanner message={notice.message} />;

  const styles = {
    warning: "border-signal-amber/40 bg-signal-amber/10 text-amber-100",
    error: "border-rose-500/40 bg-rose-500/10 text-rose-100",
    info: "border-signal-cyan/40 bg-signal-cyan/10 text-cyan-100",
  };
  const icons = {
    warning: <AlertTriangle aria-hidden="true" className="shrink-0" size={20} />,
    error: <AlertTriangle aria-hidden="true" className="shrink-0" size={20} />,
    info: <MessageSquareText aria-hidden="true" className="shrink-0" size={20} />,
  };

  return (
    <div
      className={clsx(
        "mb-6 flex flex-col gap-4 border px-4 py-4 sm:flex-row sm:items-center sm:justify-between md:px-5",
        styles[notice.level] || styles.error,
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        {icons[notice.level] || icons.error}
        <p className="min-w-0 break-words text-sm font-semibold">{notice.message}</p>
      </div>
      {notice.retryable && (
        <button
          onClick={onDismiss}
          className="inline-flex min-h-11 items-center justify-center border border-current px-4 text-xs font-bold transition hover:bg-white/10 sm:w-auto"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}
