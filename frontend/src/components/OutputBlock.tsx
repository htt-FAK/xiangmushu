import { clsx } from "../utils";
import type { ReactNode } from "react";

export type OutputBlockData = {
  chapter: string;
  text: string;
  model?: string;
  tier?: string;
  role?: string;
  kbHits?: number;
  evidenceRefs?: string[];
  auditVerdict?: string;
  auditIssues?: string[];
  revised?: boolean;
};

export function OutputBlock({
  block,
  fallbackName,
  waitingText,
  auditResultLabel,
  revisedLabel,
  routeLabel = "route",
  modelLabel = "model",
  kbHitsLabel = "kb hits",
  auditFallbackLabel = "issue",
  action,
  busy = false,
  busyLabel = "refreshing",
  preview = false,
  previewClassName,
}: {
  block: OutputBlockData;
  fallbackName: string;
  waitingText: string;
  auditResultLabel: string;
  revisedLabel: string;
  routeLabel?: string;
  modelLabel?: string;
  kbHitsLabel?: string;
  auditFallbackLabel?: string;
  action?: ReactNode;
  busy?: boolean;
  busyLabel?: string;
  preview?: boolean;
  previewClassName?: string;
}) {
  const visibleEvidence = preview ? block.evidenceRefs?.slice(0, 3) : block.evidenceRefs;
  const visibleIssues = preview ? block.auditIssues?.slice(0, 2) : block.auditIssues;
  return (
    <article
      className={clsx(
        "min-w-0 border bg-night-950 p-3.5 shadow-[0_14px_48px_rgba(0,0,0,0.22)] transition-all duration-300 md:p-4",
        busy
          ? "border-signal-cyan/50 shadow-[0_0_0_1px_rgba(54,242,230,0.12),0_18px_52px_rgba(54,242,230,0.10)]"
          : "border-white/10",
        previewClassName,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-3">
        <div className="min-w-0 flex-1">
          <p className="min-w-0 break-words font-display text-base font-semibold leading-snug text-signal-cyan md:text-lg">
            {block.chapter || fallbackName}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-slate-300 md:text-xs">
            {block.tier && (
              <span className="max-w-full break-all border border-white/10 bg-night-900/70 px-2 py-1 uppercase tracking-[0.08em]">
                {routeLabel}: {block.tier}
              </span>
            )}
            {block.role && (
              <span className="max-w-full break-all border border-signal-lime/20 bg-signal-lime/10 px-2 py-1 uppercase tracking-[0.08em] text-lime-100">
                role: {block.role}
              </span>
            )}
            {block.model && (
              <span className="max-w-full break-all border border-white/10 bg-night-900/70 px-2 py-1">
                {modelLabel}: {block.model}
              </span>
            )}
            {typeof block.kbHits === "number" && (
              <span className="max-w-full break-all border border-white/10 bg-night-900/70 px-2 py-1">
                {kbHitsLabel}: {block.kbHits}
              </span>
            )}
            {busy && (
              <span className="max-w-full break-all border border-signal-cyan/25 bg-signal-cyan/10 px-2 py-1 text-cyan-100">
                {busyLabel}
              </span>
            )}
          </div>
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>

      {visibleEvidence && visibleEvidence.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {visibleEvidence.map((item) => (
            <span
              key={item}
              className="max-w-full break-all border border-signal-cyan/20 bg-signal-cyan/10 px-2 py-1 text-[11px] text-cyan-100 md:text-xs"
            >
              {item}
            </span>
          ))}
        </div>
      )}

      {visibleIssues && visibleIssues.length > 0 && (
        <div className="mt-3 min-w-0 border border-signal-amber/30 bg-signal-amber/10 p-3 text-sm text-amber-100">
          <p className="font-semibold">
            {auditResultLabel}: {block.auditVerdict || auditFallbackLabel}
            {block.revised ? revisedLabel : ""}
          </p>
          <div className="mt-2 space-y-1">
            {visibleIssues.map((issue) => (
              <p className="break-words" key={issue}>{issue}</p>
            ))}
          </div>
        </div>
      )}

      <pre
        className={clsx(
          "mt-3 max-w-full overflow-x-auto whitespace-pre-wrap break-words text-sm leading-7 text-slate-300",
          preview ? "max-h-36 overflow-y-auto" : "",
        )}
      >
        {block.text || waitingText}
      </pre>
    </article>
  );
}
