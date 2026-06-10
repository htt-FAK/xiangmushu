import { Check, ChevronDown, Cpu, KeyRound, Languages, Loader2, Star, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { deleteApiKey, fetchApiKeyStatus, fetchModelOptions, fetchUserPreferences, saveApiKey, updateUserPreferences } from "../api";
import { useAuth, type Language } from "../auth";
import { Button, ErrorBanner, Input, PageHeader, Panel } from "../components/ui";
import { useI18n } from "../i18n";
import type { ApiKeyStatus, ModelModuleConfig, ModelOption, ModelOptionsMap } from "../types";

const BAILIAN_KEY_URL = "https://bailian.console.aliyun.com/#/key";

// ---------------------------------------------------------------------------
// Model Selector Component
// ---------------------------------------------------------------------------
function ModelSelector({
  moduleKey,
  config,
  selected,
  onSelect,
  saving,
}: {
  moduleKey: string;
  config: ModelModuleConfig;
  selected: string;
  onSelect: (moduleKey: string, model: string) => void;
  saving: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Flatten all options for display
  const flatOptions: { model: string; recommended?: boolean; tier?: string }[] = useMemo(() => {
    const result: { model: string; recommended?: boolean; tier?: string }[] = [];
    if (config.tiers) {
      for (const [tierName, models] of Object.entries(config.tiers)) {
        for (const m of models) {
          result.push({ ...m, tier: tierName });
        }
      }
    }
    if (config.options) {
      for (const m of config.options) {
        result.push(m);
      }
    }
    return result;
  }, [config]);

  const selectedLabel = flatOptions.find((o) => o.model === selected)?.model || selected || "—";
  const isRecommended = flatOptions.find((o) => o.model === selected)?.recommended;

  return (
    <div className="relative" ref={ref}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="text-sm font-medium text-slate-200">{config.label}</span>
          {config.description && (
            <p className="mt-0.5 text-xs text-slate-500 leading-relaxed">{config.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          disabled={saving}
          className={`flex min-w-[200px] items-center justify-between gap-2 border px-3 py-2 text-left text-sm transition ${
            open
              ? "border-signal-lime/60 bg-signal-lime/8 text-white"
              : "border-white/15 bg-white/[0.04] text-slate-200 hover:border-white/30"
          }`}
        >
          <span className="flex items-center gap-1.5 truncate">
            {selectedLabel}
            {isRecommended && <Star size={12} className="shrink-0 fill-signal-lime text-signal-lime" />}
          </span>
          <ChevronDown size={14} className={`shrink-0 text-slate-500 transition ${open ? "rotate-180" : ""}`} />
        </button>
      </div>

      {open && (
        <div className="absolute right-0 z-30 mt-1 w-full min-w-[240px] max-w-[320px] border border-white/15 bg-night-900 shadow-xl">
          {config.tiers ? (
            Object.entries(config.tiers).map(([tierName, models]) => (
              <div key={tierName}>
                <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  {tierName}
                </div>
                {models.map((m: ModelOption) => (
                  <button
                    key={m.model}
                    type="button"
                    onClick={() => {
                      onSelect(moduleKey, m.model);
                      setOpen(false);
                    }}
                    className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition ${
                      selected === m.model
                        ? "bg-signal-lime/12 text-white"
                        : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                    }`}
                  >
                    <span className="truncate">{m.model}</span>
                    {m.recommended && (
                      <span className="ml-2 shrink-0 rounded bg-signal-lime/20 px-1.5 py-0.5 text-[10px] font-bold text-signal-lime">
                        ⭐
                      </span>
                    )}
                    {selected === m.model && <Check size={14} className="ml-2 shrink-0 text-signal-lime" />}
                  </button>
                ))}
              </div>
            ))
          ) : (
            config.options?.map((m: ModelOption) => (
              <button
                key={m.model}
                type="button"
                onClick={() => {
                  onSelect(moduleKey, m.model);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition ${
                  selected === m.model
                    ? "bg-signal-lime/12 text-white"
                    : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                }`}
              >
                <span className="truncate">{m.model}</span>
                {m.recommended && (
                  <span className="ml-2 shrink-0 rounded bg-signal-lime/20 px-1.5 py-0.5 text-[10px] font-bold text-signal-lime">
                    ⭐
                  </span>
                )}
                {selected === m.model && <Check size={14} className="ml-2 shrink-0 text-signal-lime" />}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

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

  // Model selection state
  const [modelOptions, setModelOptions] = useState<ModelOptionsMap | null>(null);
  const [modelChoices, setModelChoices] = useState<Record<string, string>>({});
  const [modelLoading, setModelLoading] = useState(true);
  const [modelSaving, setModelSaving] = useState(false);
  const modelSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const canConfirm = apiKey.trim().length > 0;

  useEffect(() => {
    fetchApiKeyStatus()
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  // Default models per module (matches backend _DEFAULT_MODEL_OVERRIDES)
  const DEFAULT_MODELS: Record<string, string> = useMemo(() => ({
    generation: "qwen3.7-max",
    lightweight: "qwen3.6-flash",
    vision: "qwen3.7-plus",
    search: "qwen3.7-plus",
    audit: "qwen3.6-flash",
  }), []);

  // Load model options + current choices
  useEffect(() => {
    Promise.all([fetchModelOptions(), fetchUserPreferences()])
      .then(([options, prefs]) => {
        setModelOptions(options);
        // Merge saved choices with defaults for modules without saved choice
        const saved = prefs.model_choices ?? {};
        const merged: Record<string, string> = { ...saved };
        for (const key of Object.keys(options)) {
          if (!merged[key]) {
            merged[key] = DEFAULT_MODELS[key] || "";
          }
        }
        setModelChoices(merged);
      })
      .catch((err: unknown) => {
        console.error("Failed to load model options", err);
      })
      .finally(() => setModelLoading(false));
  }, []);

  const handleModelSelect = useCallback(
    (moduleKey: string, model: string) => {
      setModelChoices((prev) => ({ ...prev, [moduleKey]: model }));
      // Debounced save
      if (modelSaveTimer.current) clearTimeout(modelSaveTimer.current);
      setModelSaving(true);
      modelSaveTimer.current = setTimeout(() => {
        updateUserPreferences({ model_choices: { ...modelChoices, [moduleKey]: model } })
          .then((updated) => {
            setModelChoices(updated.model_choices ?? { ...modelChoices, [moduleKey]: model });
          })
          .catch((err: unknown) => {
            console.error("Failed to save model choice", err);
          })
          .finally(() => setModelSaving(false));
      }, 400);
    },
    [modelChoices],
  );

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

      <Panel className="hidden mb-5 md:mb-6 md:block">
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

      {/* Model Selection Panel — desktop only, requires API Key */}
      {status?.has_key && (
      <Panel className="hidden mb-5 md:mb-6 md:block">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-lime/40 bg-signal-lime/12 text-signal-lime md:h-11 md:w-11">
            <Cpu size={20} />
          </div>
          <div className="min-w-0">
            <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">
              {t("settings.modelCardTitle")}
            </h2>
            <p className="mt-0.5 text-sm text-slate-400">
              {t("settings.modelCardBody")}
            </p>
          </div>
          {modelSaving && (
            <Loader2 className="ml-auto animate-spin text-signal-lime" size={16} />
          )}
        </div>

        {modelLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="h-4 w-20 animate-pulse rounded bg-white/10" />
                <div className="h-9 w-[200px] animate-pulse rounded border border-white/10 bg-white/[0.03]" />
              </div>
            ))}
          </div>
        ) : modelOptions ? (
          <div className="space-y-3">
            {Object.entries(modelOptions).map(([key, cfg]) => (
              <ModelSelector
                key={key}
                moduleKey={key}
                config={cfg}
                selected={modelChoices[key] || ""}
                onSelect={handleModelSelect}
                saving={modelSaving}
              />
            ))}
          </div>
        ) : null}
      </Panel>
      )}

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
