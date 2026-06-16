import { Database, FileArchive, Loader2, Plus, Trash2, UploadCloud } from "lucide-react";
import { useEffect, useState } from "react";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  fetchKnowledgeBases,
  fetchKnowledgeSources,
  removeKnowledgeSource,
  uploadKnowledgeDocuments,
} from "../api";
import {
  Button,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  Panel,
  Stat,
} from "../components/ui";
import { useI18n } from "../i18n";
import type { KnowledgeBase, KnowledgeSourceStats, UploadResult } from "../types";
import { useWorkflow } from "../workflow";

export default function KnowledgeBasePage() {
  const { t } = useI18n();
  const { state: workflowState, setKnowledgeState } = useWorkflow();
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [selectedSlug, setSelectedSlug] = useState(workflowState.knowledge.selectedSlug);
  const [stats, setStats] = useState<KnowledgeSourceStats | null>(workflowState.knowledge.stats);
  const [label, setLabel] = useState("");
  const [slug, setSlug] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploadResults, setUploadResults] = useState<UploadResult[]>(workflowState.knowledge.uploadResults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    const list = await fetchKnowledgeBases();
    setItems(list);
    setSelectedSlug((current) => current || list[0]?.slug || "");
  }

  async function refreshSources(targetSlug = selectedSlug) {
    if (!targetSlug) {
      setStats(null);
      setKnowledgeState({ stats: null });
      return;
    }
    const nextStats = await fetchKnowledgeSources(targetSlug);
    setStats(nextStats);
    setKnowledgeState({ stats: nextStats });
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    refreshSources().catch((err: unknown) =>
      setError(err instanceof Error ? err.message : String(err)),
    );
  }, [selectedSlug]);

  useEffect(() => {
    setKnowledgeState({ selectedSlug, uploadResults, stats });
  }, [selectedSlug, setKnowledgeState, stats, uploadResults]);

  async function onCreate() {
    if (!label.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await createKnowledgeBase(label.trim(), slug.trim());
      if (!result.ok) throw new Error(result.error || t("knowledge.createError"));
      setLabel("");
      setSlug("");
      await refresh();
      if (result.slug) setSelectedSlug(result.slug);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function onUpload() {
    if (!selectedSlug || files.length === 0) return;
    setLoading(true);
    setError("");
    setUploadResults([]);
    try {
      const results = await uploadKnowledgeDocuments(selectedSlug, files);
      setUploadResults(results);
      setFiles([]);
      await refreshSources(selectedSlug);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function onRemoveSource(source: string) {
    if (!selectedSlug) return;
    setLoading(true);
    setError("");
    try {
      await removeKnowledgeSource(selectedSlug, source);
      await refreshSources(selectedSlug);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function onDeleteKb(targetSlug: string) {
    setLoading(true);
    setError("");
    try {
      const result = await deleteKnowledgeBase(targetSlug);
      if (!result.ok) throw new Error(result.error || t("knowledge.deleteError"));
      setSelectedSlug("");
      setStats(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const selected = items.find((item) => item.slug === selectedSlug);

  return (
    <>
      <PageHeader
        eyebrow={t("knowledge.eyebrow")}
        title={t("knowledge.title")}
        description={t("knowledge.description")}
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 xl:grid-cols-[390px_minmax(0,1fr)]">
        <div className="space-y-6">
          <Panel>
            <div className="mb-4 flex items-start justify-between gap-4 md:mb-5">
              <div className="min-w-0">
                <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("knowledge.create")}</p>
                <p className="mt-0.5 text-xs text-slate-500 md:text-sm">{t("knowledge.createHint")}</p>
              </div>
              <Database className="shrink-0 text-signal-lime" size={22} />
            </div>
            <div className="space-y-3.5 md:space-y-4">
              <Field label={t("knowledge.label")}>
                <Input
                  value={label}
                  placeholder={t("knowledge.labelPlaceholder")}
                  onChange={(event) => setLabel(event.target.value)}
                />
              </Field>
              <Field label="标识符 (Slug)">
                <Input
                  value={slug}
                  placeholder="project_kb"
                  onChange={(event) => setSlug(event.target.value)}
                />
              </Field>
              <Button className="min-h-12 w-full font-bold" onClick={onCreate} disabled={!label.trim() || loading}>
                {loading ? <Loader2 className="animate-spin" size={17} /> : <Plus size={17} />}
                {t("knowledge.createButton")}
              </Button>
            </div>
          </Panel>

          <Panel>
            <div className="mb-4 flex items-start justify-between gap-4 md:mb-5">
              <div className="min-w-0">
                <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("knowledge.upload")}</p>
                <p className="mt-0.5 text-xs text-slate-500 md:text-sm">{t("knowledge.uploadHint")}</p>
              </div>
              <UploadCloud className="shrink-0 text-signal-cyan" size={22} />
            </div>
            <div className="space-y-3.5 md:space-y-4">
              <Field label={t("knowledge.target")}>
                <select
                  className="min-h-12 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none transition focus:border-signal-cyan/70"
                  value={selectedSlug}
                  onChange={(event) => setSelectedSlug(event.target.value)}
                >
                  {items.map((item) => (
                    <option key={item.slug} value={item.slug}>
                      {item.label || item.name || item.slug}
                    </option>
                  ))}
                </select>
              </Field>
              <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center border border-dashed border-white/18 bg-night-950/60 px-4 py-5 text-center transition hover:border-signal-cyan/60 hover:bg-signal-cyan/5 md:min-h-36 md:px-5 md:py-7">
                <FileArchive className="mb-2 text-signal-cyan md:mb-3" size={28} />
                <span className="font-display text-base font-semibold text-white md:text-lg">
                  {files.length ? `${files.length} ${t("knowledge.filesSelected")}` : t("knowledge.chooseFiles")}
                </span>
                <span className="mt-2 text-xs text-slate-500">{t("knowledge.multiHint")}</span>
                <input
                  className="sr-only"
                  type="file"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
              </label>
              <Button
                className="min-h-12 w-full font-bold"
                onClick={onUpload}
                disabled={!selectedSlug || files.length === 0 || loading}
              >
                {loading ? <Loader2 className="animate-spin" size={17} /> : <UploadCloud size={17} />}
                {t("knowledge.uploadButton")}
              </Button>
            </div>
          </Panel>
        </div>

        <Panel className="min-w-0">
          <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="min-w-0">
              <p className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("knowledge.status")}</p>
              <p className="mt-1 break-words text-sm text-slate-500">
                {selected ? `${selected.label || selected.name || selected.slug} / ${selected.slug}` : t("knowledge.noneSelected")}
              </p>
            </div>
            {selectedSlug && (
              <Button className="min-h-12 w-full md:min-h-11 md:w-auto" variant="danger" onClick={() => onDeleteKb(selectedSlug)} disabled={loading}>
                <Trash2 size={17} />
                {t("knowledge.delete")}
              </Button>
            )}
          </div>

          <div className="mb-5 grid grid-cols-2 gap-3 md:mb-6 md:grid-cols-3">
            <Stat label={t("knowledge.total")} value={items.length} />
            <Stat label={t("knowledge.sources")} value={stats?.source_count ?? 0} tone="lime" />
            <Stat className="col-span-2 md:col-span-1" label={t("knowledge.chunkCount")} value={stats?.chunk_count ?? 0} tone="amber" />
          </div>

          {uploadResults.length > 0 && (
            <div className="mb-6 border border-white/10 bg-night-950/70 p-4">
              <p className="mb-3 font-display text-lg font-semibold text-white">{t("knowledge.recentUpload")}</p>
              <div className="space-y-2">
                {uploadResults.map((result) => (
                  <div key={result.file} className="grid gap-1 text-sm sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-4">
                    <span className="min-w-0 break-all text-slate-300">{result.file}</span>
                    <span className={result.ok ? "text-signal-lime" : "break-words text-signal-rose"}>
                      {result.ok ? `${result.chunks ?? 0} 个切片` : result.error}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!stats || stats.sources.length === 0 ? (
            <EmptyState title={t("knowledge.empty")} body={t("knowledge.emptyBody")} />
          ) : (
            <div className="grid gap-2.5 md:gap-3">
              {stats.sources.map((source) => (
                <div key={source} className="flex items-center justify-between gap-3 border border-white/10 bg-night-850/70 px-3.5 py-3 transition hover:border-signal-cyan/30 hover:bg-night-800/70 md:p-4">
                  <div className="min-w-0">
                    <p className="break-all text-sm font-semibold text-white">{source}</p>
                    <p className="mt-1 text-xs font-medium uppercase tracking-[0.12em] text-slate-500">vector source</p>
                  </div>
                  <Button
                    className="min-h-11 w-11 shrink-0 px-0"
                    variant="ghost"
                    onClick={() => onRemoveSource(source)}
                    disabled={loading}
                    aria-label={`${t("knowledge.delete")} ${source}`}
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
