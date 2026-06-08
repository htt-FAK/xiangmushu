import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { clsx } from "../utils";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-col gap-4 border-b border-white/10 pb-5 md:mb-8 md:gap-5 md:pb-7 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl min-w-0">
        <p className="mb-2 font-display text-xs font-semibold uppercase tracking-[0.22em] text-signal-cyan md:mb-3 md:tracking-[0.26em]">
          {eyebrow}
        </p>
        <h1 className="break-words font-display text-2xl font-semibold leading-tight text-white md:text-5xl">
          {title}
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 md:mt-4 md:leading-7">{description}</p>
      </div>
      {action && <div className="w-full lg:w-auto">{action}</div>}
    </header>
  );
}

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("border border-white/10 bg-white/[0.045] p-4 shadow-panel backdrop-blur md:p-5", className)}>
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  tone = "cyan",
  className,
}: {
  label: string;
  value: string | number;
  tone?: "cyan" | "lime" | "amber" | "rose";
  className?: string;
}) {
  const toneClass = {
    cyan: "text-signal-cyan",
    lime: "text-signal-lime",
    amber: "text-signal-amber",
    rose: "text-signal-rose",
  }[tone];

  return (
    <div className={clsx("min-w-0 border border-white/10 bg-night-850/80 p-3.5 md:p-4", className)}>
      <p className="break-words text-[11px] font-medium uppercase tracking-[0.12em] text-slate-500 md:text-xs md:normal-case md:tracking-normal">{label}</p>
      <p className={clsx("mt-1.5 break-words font-display text-xl font-semibold leading-tight md:mt-2 md:text-3xl", toneClass)}>{value}</p>
    </div>
  );
}

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
}) {
  const variantClass = {
    primary:
      "border-signal-cyan/70 bg-signal-cyan text-night-950 shadow-glow hover:bg-white",
    ghost:
      "border-white/10 bg-white/[0.055] text-slate-100 hover:border-signal-cyan/50 hover:text-signal-cyan",
    danger:
      "border-signal-rose/50 bg-signal-rose/10 text-signal-rose hover:bg-signal-rose hover:text-white",
  }[variant];

  return (
    <button
      className={clsx(
        "inline-flex min-h-11 items-center justify-center gap-2 border px-4 text-sm font-semibold transition active:scale-[0.97] active:brightness-90 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-45",
        variantClass,
        className,
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={clsx(
        "min-h-12 w-full scroll-mb-32 border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-signal-cyan/70 focus:scroll-mt-4 md:min-h-11",
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </span>
      {children}
    </label>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-dashed border-white/15 bg-night-900/60 p-6 text-center md:p-8">
      <p className="font-display text-xl font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm text-slate-400">{body}</p>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="mb-5 border border-signal-rose/40 bg-signal-rose/10 px-4 py-3 text-sm text-rose-100">
      {message}
    </div>
  );
}
