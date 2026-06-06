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
    <header className="mb-8 flex flex-col gap-5 border-b border-white/10 pb-7 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl">
        <p className="mb-3 font-display text-xs font-semibold uppercase tracking-[0.26em] text-signal-cyan">
          {eyebrow}
        </p>
        <h1 className="font-display text-4xl font-semibold leading-tight text-white md:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">{description}</p>
      </div>
      {action}
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
    <section className={clsx("border border-white/10 bg-white/[0.045] p-5 shadow-panel backdrop-blur", className)}>
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  tone = "cyan",
}: {
  label: string;
  value: string | number;
  tone?: "cyan" | "lime" | "amber" | "rose";
}) {
  const toneClass = {
    cyan: "text-signal-cyan",
    lime: "text-signal-lime",
    amber: "text-signal-amber",
    rose: "text-signal-rose",
  }[tone];

  return (
    <div className="border border-white/10 bg-night-850/80 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={clsx("mt-2 font-display text-3xl font-semibold", toneClass)}>{value}</p>
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
        "inline-flex min-h-10 items-center justify-center gap-2 border px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45",
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
        "min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-signal-cyan/70",
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
    <div className="border border-dashed border-white/15 bg-night-900/60 p-8 text-center">
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
