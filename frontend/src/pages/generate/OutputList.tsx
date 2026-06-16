import { lazy, Suspense } from "react";
import { BookOpen, Loader2, MessageSquareText, RotateCcw } from "lucide-react";
import { Button, DetailOverlay, EmptyState, Panel } from "../../components/ui";
import { useI18n } from "../../i18n";
import { SectionTitle } from "./ui";
import type { OutputBlock } from "./useGenerationSession";

const LazyOutputBlock = lazy(() => import("../../components/OutputBlock").then((m) => ({ default: m.OutputBlock })));

function OutputBlocks({
  outputs,
  taskName,
  regeneratingIndex,
  running,
  currentTask,
  busy,
  onRegenerate,
  actionsEnabled,
  preview = false,
}: {
  outputs: OutputBlock[];
  taskName: (index: number) => string;
  regeneratingIndex: number | null;
  running: boolean;
  currentTask: string;
  busy: boolean;
  onRegenerate: (index: number) => void;
  actionsEnabled: boolean;
  preview?: boolean;
}) {
  const { t } = useI18n();
  return (
    <>
      {outputs.map((block, index) => (
        <Suspense
          key={`${block.chapter}-${index}`}
          fallback={<div className="min-h-24 border border-white/10 bg-night-950/70 p-4 text-sm text-slate-500">Loading...</div>}
        >
          <LazyOutputBlock
            block={block}
            fallbackName={taskName(index)}
            waitingText={t("generate.waitingModel")}
            auditResultLabel={t("generate.auditResult")}
            revisedLabel={t("generate.revised")}
            routeLabel={t("generate.routeLabel")}
            modelLabel={t("generate.modelLabel")}
            kbHitsLabel={t("generate.kbHitsLabel")}
            auditFallbackLabel={t("generate.auditIssueFallback")}
            busy={regeneratingIndex === index || (running && block.chapter === currentTask)}
            busyLabel={t("generate.regenerating")}
            preview={preview}
            previewClassName={preview ? "shadow-none" : undefined}
            action={
              actionsEnabled ? (
                <Button
                  variant="ghost"
                  className="min-h-10 gap-2 px-3 text-xs"
                  disabled={busy}
                  onClick={() => onRegenerate(index)}
                >
                  {regeneratingIndex === index ? <Loader2 className="animate-spin" size={15} /> : <RotateCcw size={15} />}
                  {regeneratingIndex === index ? t("generate.regenerating") : t("generate.regenerateChapter")}
                </Button>
              ) : undefined
            }
          />
        </Suspense>
      ))}
    </>
  );
}

export function OutputList({
  outputs,
  taskName,
  regeneratingIndex,
  running,
  currentTask,
  busy,
  progress,
  onRegenerate,
  traceOpen,
  onOpenTrace,
  onCloseTrace,
}: {
  outputs: OutputBlock[];
  taskName: (index: number) => string;
  regeneratingIndex: number | null;
  running: boolean;
  currentTask: string;
  busy: boolean;
  progress: { done: number; total: number };
  onRegenerate: (index: number) => void;
  traceOpen: boolean;
  onOpenTrace: () => void;
  onCloseTrace: () => void;
}) {
  const { t } = useI18n();
  const blocksProps = { outputs, taskName, regeneratingIndex, running, currentTask, busy, onRegenerate };

  return (
    <>
      <Panel className="min-w-0">
        <SectionTitle icon={<BookOpen size={18} />} title={t("generate.outputTitle")} hint={t("generate.outputHint")} />
        {outputs.length === 0 ? (
          <EmptyState title={t("generate.waitingOutput")} body={t("generate.waitingOutputBody")} />
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 border border-white/10 bg-night-900/60 px-4 py-3 text-sm text-slate-200 md:px-5">
              <span className="min-w-0 break-words font-semibold">
                {running
                  ? t("generate.streamingStatus").replace("{0}", String(progress.done)).replace("{1}", String(progress.total || 0))
                  : t("generate.completedSummary").replace("{0}", String(outputs.length))}
              </span>
              <Button
                variant="ghost"
                className="min-h-10 gap-2 border border-white/10 bg-white/[0.035] px-4 text-xs font-semibold text-slate-300 hover:border-white/25 hover:text-white"
                onClick={onOpenTrace}
              >
                <MessageSquareText size={15} />
                {running ? t("generate.viewLiveProgress") : t("generate.viewFullTrace")}
              </Button>
            </div>
            <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1">
              <OutputBlocks {...blocksProps} actionsEnabled={false} preview={true} />
            </div>
          </div>
        )}
      </Panel>

      {traceOpen && (
        <DetailOverlay
          title={t("generate.traceTitle")}
          subtitle={running ? t("generate.viewLiveProgress") : t("generate.viewFullTrace")}
          icon={<MessageSquareText size={18} />}
          onClose={onCloseTrace}
        >
          <OutputBlocks {...blocksProps} actionsEnabled={true} />
        </DetailOverlay>
      )}
    </>
  );
}
