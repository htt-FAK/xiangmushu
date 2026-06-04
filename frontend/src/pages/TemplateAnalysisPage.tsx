import { FileUp, ListChecks, Loader2, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import { analyzeTemplate } from "../api";
import { Button, EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import type { FillTask } from "../types";

function taskLabel(task: FillTask, index: number) {
  return task.target_chapter || `填写任务 ${index + 1}`;
}

export default function TemplateAnalysisPage() {
  const [file, setFile] = useState<File | null>(null);
  const [tasks, setTasks] = useState<FillTask[]>([]);
  const [mode, setMode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const totalWords = useMemo(
    () => tasks.reduce((sum, task) => sum + Math.max(0, task.word_limit || 0), 0),
    [tasks],
  );

  async function onAnalyze() {
    if (!file) return;
    setLoading(true);
    setError("");
    setTasks([]);
    setMode("");
    try {
      const result = await analyzeTemplate(file);
      if (!result.ok) throw new Error(result.error || "模板分析失败");
      setTasks(result.tasks ?? []);
      setMode(result.mode ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Template Recon"
        title="上传 Word 模板，扫描可填写任务。"
        description="模板会保存到后端模板目录，并由 FastAPI 返回章节、提示词、字数和定位信息。锚点模板会走 anchor 模式，普通模板会进入推断模式。"
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <Panel>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">模板上传</p>
              <p className="text-sm text-slate-500">支持 .docx 文件。</p>
            </div>
            <UploadCloud className="text-signal-cyan" size={25} />
          </div>

          <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center border border-dashed border-white/18 bg-night-950/60 px-5 py-8 text-center transition hover:border-signal-cyan/60">
            <FileUp className="mb-4 text-signal-cyan" size={34} />
            <span className="font-display text-xl font-semibold text-white">
              {file ? file.name : "选择模板文件"}
            </span>
            <span className="mt-2 text-sm text-slate-500">
              文件会通过 /api/template/analyze 上传并分析
            </span>
            <input
              className="sr-only"
              type="file"
              accept=".docx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <Button className="mt-5 w-full" onClick={onAnalyze} disabled={!file || loading}>
            {loading ? <Loader2 className="animate-spin" size={17} /> : <ListChecks size={17} />}
            {loading ? "分析中" : "开始识别填写任务"}
          </Button>

          <div className="mt-5 grid grid-cols-3 gap-3">
            <Stat label="任务数" value={tasks.length} />
            <Stat label="目标字数" value={totalWords} tone="lime" />
            <Stat label="模式" value={mode || "-"} tone="amber" />
          </div>
        </Panel>

        <Panel>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">识别结果</p>
              <p className="text-sm text-slate-500">生成页会按这些任务逐段生成内容。</p>
            </div>
            <span className="border border-white/10 px-3 py-1 text-xs text-slate-400">
              {tasks.length} items
            </span>
          </div>

          {tasks.length === 0 ? (
            <EmptyState title="等待分析结果" body="上传模板并启动识别后，任务列表会显示在这里。" />
          ) : (
            <div className="space-y-3">
              {tasks.map((task, index) => (
                <article
                  key={`${task.target_chapter}-${index}`}
                  className="border border-white/10 bg-night-850/70 p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="font-display text-xl font-semibold text-white">
                        {taskLabel(task, index)}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-400">
                        {task.prompt || "未返回提示词"}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <span className="border border-signal-cyan/30 px-2 py-1 text-xs text-signal-cyan">
                        {task.word_limit || 0} 字
                      </span>
                      <span className="border border-white/10 px-2 py-1 text-xs text-slate-400">
                        {task.replace_mode || "replace"}
                      </span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
