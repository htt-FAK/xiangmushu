import { Download, FileText, Loader2, Play, ShieldCheck, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { downloadUrl, fetchKnowledgeBases, fetchTemplates, streamGenerate } from "../api";
import { Button, EmptyState, ErrorBanner, Field, PageHeader, Panel, Stat } from "../components/ui";
import type { GenerateEvent, KnowledgeBase, PostFillChecks, TemplateItem } from "../types";

type OutputBlock = {
  chapter: string;
  text: string;
  model?: string;
  tier?: string;
  kbHits?: number;
  evidenceRefs?: string[];
  auditVerdict?: string;
  auditIssues?: string[];
  revised?: boolean;
};

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex min-h-11 items-center justify-between border border-white/10 bg-night-950/70 px-3 text-sm text-slate-300">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {children}
    </select>
  );
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
}: {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  return (
    <input
      className="min-h-10 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
      type="number"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  );
}

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
  const [enableAudit, setEnableAudit] = useState(false);
  const [enableVisualAudit, setEnableVisualAudit] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [currentTask, setCurrentTask] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [outputs, setOutputs] = useState<OutputBlock[]>([]);
  const [downloadPath, setDownloadPath] = useState("");
  const [reportPath, setReportPath] = useState("");
  const [reportSummary, setReportSummary] = useState("");
  const [postFillChecks, setPostFillChecks] = useState<PostFillChecks | null>(null);
  const [visualScore, setVisualScore] = useState<number | null>(null);
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

  const checkHighlights = useMemo(() => {
    if (!postFillChecks) return [];
    return [
      ...(postFillChecks.leftover_placeholders ?? []).slice(0, 3).map((item) => `残留占位：${item}`),
      ...(postFillChecks.missing_chapters ?? []).slice(0, 3).map((item) => `章节缺失：${item}`),
      ...(postFillChecks.protected_issues ?? []).slice(0, 3),
    ];
  }, [postFillChecks]);

  function updateOutput(index: number, patch: Partial<OutputBlock>) {
    setOutputs((prev) => {
      const next = [...prev];
      const existing = next[index] ?? {
        chapter: `任务 ${index + 1}`,
        text: "",
        evidenceRefs: [],
        auditIssues: [],
      };
      next[index] = { ...existing, ...patch };
      return next;
    });
  }

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
    setReportPath("");
    setReportSummary("");
    setPostFillChecks(null);
    setVisualScore(null);
    setCurrentTask("");
    setProgress({ done: 0, total: 0 });

    const chapters: Record<number, string> = {};

    try {
      await streamGenerate(
        {
          slug,
          template,
          wordLimit,
          topK,
          maxDistance,
          enableWeb,
          useStream,
          enableAudit,
          enableVisualAudit,
        },
        (event: GenerateEvent) => {
          if (event.type === "task") {
            chapters[event.index] = event.chapter;
            setCurrentTask(event.chapter);
            setProgress((prev) => ({ done: prev.done, total: event.total }));
            updateOutput(event.index, { chapter: event.chapter });
            return;
          }

          if (event.type === "route") {
            updateOutput(event.index, {
              chapter: chapters[event.index] || `任务 ${event.index + 1}`,
              model: event.model,
              tier: event.tier,
              kbHits: event.kb_hits,
              evidenceRefs: event.evidence_refs ?? [],
            });
            return;
          }

          if (event.type === "chunk") {
            setOutputs((prev) => {
              const next = [...prev];
              const existing = next[event.index] ?? {
                chapter: chapters[event.index] || `任务 ${event.index + 1}`,
                text: "",
                evidenceRefs: [],
                auditIssues: [],
              };
              next[event.index] = { ...existing, text: `${existing.text}${event.text}` };
              return next;
            });
            return;
          }

          if (event.type === "audit") {
            updateOutput(event.index, {
              auditVerdict: event.verdict,
              auditIssues: event.issues,
              revised: event.revised,
            });
            return;
          }

          if (event.type === "progress") {
            setProgress({ done: event.index + 1, total: event.total });
            return;
          }

          if (event.type === "done") {
            setDownloadPath(event.download);
            setReportPath(event.report_download ?? "");
            setReportSummary(event.report_summary ?? "");
            setPostFillChecks(event.post_fill_checks ?? null);
            setVisualScore(event.visual_score ?? null);
            setCurrentTask("回填完成");
            return;
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
        title="选择知识库和模板，启动文档生成"
        description="左侧负责参数编排，右侧实时展示任务输出、检索路由、审核反馈和最终质量报告。"
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 xl:grid-cols-[390px_1fr]">
        <Panel>
          <div className="space-y-4">
            <Field label="知识库">
              <Select value={slug} onChange={setSlug}>
                {kbs.map((kb) => (
                  <option key={kb.slug} value={kb.slug}>
                    {kb.label || kb.name || kb.slug}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="模板">
              <Select value={template} onChange={setTemplate}>
                {templates.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="默认字数">
              <NumberInput value={wordLimit} onChange={setWordLimit} min={80} max={3000} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Top K">
                <NumberInput value={topK} onChange={setTopK} min={1} max={20} />
              </Field>
              <Field label="距离阈值">
                <NumberInput
                  value={maxDistance}
                  onChange={setMaxDistance}
                  min={0.1}
                  max={3}
                  step={0.05}
                />
              </Field>
            </div>

            <div className="grid gap-3">
              <ToggleRow label="联网补充" checked={enableWeb} onChange={setEnableWeb} />
              <ToggleRow label="流式输出" checked={useStream} onChange={setUseStream} />
              <ToggleRow label="内容审核" checked={enableAudit} onChange={setEnableAudit} />
              <ToggleRow
                label="视觉审核"
                checked={enableVisualAudit}
                onChange={setEnableVisualAudit}
              />
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
          <div className="mb-5 grid gap-3 md:grid-cols-4">
            <Stat label="进度" value={`${percent}%`} />
            <Stat label="完成任务" value={`${progress.done}/${progress.total || "-"}`} tone="lime" />
            <Stat label="当前任务" value={currentTask || "-"} tone="amber" />
            <Stat
              label="视觉评分"
              value={visualScore === null ? "-" : visualScore}
              tone={visualScore !== null && visualScore < 70 ? "rose" : "cyan"}
            />
          </div>

          <div className="mb-5 h-2 border border-white/10 bg-night-950">
            <div
              className="h-full bg-[linear-gradient(90deg,#36f2e6,#b8ff5e)] transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>

          {(downloadPath || reportPath) && (
            <div className="mb-5 flex flex-wrap gap-3">
              {downloadPath && (
                <a
                  className="inline-flex min-h-10 items-center gap-2 border border-signal-lime bg-signal-lime px-4 text-sm font-semibold text-night-950"
                  href={downloadUrl(downloadPath)}
                >
                  <Download size={17} />
                  下载最终文档
                </a>
              )}
              {reportPath && (
                <a
                  className="inline-flex min-h-10 items-center gap-2 border border-white/10 bg-white/[0.055] px-4 text-sm font-semibold text-slate-100"
                  href={downloadUrl(reportPath)}
                >
                  <FileText size={17} />
                  下载质量报告
                </a>
              )}
            </div>
          )}

          {(reportSummary || postFillChecks) && (
            <section className="mb-5 border border-white/10 bg-night-950/60 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-signal-cyan">
                <ShieldCheck size={16} />
                <span>生成验收</span>
              </div>
              {reportSummary && <p className="mt-3 text-sm text-slate-300">{reportSummary}</p>}
              {postFillChecks && (
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div className="border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">校验结果</p>
                    <p className="mt-2 text-white">{postFillChecks.ok ? "通过" : "需要复核"}</p>
                    <p className="mt-2 text-xs text-slate-400">
                      模板词数 {postFillChecks.template_words ?? "-"} / 输出词数{" "}
                      {postFillChecks.output_words ?? "-"}
                    </p>
                  </div>
                  <div className="border border-white/10 bg-night-900/70 p-3 text-sm text-slate-300">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">结构对比</p>
                    <p className="mt-2 text-white">
                      模板表格 {postFillChecks.template_tables ?? "-"} / 输出表格{" "}
                      {postFillChecks.output_tables ?? "-"}
                    </p>
                    <p className="mt-2 text-xs text-slate-400">
                      封面保护 {postFillChecks.cover_modified ? "异常" : "正常"}，评分表保护{" "}
                      {postFillChecks.rating_table_modified ? "异常" : "正常"}
                    </p>
                  </div>
                </div>
              )}
              {checkHighlights.length > 0 && (
                <div className="mt-3 space-y-2">
                  {checkHighlights.map((item) => (
                    <div
                      key={item}
                      className="border border-signal-amber/30 bg-signal-amber/10 px-3 py-2 text-sm text-amber-100"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {outputs.length === 0 ? (
            <EmptyState title="等待生成输出" body="启动后会按模板任务实时展示生成内容和质量信号。" />
          ) : (
            <div className="space-y-4">
              {outputs.map((block, index) => (
                <article key={`${block.chapter}-${index}`} className="border border-white/10 bg-night-950/70 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <p className="font-display text-lg font-semibold text-signal-cyan">
                      {block.chapter || `任务 ${index + 1}`}
                    </p>
                    <div className="flex flex-wrap gap-2 text-xs text-slate-300">
                      {block.tier && (
                        <span className="border border-white/10 bg-night-900/70 px-2 py-1">
                          route: {block.tier}
                        </span>
                      )}
                      {block.model && (
                        <span className="border border-white/10 bg-night-900/70 px-2 py-1">
                          model: {block.model}
                        </span>
                      )}
                      {typeof block.kbHits === "number" && (
                        <span className="border border-white/10 bg-night-900/70 px-2 py-1">
                          kb hits: {block.kbHits}
                        </span>
                      )}
                    </div>
                  </div>

                  {block.evidenceRefs && block.evidenceRefs.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {block.evidenceRefs.slice(0, 5).map((item) => (
                        <span
                          key={item}
                          className="border border-signal-cyan/20 bg-signal-cyan/10 px-2 py-1 text-xs text-cyan-100"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  )}

                  {block.auditIssues && block.auditIssues.length > 0 && (
                    <div className="mt-3 border border-signal-amber/30 bg-signal-amber/10 p-3 text-sm text-amber-100">
                      <p className="font-semibold">
                        审核结果：{block.auditVerdict || "issue"}
                        {block.revised ? "，已触发修订" : ""}
                      </p>
                      <div className="mt-2 space-y-1">
                        {block.auditIssues.slice(0, 5).map((issue) => (
                          <p key={issue}>{issue}</p>
                        ))}
                      </div>
                    </div>
                  )}

                  <pre className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">
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
