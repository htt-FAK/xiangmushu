import { useEffect, useState } from "react";
import { BarChart3, DollarSign, KeyRound, Users, Zap } from "lucide-react";
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

function StatCard({ icon: Icon, label, value, sub, tone }: { icon: typeof Users; label: string; value: string; sub?: string; tone: string }) {
  return (
    <div className={`border border-white/10 bg-night-950/70 p-5`}>
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center border text-lg`} style={{ borderColor: `${tone}66`, color: tone, background: `${tone}14` }}>
          <Icon size={20} />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{label}</p>
          <p className="mt-1 font-display text-2xl font-bold text-white">{value}</p>
          {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

export default function AdminPage() {
  const { t } = useI18n();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(apiUrl("/api/admin/stats"), { headers: buildAuthHeaders() })
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 403 ? t("admin.forbidden") : `HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => { if (!cancelled) setStats(data as AdminStats); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : String(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t]);

  if (loading) {
    return <div className="flex min-h-[60vh] items-center justify-center text-sm font-semibold uppercase tracking-widest text-slate-500">Loading...</div>;
  }

  return (
    <>
      <PageHeader eyebrow={t("admin.eyebrow")} title={t("admin.title")} description={t("admin.description")} />
      <ErrorBanner message={error} />

      {stats && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={Users} label={t("admin.totalUsers")} value={String(stats.total_users)} tone="#a78bfa" />
            <StatCard icon={Zap} label={t("admin.totalGenerations")} value={String(stats.total_generations)} tone="#22d3ee" />
            <StatCard icon={DollarSign} label={t("admin.totalCost")} value={`¥${stats.total_cost_cny.toFixed(4)}`} sub={`${(stats.total_input_tokens / 1000).toFixed(1)}K in / ${(stats.total_output_tokens / 1000).toFixed(1)}K out`} tone="#fbbf24" />
            <StatCard icon={KeyRound} label={t("admin.usersWithKey")} value={String(stats.users_with_api_key)} tone="#34d399" />
          </div>

          {/* Daily chart */}
          <Panel className="mt-6">
            <h3 className="font-display text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 size={18} className="text-signal-cyan" />
              {t("admin.dailyTitle")}
            </h3>
            {stats.daily.length === 0 ? (
              <p className="text-sm text-slate-500">{t("admin.noData")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500">
                      <th className="pb-2 pr-4">{t("admin.colDate")}</th>
                      <th className="pb-2 pr-4 text-right">{t("admin.colGenerations")}</th>
                      <th className="pb-2 pr-4 text-right">{t("admin.colCost")}</th>
                      <th className="pb-2 pr-4 text-right">{t("admin.colInputTokens")}</th>
                      <th className="pb-2 text-right">{t("admin.colOutputTokens")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.daily.map((d) => (
                      <tr key={d.day} className="border-b border-white/5 text-slate-300">
                        <td className="py-2 pr-4 font-mono text-xs">{d.day}</td>
                        <td className="py-2 pr-4 text-right">{d.generations}</td>
                        <td className="py-2 pr-4 text-right font-mono text-xs">¥{d.cost.toFixed(4)}</td>
                        <td className="py-2 pr-4 text-right font-mono text-xs">{(d.input_tokens / 1000).toFixed(1)}K</td>
                        <td className="py-2 text-right font-mono text-xs">{(d.output_tokens / 1000).toFixed(1)}K</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Top models */}
          <Panel className="mt-6">
            <h3 className="font-display text-lg font-semibold text-white mb-4">{t("admin.topModels")}</h3>
            {stats.top_models.length === 0 ? (
              <p className="text-sm text-slate-500">{t("admin.noData")}</p>
            ) : (
              <div className="space-y-3">
                {stats.top_models.map((m) => {
                  const maxCount = Math.max(...stats.top_models.map((x) => x.count));
                  const pct = (m.count / maxCount) * 100;
                  return (
                    <div key={m.model} className="flex items-center gap-4">
                      <span className="w-40 truncate text-xs font-mono text-slate-300">{m.model}</span>
                      <div className="flex-1 h-5 border border-white/10 bg-night-950/50 relative overflow-hidden">
                        <div className="absolute inset-y-0 left-0 bg-signal-cyan/40" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-16 text-right text-xs text-slate-400">{m.count}次</span>
                      <span className="w-20 text-right font-mono text-xs text-amber-400/80">¥{m.cost.toFixed(4)}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
}
