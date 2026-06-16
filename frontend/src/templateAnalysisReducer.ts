import type { BillingRecord, TemplateAnalysisEvent, TemplateAnalysisSessionSnapshot } from "./types";

function mergeBilling(
  current: TemplateAnalysisSessionSnapshot["billing"],
  record: BillingRecord,
): NonNullable<TemplateAnalysisSessionSnapshot["billing"]> {
  const existing = current ?? { records: [], input_tokens: 0, output_tokens: 0, cost_cny: 0 };
  return {
    records: [...(existing.records ?? []), record],
    input_tokens: (existing.input_tokens ?? 0) + (record.input_tokens ?? 0),
    output_tokens: (existing.output_tokens ?? 0) + (record.output_tokens ?? 0),
    cost_cny: Number(((existing.cost_cny ?? 0) + (record.cost_cny ?? 0)).toFixed(8)),
  };
}

export function reduceTemplateAnalysisSession(
  prev: TemplateAnalysisSessionSnapshot,
  event: TemplateAnalysisEvent,
  labels?: { statusComplete?: string; statusFailed?: string },
): TemplateAnalysisSessionSnapshot {
  if (event.type === "heartbeat") return prev;

  const base: TemplateAnalysisSessionSnapshot = {
    ...prev,
    last_seq: event.seq ?? prev.last_seq,
    updated_at: new Date().toISOString(),
  };

  if (event.type === "status") {
    return {
      ...base,
      status: "running",
      currentPhase: event.phase,
      statusMessage: event.message,
      logs: [...prev.logs, { phase: event.phase, message: event.message, created_at: new Date().toISOString() }],
    };
  }

  if (event.type === "billing") {
    return {
      ...base,
      billing: mergeBilling(prev.billing, event.billing),
    };
  }

  if (event.type === "done") {
    const message = event.message || labels?.statusComplete || "分析完成";
    return {
      ...base,
      status: "done",
      currentPhase: "done",
      statusMessage: message,
      template: event.template || prev.template,
      mode: event.mode || prev.mode,
      vision_status: event.vision_status || prev.vision_status,
      tasks: event.tasks ?? prev.tasks,
      billing: event.billing ?? prev.billing,
      logs: [...prev.logs, { phase: "done", message, created_at: new Date().toISOString() }],
    };
  }

  const payload =
    typeof event.error === "string"
      ? { code: "template_analysis_error", message: event.error }
      : event.error;
  const message = payload.message || labels?.statusFailed || "分析失败";
  return {
    ...base,
    status: "error",
    currentPhase: "error",
    statusMessage: message,
    last_error: payload,
    logs: [...prev.logs, { phase: "error", message, created_at: new Date().toISOString() }],
  };
}
