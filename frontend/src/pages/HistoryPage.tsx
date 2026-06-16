import {
  AlertTriangle,
  Archive,
  BarChart3,
  Download,
  FileText,
  Loader2,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchHistoryArticles } from "../api";
import { UsageChart } from "../components/UsageChart";
import { Button, Input, Panel, Stat } from "../components/ui";
import { articleTotalTokens, formatHistoryCost, formatTokenCount } from "../historyData";
import { useI18n } from "../i18n";
import type { HistoryArticleStatus, HistoryArticlesResponse } from "../types";
import { clsx } from "../utils";

const statusOrder: Array<HistoryArticleStatus | "all"> = ["all", "completed", "review", "failed"];

const emptyHistoryResponse: HistoryArticlesResponse = {
  articles: [],
  summary: {
    count: 0,
    inputTokens: 0,
    outputTokens: 0,
    totalTokens: 0,
    costCny: 0,
    modelUsage: [],
  },
  availability: {
    available: false,
    source: "unavailable",
  },
};

function statusTone(status: HistoryArticleStatus) {
  if (status === "completed") return "border-signal-lime/40 bg-signal-lime/10 text-signal-lime";
  if (status === "review") return "border-signal-amber/40 bg-signal-amber/10 text-amber-100";
  return "border-signal-rose/40 bg-signal-rose/10 text-signal-rose";
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

export default function HistoryPage() {
  const { t } = useI18n();
  const [response, setResponse] = useState<HistoryArticlesResponse>(emptyHistoryResponse);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<HistoryArticleStatus | "all">("all");
  const [selectedId, setSelectedId] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetchHistoryArticles({ query, status })
      .then((next) => {
        if (!alive) return;
        setResponse(next);
        setError("");
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : String(err));
        setResponse({
          ...emptyHistoryResponse,
          availability: {
            available: false,
            source: "unavailable",
            warning: err instanceof Error ? err.message : String(err),
          },
        });
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [query, status]);

  const articles = response.articles;
  const summary = response.summary;
  const availability = response.availability;

  useEffect(() => {
    if (!articles.length) {
      setSelectedId("");
      return;
    }
    if (!articles.some((item) => item.id === selectedId)) {
      setSelectedId(articles[0].id);
    }
  }, [articles, selectedId]);

  const selected = articles.find((item) => item.id === selectedId) ?? articles[0];
  const hasFilters = Boolean(query.trim()) || status !== "all";
  const emptyMessage = hasFilters ? "没有符合当前筛选条件的历史记录。" : t("history.empty");

  return (
    <div className="space-y-4 md:space-y-5">
      <header className="flex flex-col gap-4 border-b border-white/10 pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="mb-1 font-display text-xs font-semibold uppercase tracking-[0.2em] text-signal-cyan">
            {t("history.eyebrow")}
          </p>
          <h1 className="break-words font-display text-2xl font-semibold text-white md:text-3xl">
            {t("history.title")}
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{t("history.description")}</p>
        </div>
        <div
          className={clsx(
            "flex items-center gap-2 border px-3 py-2 text-xs font-semibold",
            availability.available
              ? "border-signal-cyan/25 bg-signal-cyan/10 text-signal-cyan"
              : "border-signal-amber/30 bg-signal-amber/10 text-amber-100",
          )}
        >
          <Archive size={15} />
          {availability.available ? t("history.backendBadge") : "后端服务未连接"}
        </div>
      </header>

      {availability.warning ? (
        <div className="flex items-start gap-3 border border-signal-amber/30 bg-signal-amber/10 px-4 py-3 text-sm text-amber-100">
          <AlertTriangle className="mt-0.5 shrink-0" size={18} />
          <p className="break-words">{availability.warning}</p>
        </div>
      ) : null}

      {error ? (
        <div className="border border-signal-rose/40 bg-signal-rose/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label={t("history.totalArticles")} value={summary.count} />
        <Stat label={t("history.inputTokens")} value={formatTokenCount(summary.inputTokens)} tone="lime" />
        <Stat label={t("history.outputTokens")} value={formatTokenCount(summary.outputTokens)} tone="amber" />
        <Stat label={t("history.totalTokens")} value={formatTokenCount(summary.totalTokens)} tone="cyan" />
        <Stat label={t("history.totalCost")} value={formatHistoryCost(summary.costCny)} tone="lime" />
      </div>

      <div className="grid min-h-0 gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
        <Panel className="min-w-0">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <p className="font-display text-xl font-semibold text-white">{t("history.records")}</p>
              <p className="mt-1 text-xs text-slate-500">{t("history.recordsHint")}</p>
            </div>
            <FileText className="text-signal-cyan" size={21} />
          </div>

          <div className="mb-3 grid gap-2">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" size={16} />
              <Input
                className="pl-9"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("history.searchPlaceholder")}
              />
            </label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2">
              {statusOrder.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setStatus(item)}
                  className={clsx(
                    "min-h-10 border px-2 text-xs font-semibold transition",
                    status === item
                      ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
                      : "border-white/10 bg-night-950/70 text-slate-400 hover:border-white/25 hover:text-white",
                  )}
                >
                  {t(`history.status.${item}`)}
                </button>
              ))}
            </div>
          </div>

          <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
            {loading ? (
              <div className="flex min-h-28 items-center justify-center text-slate-500">
                <Loader2 className="mr-2 animate-spin" size={16} />
                正在加载历史记录...
              </div>
            ) : !availability.available ? (
              <div className="border border-dashed border-signal-amber/30 bg-night-950/60 p-5 text-sm text-slate-300">
                当前无法获取历史记录。
              </div>
            ) : articles.length === 0 ? (
              <div className="border border-dashed border-white/15 bg-night-950/60 p-5 text-sm text-slate-500">
                {emptyMessage}
              </div>
            ) : (
              articles.map((article) => {
                const active = article.id === selected?.id;
                return (
                  <button
                    key={article.id}
                    type="button"
                    onClick={() => setSelectedId(article.id)}
                    className={clsx(
                      "w-full min-w-0 border p-3 text-left transition active:scale-[0.99]",
                      active
                        ? "border-signal-cyan/60 bg-signal-cyan/10"
                        : "border-white/10 bg-night-950/65 hover:border-white/25",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-semibold text-white">{article.title}</p>
                        <p className="mt-1 truncate text-xs text-slate-500">{article.template}</p>
                      </div>
                      <span className={clsx("shrink-0 border px-2 py-1 text-[11px] font-semibold", statusTone(article.status))}>
                        {t(`history.status.${article.status}`)}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                      <span>{formatDate(article.createdAt)}</span>
                      <span>{formatTokenCount(articleTotalTokens(article))} 字符 (Tokens)</span>
                      <span>{formatHistoryCost(article.costCny)}</span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </Panel>

        <div className="min-w-0 space-y-4">
          <Panel className="min-w-0">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <p className="font-display text-xl font-semibold text-white md:text-2xl">
                  {selected?.title ?? t("history.noSelection")}
                </p>
                {selected ? (
                  <p className="mt-1 break-words text-sm text-slate-400">
                    {selected.template} / {selected.knowledgeBase}
                  </p>
                ) : (
                  <p className="mt-1 text-sm text-slate-500">
                    {loading
                      ? "正在加载历史数据..."
                      : availability.available
                        ? emptyMessage
                        : "暂无可选的历史记录。"}
                  </p>
                )}
              </div>
              {selected ? (
                <span className={clsx("w-fit border px-2.5 py-1 text-xs font-semibold", statusTone(selected.status))}>
                  {t(`history.status.${selected.status}`)}
                </span>
              ) : null}
            </div>

            {selected ? (
              <>
                <div className="grid gap-3 md:grid-cols-4">
                  <Stat label={t("history.inputTokens")} value={formatTokenCount(selected.inputTokens)} />
                  <Stat label={t("history.outputTokens")} value={formatTokenCount(selected.outputTokens)} tone="lime" />
                  <Stat label={t("history.totalTokens")} value={formatTokenCount(articleTotalTokens(selected))} tone="amber" />
                  <Stat label={t("history.cost")} value={formatHistoryCost(selected.costCny)} tone="lime" />
                </div>

                <div className="mt-4 flex flex-wrap gap-3">
                  <Button
                    className="min-h-11"
                    disabled={!selected.documentUrl}
                    onClick={() => selected.documentUrl && window.open(selected.documentUrl, "_blank")}
                  >
                    <Download size={17} />
                    {t("history.downloadDoc")}
                  </Button>
                  <Button
                    className="min-h-11"
                    variant="ghost"
                    disabled={!selected.reportUrl}
                    onClick={() => selected.reportUrl && window.open(selected.reportUrl, "_blank")}
                  >
                    <FileText size={17} />
                    {t("history.downloadReport")}
                  </Button>
                </div>
              </>
            ) : null}
          </Panel>

          <div className="grid gap-4 2xl:grid-cols-2">
            <Panel className="min-w-0">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center border border-signal-cyan/30 bg-signal-cyan/10 text-signal-cyan">
                  <BarChart3 size={18} />
                </div>
                <div>
                  <p className="font-display text-lg font-semibold text-white">{t("history.aggregateUsage")}</p>
                  <p className="text-xs text-slate-500">{t("history.aggregateUsageHint")}</p>
                </div>
              </div>
              <UsageChart usage={summary.modelUsage} title={t("history.modelUsage")} />
            </Panel>

            <Panel className="min-w-0">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center border border-signal-lime/30 bg-signal-lime/10 text-signal-lime">
                  <SlidersHorizontal size={18} />
                </div>
                <div>
                  <p className="font-display text-lg font-semibold text-white">{t("history.articleUsage")}</p>
                  <p className="text-xs text-slate-500">{t("history.articleUsageHint")}</p>
                </div>
              </div>
              <UsageChart usage={selected?.modelUsage ?? []} title={selected?.title ?? t("history.modelUsage")} />
            </Panel>
          </div>
        </div>
      </div>
    </div>
  );
}
