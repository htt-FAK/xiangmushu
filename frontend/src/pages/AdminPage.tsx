import { useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Coins,
  Cpu,
  Gauge,
  KeyRound,
  ShieldAlert,
  Users,
  Zap,
} from "lucide-react";
import { useI18n } from "../i18n";
import { ErrorBanner, PageHeader, Panel } from "../components/ui";
import { apiUrl } from "../apiBase";
import { buildAuthHeaders } from "../auth";

type DailyStat = { day: string; generations: number; cost: number; input_tokens: number; output_tokens: number };
type ModelStat = { model: string; count: number; cost: number };
type AdminStats = {
  total_users: number;
  total_generations: number;
  total_cost_cny: number;
  total_input_tokens: number;
  total_output_tokens: number;
  users_with_api_key: number;
  daily: DailyStat[];
  top_models: ModelStat[];
};

type MetricTone = "cyan" | "lime" | "amber" | "white";

const toneClass: Record<MetricTone, { text: string; border: string; bg: string; bar: string }> = {
  cyan: {
    text: "text-signal-cyan",
    border: "border-signal-cyan/40",
    bg: "bg-signal-cyan/10",
    bar: "bg-signal-cyan",
  },
  lime: {
    text: "text-signal-lime",
    border: "border-signal-lime/40",
    bg: "bg-signal-lime/10",
    bar: "bg-signal-lime",
  },
  amber: {
    text: "text-amber-400",
    border: "border-amber-400/40",
    bg: "bg-amber-400/10",
    bar: "bg-amber-400",
  },
  white: {
    text: "text-white",
    border: "border-white/20",
    bg: "bg-white/5",
    bar: "bg-white",
  },
};

function formatInteger(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function formatCost(value: number) {
  return `¥${new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(value)}`;
}

function formatTokens(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return formatInteger(value);
}

function CountUpNumber({
  value,
  format = formatInteger,
  duration = 760,
}: {
  value: number;
  format?: (value: number) => string;
  duration?: number;
}) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let frame = 0;
    const start = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(value * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [duration, value]);

  return <>{format(displayValue)}</>;
}

