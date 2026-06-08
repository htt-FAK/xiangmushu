import { ArrowRight, Database, FileText, RefreshCcw } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchKnowledgeBases, fetchTemplates } from "../api";
import { EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { formatDate, useAsyncData } from "../hooks";
import { useI18n } from "../i18n";

export default function HomePage() {
  const { t } = useI18n();
  const templates = useAsyncData(fetchTemplates, []);
  const kbs = useAsyncData(fetchKnowledgeBases, []);

  const error = templates.error || kbs.error;
  const templateItems = templates.data ?? [];
  const kbItems = kbs.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow={t("home.eyebrow")}
        title={t("home.title")}
        description={t("home.description")}
        action={
          <Link
            to="/generate"
            className="inline-flex min-h-12 w-full items-center justify-center gap-2 border border-signal-cyan bg-signal-cyan px-5 text-sm font-bold text-night-950 shadow-glow transition hover:bg-white sm:min-h-11 sm:w-auto sm:font-semibold"
          >
            {t("home.start")}
            <ArrowRight size={17} />
          </Link>
        }
      />
      <ErrorBanner message={error} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4">
        <Stat label={t("home.templateCount")} value={templates.loading ? "..." : templateItems.length} />
        <Stat label={t("home.knowledgeCount")} value={kbs.loading ? "..." : kbItems.length} tone="lime" />
        <Stat className="col-span-2 md:col-span-1" label={t("home.backendPort")} value="8502" tone="amber" />
      </div>

      <div className="mt-5 grid gap-5 md:mt-6 md:gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel>
          <div className="mb-3 flex items-start justify-between gap-4 md:mb-4">
            <div className="min-w-0">
              <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("home.uploadedTemplates")}</p>
              <p className="mt-0.5 text-xs text-slate-500 md:text-sm">{t("home.templateSource")}</p>
            </div>
            <FileText className="shrink-0 text-signal-cyan" size={22} />
          </div>
          {templateItems.length === 0 ? (
            <EmptyState title={t("home.noTemplates")} body={t("home.noTemplatesBody")} />
          ) : (
            <div className="divide-y divide-white/10 border border-white/10 bg-night-950/35">
              {templateItems.slice(0, 8).map((item) => (
                <div key={item.name} className="flex items-center justify-between gap-3 px-3.5 py-3 md:p-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{item.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{formatDate(item.mtime)}</p>
                  </div>
                  <span className="shrink-0 border border-signal-cyan/30 bg-signal-cyan/10 px-2 py-1 text-[11px] font-semibold text-signal-cyan">
                    DOCX
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel>
          <div className="mb-3 flex items-start justify-between gap-4 md:mb-4">
            <div className="min-w-0">
              <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("home.knowledgeList")}</p>
              <p className="mt-0.5 text-xs text-slate-500 md:text-sm">{t("home.knowledgeBody")}</p>
            </div>
            <Database className="shrink-0 text-signal-lime" size={22} />
          </div>
          {kbItems.length === 0 ? (
            <EmptyState title={t("home.noKnowledge")} body={t("home.noKnowledgeBody")} />
          ) : (
            <div className="grid gap-2.5 md:gap-3">
              {kbItems.map((kb) => (
                <Link
                  key={kb.slug}
                  to="/knowledge"
                  className="group border border-white/10 bg-night-850/70 px-3.5 py-3 transition hover:border-signal-lime/40 hover:bg-night-800/70 md:p-4"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">
                        {kb.label || kb.name || kb.slug}
                      </p>
                      <p className="mt-1 truncate text-xs text-slate-500">{kb.slug}</p>
                    </div>
                    <RefreshCcw
                      className="text-slate-600 transition group-hover:text-signal-lime"
                      size={17}
                    />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
