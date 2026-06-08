import { Check, KeyRound, Languages, Loader2, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { deleteApiKey, fetchApiKeyStatus, saveApiKey } from "../api";
import { useAuth, type Language } from "../auth";
import { Button, ErrorBanner, Input, PageHeader, Panel } from "../components/ui";
import { useI18n } from "../i18n";
import type { ApiKeyStatus } from "../types";

const BAILIAN_KEY_URL = "https://bailian.console.aliyun.com/#/key";

export default function SettingsPage() {
  const { t } = useI18n();
  const { language, setLanguage } = useAuth();
  const [status, setStatus] = useState<ApiKeyStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [agreeChecked, setAgreeChecked] = useState(false);
  const [agreeText, setAgreeText] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [languageSaving, setLanguageSaving] = useState(false);
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

  async function chooseLanguage(nextLanguage: Language) {
    if (nextLanguage === language || languageSaving) return;
    setLanguageSaving(true);
    setError("");
    try {
      await setLanguage(nextLanguage);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLanguageSaving(false);
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

      <Panel className="mb-5 md:mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-lime/40 bg-signal-lime/12 text-signal-lime md:h-11 md:w-11">
                <Languages size={20} />
              </div>
              <div className="min-w-0">
                <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">
                  {t("settings.languageCardTitle")}
                </h2>
                <p className="mt-0.5 text-sm text-slate-400">
                  {t("settings.languageCardBody")}
                </p>
              </div>
            </div>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:w-[440px]">
            {(["zh", "en"] as const).map((item) => {
              const active = language === item;
              return (
                <button
                  key={item}
                  type="button"
                  onClick={() => void chooseLanguage(item)}
                  disabled={languageSaving}
                  className={`min-h-20 border p-3.5 text-left transition md:min-h-24 md:p-4 ${
                    active
                      ? "border-signal-lime/70 bg-signal-lime/12 text-white shadow-[0_0_0_1px_rgba(184,255,94,0.12),0_18px_48px_rgba(184,255,94,0.08)]"
                      : "border-white/10 bg-white/[0.035] text-slate-300 hover:border-white/25 hover:text-white"
                  }`}
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="font-display text-lg font-semibold md:text-xl">
                      {t(`settings.language.${item}.title`)}
                    </span>
                    {active ? <Check size={19} className="text-signal-lime" /> : null}
                  </span>
                  <span className="mt-1.5 block text-sm leading-6 text-slate-400 md:mt-2">
                    {t(`settings.language.${item}.body`)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </Panel>

      <div className="grid gap-5 md:gap-6 lg:grid-cols-[1fr_360px]">
        <Panel className="min-w-0">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/12 text-signal-cyan md:h-11 md:w-11">
                  <KeyRound size={20} />
                </div>
                <div className="min-w-0">
                  <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">
                    {t("settings.apiKeyCardTitle")}
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">{statusText}</p>
                </div>
              </div>
              {status?.has_key && status.key_preview && (
                <div className="mt-3 inline-flex items-center gap-2 border border-white/10 bg-night-950/70 px-3 py-2 font-mono text-sm tracking-wide text-signal-cyan">
                  <KeyRound size={14} />
                  <span>{status.key_preview}</span>
                </div>
              )}
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 md:mt-5 md:leading-7">
                {t("settings.apiKeyCardBody")}
              </p>
              {status?.updated_at && (
                <p className="mt-3 text-xs text-slate-500">
                  {t("settings.updatedAt")} {status.updated_at}
                </p>
              )}
            </div>
            <div className="grid shrink-0 gap-2.5 sm:flex sm:flex-wrap sm:gap-3">
              <Button className="min-h-12 w-full font-bold sm:min-h-11 sm:w-auto sm:font-semibold" onClick={openDialog} disabled={saving}>
                <KeyRound size={17} />
                {status?.has_key ? t("settings.replaceKey") : t("settings.addKey")}
              </Button>
              <Button className="min-h-12 w-full sm:min-h-11 sm:w-auto" variant="danger" onClick={removeKey} disabled={!status?.has_key || saving}>
                {saving ? <Loader2 className="animate-spin" size={17} /> : <Trash2 size={17} />}
                {t("settings.deleteKey")}
              </Button>
            </div>
          </div>
        </Panel>

        <Panel className="min-w-0">
          <p className="font-display text-lg font-semibold text-white">{t("settings.bailianTitle")}</p>
          <p className="mt-2 text-sm leading-6 text-slate-300 md:mt-3 md:leading-7">{t("settings.bailianBody")}</p>
          <a
            className="mt-4 inline-flex min-h-12 w-full items-center justify-center border border-white/10 bg-white/[0.055] px-4 text-sm font-bold text-signal-cyan hover:border-signal-cyan/50 sm:min-h-11 sm:w-auto sm:font-semibold"
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
          <div className="mx-auto w-full max-w-3xl border border-white/10 bg-night-900 p-4 shadow-panel md:p-5">
            <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-3 md:pb-4">
              <h2 className="break-words font-display text-xl font-semibold text-white md:text-3xl">
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

            <div className="mt-4 space-y-2.5 text-sm leading-6 text-slate-200 md:mt-5 md:space-y-3 md:leading-7">
              {[1, 2, 3, 4, 5, 6].map((item) => (
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
              <label className="flex min-h-12 items-center gap-3 border border-white/10 bg-night-950/70 p-3 text-sm text-slate-200">
                <input
                  className="h-5 w-5 shrink-0 accent-signal-cyan"
                  type="checkbox"
                  checked={agreeChecked}
                  onChange={(event) => setAgreeChecked(event.target.checked)}
                />
                <span className="min-w-0 break-words">{t("settings.readConfirm")}</span>
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

            <div className="mt-6 grid gap-3 sm:flex sm:flex-wrap sm:justify-end">
              <Button className="min-h-12 w-full sm:w-auto" variant="ghost" onClick={() => setDialogOpen(false)} disabled={saving}>
                {t("settings.cancel")}
              </Button>
              <Button className="min-h-12 w-full font-bold sm:w-auto" onClick={confirmSave} disabled={!canConfirm || saving}>
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
