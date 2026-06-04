import { ArrowRight, Database, FileText, RefreshCcw } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchKnowledgeBases, fetchTemplates } from "../api";
import { EmptyState, ErrorBanner, PageHeader, Panel, Stat } from "../components/ui";
import { formatDate, useAsyncData } from "../hooks";

export default function HomePage() {
  const templates = useAsyncData(fetchTemplates, []);
  const kbs = useAsyncData(fetchKnowledgeBases, []);

  const error = templates.error || kbs.error;
  const templateItems = templates.data ?? [];
  const kbItems = kbs.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Mission Control"
        title="把知识库、模板和生成任务放在同一个作业面板里。"
        description="独立 TypeScript 前端已对接 FastAPI：查看模板库存、知识库状态，进入模板识别或生成流程。深色界面采用高对比信息密度，避免泛化 AI 产品的圆润卡片感。"
        action={
          <Link
            to="/generate"
            className="inline-flex min-h-11 items-center gap-2 border border-signal-cyan bg-signal-cyan px-5 text-sm font-semibold text-night-950 shadow-glow transition hover:bg-white"
          >
            开始生成
            <ArrowRight size={17} />
          </Link>
        }
      />
      <ErrorBanner message={error} />

      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="模板数量" value={templates.loading ? "..." : templateItems.length} />
        <Stat label="知识库数量" value={kbs.loading ? "..." : kbItems.length} tone="lime" />
        <Stat label="后端目标" value="8000" tone="amber" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">已上传模板</p>
              <p className="text-sm text-slate-500">来自后端 `data/templates`。</p>
            </div>
            <FileText className="text-signal-cyan" size={24} />
          </div>
          {templateItems.length === 0 ? (
            <EmptyState title="暂无模板" body="进入模板分析页上传 .docx 模板。" />
          ) : (
            <div className="divide-y divide-white/10 border border-white/10">
              {templateItems.slice(0, 8).map((item) => (
                <div key={item.name} className="flex items-center justify-between gap-4 p-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{item.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{formatDate(item.mtime)}</p>
                  </div>
                  <span className="border border-signal-cyan/30 px-2 py-1 text-xs text-signal-cyan">
                    DOCX
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="font-display text-2xl font-semibold text-white">知识库列表</p>
              <p className="text-sm text-slate-500">用于检索证据和生成草稿。</p>
            </div>
            <Database className="text-signal-lime" size={24} />
          </div>
          {kbItems.length === 0 ? (
            <EmptyState title="暂无知识库" body="进入知识库管理页创建并导入资料。" />
          ) : (
            <div className="grid gap-3">
              {kbItems.map((kb) => (
                <Link
                  key={kb.slug}
                  to="/knowledge"
                  className="group border border-white/10 bg-night-850/70 p-4 transition hover:border-signal-lime/40"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">
                        {kb.label || kb.name || kb.slug}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{kb.slug}</p>
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
