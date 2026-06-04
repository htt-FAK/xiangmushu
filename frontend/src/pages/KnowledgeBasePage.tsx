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
import type { KnowledgeBase, KnowledgeSourceStats, UploadResult } from "../types";

export default function KnowledgeBasePage() {
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [stats, setStats] = useState<KnowledgeSourceStats | null>(null);
  const [label, setLabel] = useState("");
  const [slug, setSlug] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploadResults, setUploadResults] = useState<UploadResult[]>([]);
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
      return;
    }
    setStats(await fetchKnowledgeSources(targetSlug));
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    refreshSources().catch((err: unknown) =>
      setError(err instanceof Error ? err.message : String(err)),
    );
  }, [selectedSlug]);

  async function onCreate() {
    if (!label.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await createKnowledgeBase(label.trim(), slug.trim());
      if (!result.ok) throw new Error(result.error || "创建知识库失败");
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
      if (!result.ok) throw new Error(result.error || "删除知识库失败");
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
        eyebrow="Knowledge Dock"
        title="导入资料，维护生成用知识库。"
        description="知识库管理页覆盖创建、上传、查看文档来源和删除来源。后端会负责解析文档、切块并写入向量库。"
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 xl:grid-cols-[390px_1fr]">
        <div className="space-y-6">
          <Panel>
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="font-display text-2xl font-semibold text-white">新建知识库</p>
                <p className="text-sm text-slate-500">Slug 留空时由后端生成。</p>
              </div>
              <Database className="text-signal-lime" size={24} />
            </div>
            <div className="space-y-4">
              <Field label="显示名称">
                <Input
                  value={label}
                  placeholder="例如：创新计划书资料库"
                  onChange={(event) => setLabel(event.target.value)}
                />
              </Field>
              <Field label="Slug">
                <Input
                  value={slug}
                  placeholder="project_kb"
                  onChange={(event) => setSlug(event.target.value)}
                />
              </Field>
              <Button className="w-full" onClick={onCreate} disabled={!label.trim() || loading}>
                {loading ? <Loader2 className="animate-spin" size={17} /> : <Plus size={17} />}
                创建知识库
              </Button>
            </div>
          </Panel>

          <Panel>
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="font-display text-2xl font-semibold text-white">上传文档</p>
                <p className="text-sm text-slate-500">PDF、DOCX、Markdown 等由后端解析。</p>
              </div>
              <UploadCloud className="text-signal-cyan" size={24} />
            </div>
            <div className="space-y-4">
              <Field label="目标知识库">
                <select
                  className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
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
              <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center border border-dashed border-white/18 bg-night-950/60 px-5 py-7 text-center transition hover:border-signal-cyan/60">
                <FileArchive className="mb-3 text-signal-cyan" size={31} />
                <span className="font-display text-lg font-semibold text-white">
                  {files.length ? `${files.length} 个文件已选择` : "选择资料文件"}
                </span>
                <span className="mt-2 text-xs text-slate-500">可多选，上传后自动入库</span>
                <input
                  className="sr-only"
                  type="file"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
              </label>
              <Button
                className="w-full"
                onClick={onUpload}
                disabled={!selectedSlug || files.length === 0 || loading}
              >
                {loading ? <Loader2 className="animate-spin" size={17} /> : <UploadCloud size={17} />}
                上传并入库
              </Button>
            </div>
          </Panel>
        </div>

        <Panel>
          <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">知识库状态</p>
              <p className="mt-1 text-sm text-slate-500">
                {selected ? `${selected.label || selected.name || selected.slug} / ${selected.slug}` : "未选择"}
              </p>
            </div>
            {selectedSlug && (
              <Button variant="danger" onClick={() => onDeleteKb(selectedSlug)} disabled={loading}>
                <Trash2 size={17} />
                删除知识库
              </Button>
            )}
          </div>

          <div className="mb-6 grid gap-3 md:grid-cols-3">
            <Stat label="知识库总数" value={items.length} />
            <Stat label="文档来源" value={stats?.source_count ?? 0} tone="lime" />
            <Stat label="Chunk 数" value={stats?.chunk_count ?? 0} tone="amber" />
          </div>

          {uploadResults.length > 0 && (
            <div className="mb-6 border border-white/10 bg-night-950/70 p-4">
              <p className="mb-3 font-display text-lg font-semibold text-white">最近上传</p>
              <div className="space-y-2">
                {uploadResults.map((result) => (
                  <div key={result.file} className="flex justify-between gap-4 text-sm">
                    <span className="truncate text-slate-300">{result.file}</span>
                    <span className={result.ok ? "text-signal-lime" : "text-signal-rose"}>
                      {result.ok ? `${result.chunks ?? 0} chunks` : result.error}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!stats || stats.sources.length === 0 ? (
            <EmptyState title="暂无入库文档" body="选择知识库并上传资料后，来源文件会显示在这里。" />
          ) : (
            <div className="divide-y divide-white/10 border border-white/10">
              {stats.sources.map((source) => (
                <div key={source} className="flex items-center justify-between gap-4 p-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{source}</p>
                    <p className="mt-1 text-xs text-slate-500">vector source</p>
                  </div>
                  <Button
                    variant="ghost"
                    onClick={() => onRemoveSource(source)}
                    disabled={loading}
                    aria-label={`删除 ${source}`}
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
