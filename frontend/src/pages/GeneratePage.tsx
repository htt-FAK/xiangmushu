import { Download, Loader2, Play, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { downloadUrl, fetchKnowledgeBases, fetchTemplates, streamGenerate } from "../api";
import { Button, EmptyState, ErrorBanner, Field, PageHeader, Panel, Stat } from "../components/ui";
import type { GenerateEvent, KnowledgeBase, TemplateItem } from "../types";

type OutputBlock = {
  chapter: string;
  text: string;
};

export default function GeneratePage() {
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [template, setTemplate] = useState("");
  const [slug, setSlug] = useState("");
  const [wordLimit, setWordLimit] = useState(300);
  const [topK, setTopK] = useState(4);
  const [maxDistance, setMaxDistance] = useState(1.25);
  const [enableWeb, setEnableWeb] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [currentTask, setCurrentTask] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [outputs, setOutputs] = useState<OutputBlock[]>([]);
  const [downloadPath, setDownloadPath] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    Promise.all([fetchTemplates(), fetchKnowledgeBases()])
      .then(([templateList, kbList]) => {
        setTemplates(templateList);
        setKbs(kbList);
        setTemplate((current) => current || templateList[0]?.name || "");
        setSlug((current) => current || kbList[0]?.slug || "");
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const percent = useMemo(() => {
    if (!progress.total) return 0;
    return Math.round((progress.done / progress.total) * 100);
  }, [progress]);

  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
  }

  async function start() {
    if (!template || !slug) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setError("");
    setOutputs([]);
    setDownloadPath("");
    setCurrentTask("");
    setProgress({ done: 0, total: 0 });

    const chapters: Record<number, string> = {};
    try {
      await streamGenerate(
        { slug, template, wordLimit, topK, maxDistance, enableWeb, useStream },
        (event: GenerateEvent) => {
          if (event.type === "task") {
            chapters[event.index] = event.chapter;
            setCurrentTask(event.chapter);
            setProgress((prev) => ({ done: prev.done, total: event.total }));
            setOutputs((prev) => {
              if (prev[event.index]) return prev;
              const next = [...prev];
              next[event.index] = { chapter: event.chapter, text: "" };
              return next;
            });
          }
          if (event.type === "chunk") {
            setOutputs((prev) => {
              const next = [...prev];
              const existing = next[event.index] ?? {
                chapter: chapters[event.index] || `任务 ${event.index + 1}`,
                text: "",
              };
              next[event.index] = { ...existing, text: existing.text + event.text };
              return next;
            });
          }
          if (event.type === "progress") {
            setProgress({ done: event.index + 1, total: event.total });
          }
          if (event.type === "done") {
            setDownloadPath(event.download);
            setCurrentTask("回填完成");
          }
          if (event.type === "error") {
            setError(event.error);
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Generation Bay"
        title="选择知识库和模板，启动流式生成。"
        description="生成页以任务进度为中心：参数在左侧，实时输出在右侧。完成后返回 Word 下载链接。"
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 xl:grid-cols-[390px_1fr]">
        <Panel>
          <div className="space-y-4">
            <Field label="知识库">
              <select
                className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
              >
                {kbs.map((kb) => (
                  <option key={kb.slug} value={kb.slug}>
                    {kb.label || kb.name || kb.slug}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="模板">
              <select
                className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
                value={template}
                onChange={(event) => setTemplate(event.target.value)}
              >
                {templates.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="默认字数">
              <input
                className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
                type="number"
                min={80}
                max={3000}
                value={wordLimit}
                onChange={(event) => setWordLimit(Number(event.target.value))}
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Top K">
                <input
                  className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value))}
                />
              </Field>
              <Field label="距离阈值">
                <input
                  className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
                  type="number"
                  step={0.05}
                  min={0.1}
                  max={3}
                  value={maxDistance}
                  onChange={(event) => setMaxDistance(Number(event.target.value))}
                />
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <label className="flex min-h-11 items-center justify-between border border-white/10 bg-night-950/70 px-3 text-sm text-slate-300">
                联网补充
                <input
                  type="checkbox"
                  checked={enableWeb}
                  onChange={(event) => setEnableWeb(event.target.checked)}
                />
              </label>
              <label className="flex min-h-11 items-center justify-between border border-white/10 bg-night-950/70 px-3 text-sm text-slate-300">
                流式输出
                <input
                  type="checkbox"
                  checked={useStream}
                  onChange={(event) => setUseStream(event.target.checked)}
                />
              </label>
            </div>

            <div className="flex gap-3">
              <Button className="flex-1" onClick={start} disabled={!template || !slug || running}>
                {running ? <Loader2 className="animate-spin" size={17} /> : <Play size={17} />}
                {running ? "生成中" : "开始生成"}
              </Button>
              <Button variant="ghost" onClick={stop} disabled={!running} aria-label="停止生成">
                <Square size={17} />
              </Button>
            </div>
          </div>
        </Panel>

        <Panel>
          <div className="mb-5 grid gap-3 md:grid-cols-3">
            <Stat label="进度" value={`${percent}%`} />
            <Stat label="完成任务" value={`${progress.done}/${progress.total || "-"}`} tone="lime" />
            <Stat label="当前任务" value={currentTask || "-"} tone="amber" />
          </div>

          <div className="mb-5 h-2 border border-white/10 bg-night-950">
            <div
              className="h-full bg-[linear-gradient(90deg,#36f2e6,#b8ff5e)] transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>

          {downloadPath && (
            <a
              className="mb-5 inline-flex min-h-10 items-center gap-2 border border-signal-lime bg-signal-lime px-4 text-sm font-semibold text-night-950"
              href={downloadUrl(downloadPath)}
            >
              <Download size={17} />
              下载已填写 Word
            </a>
          )}

          {outputs.length === 0 ? (
            <EmptyState title="等待生成输出" body="启动后会按模板任务展示流式文本。" />
          ) : (
            <div className="space-y-4">
              {outputs.map((block, index) => (
                <article key={`${block.chapter}-${index}`} className="border border-white/10 bg-night-950/70 p-4">
                  <p className="mb-3 font-display text-lg font-semibold text-signal-cyan">
                    {block.chapter || `任务 ${index + 1}`}
                  </p>
                  <pre className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">
                    {block.text || "等待模型输出..."}
                  </pre>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