function MetricBlock({
  icon: Icon,
  label,
  value,
  format,
  tone,
  className = "",
  subValue,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  format?: (value: number) => string;
  tone: MetricTone;
  className?: string;
  subValue?: string;
}) {
  const classes = toneClass[tone];

  return (
    <div className={`group border border-white/10 bg-night-950/80 p-4 transition hover:border-white/25 ${className}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
            {label}
          </p>
          <p className={`mt-3 font-mono text-3xl font-semibold leading-none tabular-nums md:text-4xl ${classes.text}`}>
            <CountUpNumber value={value} format={format} />
          </p>
        </div>
        <div className={`border ${classes.border} ${classes.bg} p-2 ${classes.text}`}>
          <Icon size={18} strokeWidth={1.7} />
        </div>
      </div>
      {subValue && (
        <p className="mt-4 border-t border-white/10 pt-3 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500 tabular-nums">
          {subValue}
        </p>
      )}
    </div>
  );
}

function EmptyTerminalState({ label }: { label: string }) {
  return (
    <div className="flex min-h-36 items-center justify-center border border-dashed border-white/15 bg-night-950/60">
      <p className="font-display text-sm font-semibold uppercase tracking-[0.26em] text-slate-500">{label}</p>
    </div>
  );
}

function SectionTitle({ icon: Icon, title, tone = "cyan" }: { icon: LucideIcon; title: string; tone?: MetricTone }) {
  const classes = toneClass[tone];

  return (
    <div className="mb-4 flex items-center justify-between gap-4 border-b border-white/10 pb-3">
      <h2 className="flex items-center gap-2 font-display text-base font-semibold uppercase tracking-[0.18em] text-white">
        <Icon size={17} className={classes.text} strokeWidth={1.8} />
        {title}
      </h2>
      <span className={`h-1.5 w-1.5 ${classes.bar}`} />
    </div>
  );
}

export default function AdminPage() {
  const { t } = useI18n();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [barsVisible, setBarsVisible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(apiUrl("/api/admin/stats"), { headers: buildAuthHeaders() })
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 403 ? t("admin.forbidden") : String(res.status));
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setStats(data as AdminStats);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  useEffect(() => {
    setBarsVisible(false);
    if (!stats) return;
    const timer = window.setTimeout(() => setBarsVisible(true), 80);
    return () => window.clearTimeout(timer);
  }, [stats]);

  const maxModelCount = useMemo(
    () => Math.max(1, ...(stats?.top_models.map((model) => model.count) ?? [])),
    [stats],
  );

  const hasAnyData = Boolean(
    stats &&
      (stats.total_users > 0 ||
        stats.total_generations > 0 ||
        stats.total_cost_cny > 0 ||
        stats.users_with_api_key > 0 ||
        stats.daily.length > 0 ||
        stats.top_models.length > 0),
  );

  if (loading) {
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <div className="h-8 w-8 animate-spin border border-signal-cyan/20 border-t-signal-cyan" />
      </div>
    );
  }

  return (
    <>
      <PageHeader eyebrow={t("admin.eyebrow")} title={t("admin.title")} description={t("admin.description")} />
      <ErrorBanner message={error} />

      {error === t("admin.forbidden") && (
        <Panel className="border-signal-rose/35 bg-night-950/80 p-6 shadow-none">
          <div className="flex items-center gap-3 text-signal-rose">
            <ShieldAlert size={20} />
            <p className="font-display text-sm font-semibold uppercase tracking-[0.22em]">{t("admin.forbidden")}</p>
          </div>
        </Panel>
      )}

      {stats && (
        <div className="space-y-6">
          {!hasAnyData && <EmptyTerminalState label={t("admin.noData")} />}

          <section className="grid gap-3 lg:grid-cols-12">
            <MetricBlock
              icon={Users}
              label={t("admin.totalUsers")}
              value={stats.total_users}
              tone="cyan"
              className="lg:col-span-3"
            />
            <MetricBlock
              icon={Zap}
              label={t("admin.totalGenerations")}
              value={stats.total_generations}
              tone="lime"
              className="lg:col-span-4"
            />
            <MetricBlock
              icon={Coins}
              label={t("admin.totalCost")}
              value={stats.total_cost_cny}
              format={formatCost}
              tone="amber"
              className="lg:col-span-3"
              subValue={`${t("admin.colInputTokens")} ${formatTokens(stats.total_input_tokens)} / ${t("admin.colOutputTokens")} ${formatTokens(stats.total_output_tokens)}`}
            />
            <MetricBlock
              icon={KeyRound}
              label={t("admin.usersWithKey")}
              value={stats.users_with_api_key}
              tone="white"
              className="lg:col-span-2"
            />
          </section>

          <Panel className="bg-night-950/80 p-0 shadow-none backdrop-blur-none">
            <div className="p-4 pb-0">
              <SectionTitle icon={BarChart3} title={t("admin.dailyTitle")} tone="cyan" />
            </div>
            {stats.daily.length === 0 ? (
              <div className="p-4 pt-0">
                <EmptyTerminalState label={t("admin.noData")} />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-collapse text-left">
                  <thead>
                    <tr className="border-y border-white/10 bg-white/[0.025] font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <th className="px-4 py-3">{t("admin.colDate")}</th>
                      <th className="px-4 py-3 text-right">{t("admin.colGenerations")}</th>
                      <th className="px-4 py-3 text-right">{t("admin.colCost")}</th>
                      <th className="px-4 py-3 text-right">{t("admin.colInputTokens")}</th>
                      <th className="px-4 py-3 text-right">{t("admin.colOutputTokens")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.daily.map((day) => (
                      <tr
                        key={day.day}
                        className="border-b border-white/[0.06] text-sm text-slate-300 transition hover:bg-signal-cyan/[0.07] hover:text-white"
                      >
                        <td className="px-4 py-3 font-mono text-xs text-slate-400 tabular-nums">{day.day}</td>
                        <td className="px-4 py-3 text-right font-mono text-signal-lime tabular-nums">
                          {formatInteger(day.generations)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-amber-400 tabular-nums">
                          {formatCost(day.cost)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-slate-300 tabular-nums">
                          {formatTokens(day.input_tokens)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-slate-300 tabular-nums">
                          {formatTokens(day.output_tokens)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel className="bg-night-950/80 shadow-none backdrop-blur-none">
            <SectionTitle icon={Cpu} title={t("admin.topModels")} tone="lime" />
            {stats.top_models.length === 0 ? (
              <EmptyTerminalState label={t("admin.noData")} />
            ) : (
              <div className="space-y-3">
                {stats.top_models.map((model, index) => {
                  const pct = (model.count / maxModelCount) * 100;
                  const tone = index === 0 ? "lime" : index === 1 ? "cyan" : "amber";
                  const classes = toneClass[tone];

                  return (
                    <div
                      key={model.model}
                      className="grid grid-cols-[minmax(8rem,14rem)_1fr_auto_auto] items-center gap-3 border-b border-white/[0.06] pb-3 text-sm transition hover:border-signal-cyan/30 hover:bg-white/[0.025] sm:gap-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-mono text-xs text-slate-300">{model.model}</p>
                      </div>
                      <div className="h-6 border border-white/10 bg-night-900/80 p-1">
                        <div
                          className={`h-full ${classes.bar} opacity-80 transition-all duration-700 ease-out`}
                          style={{ width: barsVisible ? `${pct}%` : "0%" }}
                        />
                      </div>
                      <p className={`w-16 text-right font-mono text-xs tabular-nums ${classes.text}`}>
                        {formatInteger(model.count)}
                      </p>
                      <p className="w-24 text-right font-mono text-xs text-amber-400 tabular-nums">
                        {formatCost(model.cost)}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          <div className="grid gap-3 border border-white/10 bg-night-950/70 p-4 text-xs text-slate-500 md:grid-cols-3">
            <div className="flex items-center gap-2 font-mono tabular-nums">
              <Gauge size={15} className="text-signal-cyan" />
              {t("admin.colGenerations")} {formatInteger(stats.total_generations)}
            </div>
            <div className="flex items-center gap-2 font-mono tabular-nums">
              <Activity size={15} className="text-signal-lime" />
              {t("admin.colInputTokens")} {formatTokens(stats.total_input_tokens)}
            </div>
            <div className="flex items-center gap-2 font-mono tabular-nums">
              <Activity size={15} className="text-amber-400" />
              {t("admin.colOutputTokens")} {formatTokens(stats.total_output_tokens)}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
