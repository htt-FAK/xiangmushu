import { FileUp, ListChecks, Loader2, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import { analyzeTemplate } from "../api";
import { Button, EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { useI18n } from "../i18n";
import type { FillTask } from "../types";

function taskLabel(task: FillTask, index: number, fallback: string) {
  return task.target_chapter || `${fallback} ${index + 1}`;
}

export default function TemplateAnalysisPage() {
  const { t } = useI18n();
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
      if (!result.ok) throw new Error(result.error || t("template.analyze"));
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
        eyebrow={t("template.eyebrow")}
        title={t("template.title")}
        description={t("template.description")}
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <Panel>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">{t("template.upload")}</p>
              <p className="text-sm text-slate-500">{t("template.uploadHint")}</p>
            </div>
            <UploadCloud className="text-signal-cyan" size={25} />
          </div>

          <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center border border-dashed border-white/18 bg-night-950/60 px-5 py-8 text-center transition hover:border-signal-cyan/60">
            <FileUp className="mb-4 text-signal-cyan" size={34} />
            <span className="font-display text-xl font-semibold text-white">
              {file ? file.name : t("template.chooseFile")}
            </span>
            <span className="mt-2 text-sm text-slate-500">{t("template.fileHint")}</span>
            <input
              className="sr-only"
              type="file"
              accept=".docx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <Button className="mt-5 w-full" onClick={onAnalyze} disabled={!file || loading}>
            {loading ? <Loader2 className="animate-spin" size={17} /> : <ListChecks size={17} />}
            {loading ? t("template.analyzing") : t("template.analyze")}
          </Button>

          <div className="mt-5 grid grid-cols-3 gap-3">
            <Stat label={t("template.taskCount")} value={tasks.length} />
            <Stat label={t("template.wordTarget")} value={totalWords} tone="lime" />
            <Stat label={t("template.mode")} value={mode || "-"} tone="amber" />
          </div>
        </Panel>

        <Panel>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">{t("template.results")}</p>
              <p className="text-sm text-slate-500">{t("template.resultsHint")}</p>
            </div>
            <span className="border border-white/10 px-3 py-1 text-xs text-slate-400">
              {tasks.length} {t("template.items")}
            </span>
          </div>

          {tasks.length === 0 ? (
            <EmptyState title={t("template.empty")} body={t("template.emptyBody")} />
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
                        {taskLabel(task, index, t("template.taskFallback"))}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-400">
                        {task.prompt || t("template.noPrompt")}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <span className="border border-signal-cyan/30 px-2 py-1 text-xs text-signal-cyan">
                        {task.word_limit || 0} {t("template.wordUnit")}
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
