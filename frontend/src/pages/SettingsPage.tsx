import { KeyRound, Loader2, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { deleteApiKey, fetchApiKeyStatus, saveApiKey } from "../api";
import { Button, ErrorBanner, Input, PageHeader, Panel } from "../components/ui";
import { useI18n } from "../i18n";
import type { ApiKeyStatus } from "../types";

const BAILIAN_KEY_URL = "https://bailian.console.aliyun.com/#/key";

export default function SettingsPage() {
  const { t } = useI18n();
  const [status, setStatus] = useState<ApiKeyStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [agreeChecked, setAgreeChecked] = useState(false);
  const [agreeText, setAgreeText] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const canConfirm = agreeChecked && agreeText === t("settings.consentExact") && apiKey.trim().length > 0;

  useEffect(() => {
    fetchApiKeyStatus()
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const statusText = useMemo(() => {
    if (loading) return t("settings.loading");
    if (status?.has_key) return t("settings.keySaved");
    return t("settings.keyNotSaved");
  }, [loading, status?.has_key, t]);

  function openDialog() {
    setError("");
    setAgreeChecked(false);
    setAgreeText("");
    setDialogOpen(true);
  }

  async function confirmSave() {
    if (!canConfirm) return;
    setSaving(true);
    setError("");
    try {
      const next = await saveApiKey(apiKey);
      setStatus(next);
      setApiKey("");
      setDialogOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function removeKey() {
    setSaving(true);
    setError("");
    try {
      const next = await deleteApiKey();
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={t("settings.eyebrow")}
        title={t("settings.title")}
        description={t("settings.description")}
      />
      <ErrorBanner message={error} />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Panel>
          <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/12 text-signal-cyan">
                  <KeyRound size={20} />
                </div>
                <div>
                  <h2 className="font-display text-2xl font-semibold text-white">
                    {t("settings.apiKeyCardTitle")}
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">{statusText}</p>
                </div>
              </div>
              <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-300">
                {t("settings.apiKeyCardBody")}
              </p>
              {status?.updated_at && (
                <p className="mt-3 text-xs text-slate-500">
                  {t("settings.updatedAt")} {status.updated_at}
                </p>
              )}
            </div>
            <div className="flex shrink-0 flex-wrap gap-3">
              <Button onClick={openDialog} disabled={saving}>
                <KeyRound size={17} />
                {status?.has_key ? t("settings.replaceKey") : t("settings.addKey")}
              </Button>
              <Button variant="danger" onClick={removeKey} disabled={!status?.has_key || saving}>
                {saving ? <Loader2 className="animate-spin" size={17} /> : <Trash2 size={17} />}
                {t("settings.deleteKey")}
              </Button>
            </div>
          </div>
        </Panel>

        <Panel>
          <p className="font-display text-lg font-semibold text-white">{t("settings.bailianTitle")}</p>
          <p className="mt-3 text-sm leading-7 text-slate-300">{t("settings.bailianBody")}</p>
          <a
            className="mt-4 inline-flex min-h-10 items-center border border-white/10 bg-white/[0.055] px-4 text-sm font-semibold text-signal-cyan hover:border-signal-cyan/50"
            href={BAILIAN_KEY_URL}
            target="_blank"
            rel="noreferrer"
          >
            {t("settings.getKeyLink")}
          </a>
        </Panel>
      </div>

      {dialogOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-night-950/92 px-4 py-6 backdrop-blur">
          <div className="mx-auto max-w-3xl border border-white/10 bg-night-900 p-5 shadow-panel">
            <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-4">
              <h2 className="font-display text-3xl font-semibold text-white">
                {t("settings.noticeTitle")}
              </h2>
              <button
                type="button"
                onClick={() => setDialogOpen(false)}
                className="flex h-10 w-10 items-center justify-center border border-white/10 text-slate-400 hover:border-white/30 hover:text-white"
                aria-label={t("settings.cancel")}
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-5 space-y-3 text-sm leading-7 text-slate-200">
              {[1, 2, 3, 4, 5].map((item) => (
                <p key={item}>
                  {item}. {t(`settings.noticePoint${item}`)}
                </p>
              ))}
              <p>
                {t("settings.getKeyPrefix")}{" "}
                <a className="text-signal-cyan underline" href={BAILIAN_KEY_URL} target="_blank" rel="noreferrer">
                  {BAILIAN_KEY_URL}
                </a>
              </p>
            </div>

            <div className="mt-6 grid gap-4">
              <label className="flex items-center gap-3 border border-white/10 bg-night-950/70 p-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={agreeChecked}
                  onChange={(event) => setAgreeChecked(event.target.checked)}
                />
                <span>{t("settings.readConfirm")}</span>
              </label>

              <label className="block">
                <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {t("settings.consentLabel")}
                </span>
                <Input
                  value={agreeText}
                  onChange={(event) => setAgreeText(event.target.value)}
                  placeholder={t("settings.consentPlaceholder")}
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {t("settings.apiKeyLabel")}
                </span>
                <Input
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={t("settings.apiKeyPlaceholder")}
                  type="password"
                  autoComplete="off"
                />
              </label>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <Button variant="ghost" onClick={() => setDialogOpen(false)} disabled={saving}>
                {t("settings.cancel")}
              </Button>
              <Button onClick={confirmSave} disabled={!canConfirm || saving}>
                {saving ? <Loader2 className="animate-spin" size={17} /> : <KeyRound size={17} />}
                {t("settings.confirm")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
