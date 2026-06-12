import type { HistoryArticle, HistoryArticleStatus, HistoryModelUsage } from "./types";

export const mockHistoryArticles: HistoryArticle[] = [
  {
    id: "hist-20260612-agent-practice",
    title: "智能体应用开发实践",
    template: "智能体应用开发实践.docx",
    knowledgeBase: "项目 / kb",
    createdAt: "2026-06-12T15:38:08+08:00",
    status: "review",
    documentUrl: "/api/download/智能体应用开发实践_u5_20260612_153807.docx",
    reportUrl: "/api/download/智能体应用开发实践_u5_20260612_153807_report.md",
    inputTokens: 59097,
    outputTokens: 8090,
    costCny: 0.1667,
    modelUsage: [
      { model: "qwen3.7-max", inputTokens: 42120, outputTokens: 6420, costCny: 0.1294 },
      { model: "qwen3.7-plus", inputTokens: 11820, outputTokens: 980, costCny: 0.0251 },
      { model: "qwen3.6-flash", inputTokens: 5157, outputTokens: 690, costCny: 0.0122 },
    ],
  },
  {
    id: "hist-20260611-innovation-plan",
    title: "大学生创新创业训练计划书",
    template: "2024级广东理工学院创新计划书参考模板.docx",
    knowledgeBase: "创新计划资料库",
    createdAt: "2026-06-11T22:14:32+08:00",
    status: "completed",
    documentUrl: "/api/download/创新计划书_u5_20260611_221432.docx",
    reportUrl: "/api/download/创新计划书_u5_20260611_221432_report.md",
    inputTokens: 38240,
    outputTokens: 12480,
    costCny: 0.1189,
    modelUsage: [
      { model: "qwen3.7-plus", inputTokens: 24100, outputTokens: 8400, costCny: 0.0813 },
      { model: "qwen3.6-flash", inputTokens: 9140, outputTokens: 2110, costCny: 0.0184 },
      { model: "qwen3.7-max", inputTokens: 5000, outputTokens: 1970, costCny: 0.0192 },
    ],
  },
  {
    id: "hist-20260610-platform-report",
    title: "AI 平台建设阶段报告",
    template: "项目阶段报告模板.docx",
    knowledgeBase: "平台建设知识库",
    createdAt: "2026-06-10T18:02:11+08:00",
    status: "completed",
    documentUrl: "/api/download/AI平台建设阶段报告_u5_20260610_180211.docx",
    inputTokens: 28560,
    outputTokens: 7320,
    costCny: 0.0826,
    modelUsage: [
      { model: "qwen3.7-plus", inputTokens: 18600, outputTokens: 5220, costCny: 0.0601 },
      { model: "qwen3.6-flash", inputTokens: 9960, outputTokens: 2100, costCny: 0.0225 },
    ],
  },
  {
    id: "hist-20260609-broken-template",
    title: "损坏模板试跑",
    template: "corrupted.docx",
    knowledgeBase: "项目 / kb",
    createdAt: "2026-06-09T11:36:58+08:00",
    status: "failed",
    inputTokens: 4200,
    outputTokens: 320,
    costCny: 0.0093,
    modelUsage: [
      { model: "qwen3.6-flash", inputTokens: 4200, outputTokens: 320, costCny: 0.0093 },
    ],
  },
];

export function formatTokenCount(value: number) {
  return value.toLocaleString();
}

export function formatHistoryCost(value: number) {
  return `¥${value.toFixed(4)}`;
}

export function articleTotalTokens(article: HistoryArticle) {
  return article.inputTokens + article.outputTokens;
}

export function aggregateHistory(records: HistoryArticle[]) {
  const inputTokens = records.reduce((sum, item) => sum + item.inputTokens, 0);
  const outputTokens = records.reduce((sum, item) => sum + item.outputTokens, 0);
  const costCny = records.reduce((sum, item) => sum + item.costCny, 0);
  return {
    count: records.length,
    inputTokens,
    outputTokens,
    totalTokens: inputTokens + outputTokens,
    costCny,
  };
}

export function aggregateModelUsage(records: HistoryArticle[]): HistoryModelUsage[] {
  const usage = new Map<string, HistoryModelUsage>();
  for (const record of records) {
    for (const item of record.modelUsage) {
      const current = usage.get(item.model) ?? {
        model: item.model,
        inputTokens: 0,
        outputTokens: 0,
        costCny: 0,
      };
      current.inputTokens += item.inputTokens;
      current.outputTokens += item.outputTokens;
      current.costCny = Number((current.costCny + item.costCny).toFixed(8));
      usage.set(item.model, current);
    }
  }
  return Array.from(usage.values()).sort(
    (a, b) => b.inputTokens + b.outputTokens - (a.inputTokens + a.outputTokens),
  );
}

export function filterHistoryArticles(
  records: HistoryArticle[],
  query: string,
  status: HistoryArticleStatus | "all",
) {
  const normalized = query.trim().toLowerCase();
  return records.filter((record) => {
    if (status !== "all" && record.status !== status) return false;
    if (!normalized) return true;
    return [
      record.title,
      record.template,
      record.knowledgeBase,
      record.status,
    ].some((value) => value.toLowerCase().includes(normalized));
  });
}
