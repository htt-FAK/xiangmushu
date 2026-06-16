import type { HistoryArticle } from "./types";

export function formatTokenCount(value: number) {
  return value.toLocaleString();
}

export function formatHistoryCost(value: number) {
  return `¥${value.toFixed(4)}`;
}

export function articleTotalTokens(article: HistoryArticle) {
  return article.inputTokens + article.outputTokens;
}
