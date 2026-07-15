// DEPRECATED: replaced by frontend/src/components/CustomModelsManager.tsx
// Kept for backward compatibility; remove in v2.1.0
import { Check, KeyRound, Loader2, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import {
  deleteCustomAuditModel,
  fetchCustomAuditModel,
  saveCustomAuditModel,
} from "../api";
import { Button, ErrorBanner, Input, Panel } from "../components/ui";
import { useI18n } from "../i18n";
import type { CustomAuditModelError, CustomAuditModelStatus } from "../types";


type CustomAuditSaveError = Error & {
  customAuditError?: CustomAuditModelError;
};


interface FormState {
  name: string;
  baseUrl: string;
  modelId: string;
  apiKey: string;
}


const INITIAL_FORM: FormState = {
  name: "",
  baseUrl: "",
  modelId: "",
  apiKey: "",
};


/**
 * Map a backend error code to a localized message via the errors.customAudit
 * i18n namespace. Falls back to the backend-provided message when no matching
 * key exists (defensive against unknown error codes).
 */
function localizeErrorCode(
  code: string | undefined,
  fallbackMessage: string,
  t: (key: string, ...args: Array<string | number>) => string,
): string {
  if (!code) return fallbackMessage;
  const key = `errors.customAudit.${code}`;
  const localized = t(key);
  // The t() helper returns the literal key when it is not found in the
  // dictionary; detect that and fall back to the raw backend message.
  return localized === key ? fallbackMessage : localized;
}


export default function CustomAuditModelCard() {
  const { t } = useI18n();

  const [status, setStatus] = useState<CustomAuditModelStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string>("");

  async function loadStatus(): Promise<void> {
    setStatusLoading(true);
    try {
      const current = await fetchCustomAuditModel();
      setStatus(current);
      // Pre-populate the editable fields (NOT the api_key; the backend only
      // ever returns a masked preview like "sk-a1...ef").
      setForm({
        name: current?.name ?? "",
        baseUrl: current?.base_url ?? "",
        modelId: current?.model_id ?? "",
        apiKey: "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  function updateField<K extends keyof FormState>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
    // Clear stale 422 error as soon as the user starts typing again.
    if (error) setError("");
  }

  async function handleSave() {
    if (!form.name.trim() || !form.baseUrl.trim() || !form.modelId.trim() || !form.apiKey.trim()) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      const saved = await saveCustomAuditModel({
        name: form.name.trim(),
        base_url: form.baseUrl.trim(),
        model_id: form.modelId.trim(),
        api_key: form.apiKey.trim(),
      });
      setStatus(saved);
      // Clear api_key on success so the preview reflects the masked hint.
      setForm((prev) => ({ ...prev, apiKey: "" }));
      window.dispatchEvent(
        new CustomEvent("xiangmushu:apikey-status-changed", {
          detail: { kind: "custom-audit-model", status: saved },
        }),
      );
    } catch (err) {
      const customErr = (err as CustomAuditSaveError)?.customAuditError;
      const localized = localizeErrorCode(
        customErr?.code,
        err instanceof Error ? err.message : String(err),
        t,
      );
      setError(localized);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setError("");
    try {
      await deleteCustomAuditModel();
      setStatus(null);
      setForm(INITIAL_FORM);
      window.dispatchEvent(
        new CustomEvent("xiangmushu:apikey-status-changed", {
          detail: { kind: "custom-audit-model", status: null },
        }),
      );
    } catch (err) {
      setError(
        t(
          "settings.customAudit.deleteError",
          err instanceof Error ? err.message : String(err),
        ),
      );
    } finally {
      setDeleting(false);
    }
  }

  const isDirty =
    (status?.name ?? "") !== form.name ||
    (status?.base_url ?? "") !== form.baseUrl ||
    (status?.model_id ?? "") !== form.modelId ||
    !!form.apiKey;

  const canSave =
    !!form.name.trim() &&
    !!form.baseUrl.trim() &&
    !!form.modelId.trim() &&
    !!form.apiKey.trim() &&
    !saving &&
    !deleting;

  const validated = status !== null && status.validated_at !== null && status.status !== "failed";
  const failed = status !== null && status.status === "failed";

  // Render-time: status pill + timestamp.
  const statusLabel = validated
    ? t("settings.customAudit.validated")
    : failed
      ? t("settings.customAudit.failed")
      : t("settings.customAudit.untested");
  const statusToneClass = validated
    ? "border-signal-lime/30 bg-signal-lime/10 text-signal-lime"
    : failed
      ? "border-signal-amber/30 bg-signal-amber/10 text-signal-amber"
      : "border-white/10 bg-white/[0.025] text-slate-400";

  return (
    <Panel className="mb-5 md:mb-6">
      <div id="custom-audit-model" className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 inline-flex items-center border border-white/10 bg-night-950 px-2 py-1 text-[11px] text-slate-400">
              {t("settings.customAudit.badge")}
            </div>
            <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">
              {t("settings.customAudit.title")}
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              {t("settings.customAudit.description")}
            </p>
          </div>
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-lime/40 bg-signal-lime/12 text-signal-lime">
            <ShieldCheck aria-hidden="true" size={20} />
          </div>
        </div>

        {status?.api_key_preview ? (
          <div className="inline-flex items-center gap-2 border border-white/10 bg-night-950 px-3 py-2 font-mono text-sm tracking-wide text-signal-lime">
            <KeyRound aria-hidden="true" size={14} />
            <span>{status.api_key_preview}</span>
          </div>
        ) : null}

        {statusLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="space-y-1">
                <div className="h-3 w-24 animate-pulse rounded bg-white/10" />
                <div className="h-9 animate-pulse rounded border border-white/10 bg-white/[0.025]" />
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                {t("settings.customAudit.nameLabel")}
              </span>
              <Input
                value={form.name}
                placeholder={t("settings.customAudit.namePlaceholder")}
                onChange={(event) => updateField("name", event.target.value)}
                disabled={saving || deleting}
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                {t("settings.customAudit.baseUrlLabel")}
              </span>
              <Input
                value={form.baseUrl}
                placeholder={t("settings.customAudit.baseUrlPlaceholder")}
                onChange={(event) => updateField("baseUrl", event.target.value)}
                disabled={saving || deleting}
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                {t("settings.customAudit.modelIdLabel")}
              </span>
              <Input
                value={form.modelId}
                placeholder={t("settings.customAudit.modelIdPlaceholder")}
                onChange={(event) => updateField("modelId", event.target.value)}
                disabled={saving || deleting}
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                {t("settings.customAudit.apiKeyLabel")}
              </span>
              <Input
                type="password"
                value={form.apiKey}
                placeholder={t("settings.customAudit.apiKeyPlaceholder")}
                onChange={(event) => updateField("apiKey", event.target.value)}
                disabled={saving || deleting}
                autoComplete="off"
              />
            </label>
          </div>
        )}

        {error ? <ErrorBanner message={error} /> : null}

        <div className="flex items-center gap-3 border-t border-white/10 pt-4">
          <div
            className={`inline-flex items-center gap-2 border px-2 py-1 text-xs font-semibold ${statusToneClass}`}
            role="status"
            aria-live="polite"
          >
            {validated ? <Check aria-hidden="true" size={14} /> : null}
            {statusLabel}
          </div>
          {validated && status?.validated_at ? (
            <span className="text-xs text-slate-500">
              {t("settings.customAudit.testedAt", status.validated_at)}
            </span>
          ) : null}
          {failed ? (
            <span className="text-xs text-signal-amber">
              {t("settings.customAudit.failedHint")}
            </span>
          ) : null}
        </div>

        <div className="grid gap-2.5">
          <Button
            className="min-h-12 w-full"
            onClick={() => {
              void handleSave();
            }}
            disabled={!canSave}
          >
            {saving ? (
              <Loader2 aria-hidden="true" className="animate-spin" size={16} />
            ) : (
              <ShieldCheck aria-hidden="true" size={16} />
            )}
            {saving
              ? t("settings.customAudit.saving")
              : t("settings.customAudit.validateAndSave")}
          </Button>

          <Button
            className="min-h-12 w-full"
            variant="danger"
            onClick={() => {
              void handleDelete();
            }}
            disabled={!status || deleting || saving}
          >
            {deleting ? (
              <Loader2 aria-hidden="true" className="animate-spin" size={16} />
            ) : (
              <Trash2 aria-hidden="true" size={16} />
            )}
            {deleting
              ? t("settings.customAudit.deleting")
              : t("settings.customAudit.delete")}
          </Button>

          <p className="px-1 text-xs leading-5 text-slate-500">
            {t("settings.customAudit.protocolNote")}
          </p>
          {validated && isDirty ? (
            <p className="px-1 text-xs leading-5 text-signal-amber">
              {t("settings.customAudit.unsavedChangesHint")}
            </p>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
