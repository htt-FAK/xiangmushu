/**
 * `<TestResultPanel>` — displays capability test results with per-test status and suggested roles.
 *
 * @remarks
 * - Renders as a DetailOverlay showing per-capability results: green checkmark (passed), red X (failed), gray dash (skipped), with latency and error details.
 * - State machine: viewing results, accepting suggestions (saving spinner), retrying tests.
 * - Calls: `assignModelRoles` when user accepts suggested roles; delegates retry/close to parent.
 * - Integrates with: CustomModelsManager (receives TestResult, triggers role assignment).
 *
 * @example
 * ```tsx
 * import TestResultPanel from "../components/TestResultPanel";
 * <TestResultPanel result={testResult} onAcceptSuggestions={handleAccept} onRetry={handleRetry} onClose={handleClose} />
 * ```
 *
 * @packageDocumentation
 * Part of the multi-custom-models feature (openspec change: multi-custom-models).
 */
import { CheckCircle2, Loader2, MinusCircle, RefreshCcw, XCircle } from "lucide-react";
import { useState } from "react";
import { assignModelRoles } from "../api";
import { Button, DetailOverlay } from "./ui";
import { useI18n } from "../i18n";
import type { TestResult } from "../types";

interface TestResultPanelProps {
  result: TestResult;
  onAcceptSuggestions: () => void;
  onRetry: () => void;
  onClose: () => void;
}

export default function TestResultPanel({
  result,
  onAcceptSuggestions,
  onRetry,
  onClose,
}: TestResultPanelProps) {
  const { t, language } = useI18n();
  const [saving, setSaving] = useState(false);

  // Pick the user-language detail string when available (``detail_i18n``);
  // fall back to the English ``detail`` string for backward compatibility.
  function detailText(data: { detail?: string | null; detail_i18n?: { zh: string; en: string } | null } | undefined | null): string | null {
    if (!data) return null;
    if (data.detail_i18n) {
      return data.detail_i18n[language] ?? data.detail_i18n.en;
    }
    return data.detail ?? null;
  }

  const capabilities = [
    { key: "text", label: t("settings.customModels.capabilityText"), data: result.test_results.text },
    { key: "vision", label: t("settings.customModels.capabilityVision"), data: result.test_results.vision },
    { key: "embedding", label: t("settings.customModels.capabilityEmbedding"), data: result.test_results.embedding },
  ] as const;

  async function handleAccept() {
    setSaving(true);
    try {
      await assignModelRoles(result.id, result.suggested_roles);
      onAcceptSuggestions();
    } catch (err) {
      console.error("Failed to assign roles", err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <DetailOverlay
      title={t("settings.customModels.testResultTitle")}
      onClose={onClose}
    >
      <div className="space-y-6">
        <div className="divide-y divide-white/10 border border-white/10 bg-night-950">
          {capabilities.map((cap) => (
            <div key={cap.key} className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                {cap.data?.passed ? (
                  <CheckCircle2 size={18} className="text-signal-lime" />
                ) : detailText(cap.data) ? (
                  <XCircle size={18} className="text-signal-rose" />
                ) : (
                  <MinusCircle size={18} className="text-slate-500" />
                )}
                <div>
                  <p className="text-sm font-medium text-white">{cap.label}</p>
                  {detailText(cap.data) && (
                    <p className="text-xs text-signal-rose/80">{detailText(cap.data)}</p>
                  )}
                </div>
              </div>
              <div className="text-right">
                <p className="font-mono text-xs text-slate-400">
                  {cap.data && cap.data.latency_ms > 0 ? `${cap.data.latency_ms}ms` : "--"}
                </p>
              </div>
            </div>
          ))}
        </div>

        {result.suggested_roles.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {t("settings.customModels.suggestedRoles")}
            </h4>
            <div className="flex flex-wrap gap-2">
              {result.suggested_roles.map((role) => (
                <span
                  key={role}
                  className="border border-signal-cyan/40 bg-signal-cyan/10 px-2 py-0.5 text-xs font-medium text-signal-cyan"
                >
                  {role}
                </span>
              ))}
            </div>
            <Button
              variant="primary"
              className="mt-2 w-full"
              onClick={handleAccept}
              disabled={saving}
            >
              {saving && <Loader2 size={16} className="animate-spin" />}
              {t("settings.customModels.acceptSuggestions")}
            </Button>
          </div>
        )}

        <div className="flex gap-3 pt-4 border-t border-white/10">
          <Button variant="secondary" className="flex-1" onClick={onRetry}>
            <RefreshCcw size={16} />
            {t("settings.customModels.retryAll")}
          </Button>
          <Button variant="ghost" className="px-8" onClick={onClose}>
            {t("common.close")}
          </Button>
        </div>
      </div>
    </DetailOverlay>
  );
}
