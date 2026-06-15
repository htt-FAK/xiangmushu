import { Check, ChevronDown, Cpu, KeyRound, Languages, Loader2, Star, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { deleteApiKey, fetchApiKeyStatus, fetchModelOptions, fetchUserPreferences, saveApiKey, updateUserPreferences, validateApiKey } from "../api";
import { useAuth, type Language } from "../auth";
import { Button, ErrorBanner, Input, PageHeader, Panel } from "../components/ui";
import { useI18n } from "../i18n";
import type { ApiKeyStatus, ApiKeyValidationResult, ModelModuleConfig, ModelOption, ModelOptionsMap, ProviderApiKeyStatus } from "../types";

const MODEL_ROLE_ORDER = ["main_writer", "web_search", "fast_writer", "vision_layout", "template_planner", "audit_text"];
type ApiKeyStage = "idle" | "validating" | "saving" | "saved" | "failed";
type ProviderCode = "dashscope" | "deepseek" | "mimo";

const PROVIDERS: Array<{
  code: ProviderCode;
  title: string;
  body: string;
  link: string;
  linkLabel: string;
  badge: string;
}> = [
  {
    code: "dashscope",
    title: "DashScope / 阿里云百炼",
    body: "站点基础能力提供方。知识库 embedding、默认文本、默认联网和默认视觉链路都依赖 DashScope。",
    link: "https://bailian.console.aliyun.com/#/key",
    linkLabel: "获取 DashScope Key",
    badge: "基础必需",
  },
  {
    code: "deepseek",
    title: "DeepSeek",
    body: "文本补充 provider。可用于主写作、快速写作、模板规划和文本审核，不参与联网搜索、视觉和 embedding。",
    link: "https://platform.deepseek.com/api_keys",
    linkLabel: "获取 DeepSeek Key",
    badge: "文本补充",
  },
  {
    code: "mimo",
    title: "Xiaomi MiMo",
    body: "文本、联网搜索和视觉补充 provider。按量付费，联网搜索需单独开通插件服务。",
    link: "https://platform.xiaomimimo.com/console/api-keys",
    linkLabel: "获取 MiMo Key",
    badge: "文本 / 搜索 / 视觉",
  },
];

function flattenOptions(config?: ModelModuleConfig): ModelOption[] {
  const seen = new Set<string>();
  const out: ModelOption[] = [];
  for (const group of Object.values(config?.tiers ?? {})) {
    for (const item of group) {
      if (!item.model || seen.has(item.model)) continue;
      seen.add(item.model);
      out.push(item);
    }
  }
  for (const item of config?.options ?? []) {
    if (!item.model || seen.has(item.model)) continue;
    seen.add(item.model);
    out.push(item);
  }
  return out;
}

function preferredModel(config?: ModelModuleConfig, current = "") {
  const options = flattenOptions(config);
  if (current && options.some((item) => item.model === current)) return current;
  return options.find((item) => item.recommended)?.model || options[0]?.model || current;
}

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

  const flatOptions: ModelOption[] = useMemo(() => flattenOptions(config), [config]);
  const selectedOption = flatOptions.find((o) => o.model === selected);
  const selectedLabel = selectedOption?.label || selectedOption?.model || selected || "...";

  return (
    <div className={`relative ${open ? "z-[90]" : "z-0"}`} ref={ref}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="text-sm font-medium text-slate-200">{config.label}</span>
          {config.description ? <p className="mt-0.5 text-xs text-slate-500 leading-relaxed">{config.description}</p> : null}
        </div>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          disabled={saving}
          className={`flex min-w-[220px] items-center justify-between gap-2 border px-3 py-2 text-left text-sm transition ${
            open
              ? "border-signal-lime/60 bg-signal-lime/8 text-white"
              : "border-white/15 bg-white/[0.04] text-slate-200 hover:border-white/30"
          }`}
        >
          <span className="flex items-center gap-1.5 truncate">
            {selectedLabel}
            {selectedOption?.provider_name ? <span className="text-xs text-slate-500">({selectedOption.provider_name})</span> : null}
            {selectedOption?.recommended ? <Star size={12} className="shrink-0 fill-signal-lime text-signal-lime" /> : null}
          </span>
          <ChevronDown size={14} className={`shrink-0 text-slate-500 transition ${open ? "rotate-180" : ""}`} />
        </button>
      </div>

      {open ? (
        <div className="absolute right-0 z-[100] mt-1 max-h-[360px] w-full min-w-[260px] max-w-[360px] overflow-y-auto border border-white/15 bg-night-900 shadow-xl">
          {flatOptions.map((option) => (
            <button
              key={`${option.provider_code || "default"}-${option.model}`}
              type="button"
              onClick={() => {
                onSelect(moduleKey, option.model);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition ${
                selected === option.model
                  ? "bg-signal-lime/12 text-white"
                  : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate">{option.label || option.model}</span>
                <span className="block truncate text-xs text-slate-500">
                  {option.provider_name || option.provider_code || option.model}
                </span>
              </span>
              <span className="ml-2 flex shrink-0 items-center gap-2">
                {option.recommended ? (
                  <span className="rounded bg-signal-lime/20 px-1.5 py-0.5 text-[10px] font-bold text-signal-lime">推荐</span>
                ) : null}
                {selected === option.model ? <Check size={14} className="text-signal-lime" /> : null}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function providerStatusText(status: ProviderApiKeyStatus | undefined, loading: boolean) {
  if (loading) return "加载中...";
  if (!status?.has_key) return "未保存";
  if (status.validated) return "已验证";
  return "已保存，待验证";
}

export default function SettingsPage() {
  const { t } = useI18n();
  const { language, setLanguage } = useAuth();
  const [status, setStatus] = useState<ApiKeyStatus | null>(null);
  const [activeProvider, setActiveProvider] = useState<ProviderCode>("dashscope");
  const [apiKey, setApiKey] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [languageSaving, setLanguageSaving] = useState(false);
  const [error, setError] = useState("");
  const [validation, setValidation] = useState<ApiKeyValidationResult | null>(null);
  const [apiKeyStage, setApiKeyStage] = useState<ApiKeyStage>("idle");
  const [modelOptions, setModelOptions] = useState<ModelOptionsMap | null>(null);
  const [modelChoices, setModelChoices] = useState<Record<string, string>>({});
  const [modelWarnings, setModelWarnings] = useState<Record<string, string>>({});
  const [modelLoading, setModelLoading] = useState(true);
  const [modelSaving, setModelSaving] = useState(false);
  const modelSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const providerStatuses = status?.providers ?? {};
  const canConfirm = apiKey.trim().length > 0;

  useEffect(() => {
    fetchApiKeyStatus()
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const visibleModelOptions = useMemo(() => {
    if (!modelOptions) return [];
    return MODEL_ROLE_ORDER.filter((key) => modelOptions[key]).map((key) => [key, modelOptions[key]] as const);
  }, [modelOptions]);

  useEffect(() => {
    Promise.all([fetchModelOptions(), fetchUserPreferences()])
      .then(([options, prefs]) => {
        setModelOptions(options);
        const saved = prefs.model_choices ?? {};
        const merged: Record<string, string> = { ...saved };
        const warnings: Record<string, string> = { ...(prefs.warnings ?? {}) };
        for (const key of MODEL_ROLE_ORDER) {
          const cfg = options[key];
          const availableModels = flattenOptions(cfg).map((item) => item.model);
          const savedChoice = merged[key];
          if (savedChoice && availableModels.length > 0 && !availableModels.includes(savedChoice)) {
            const fallbackModel = preferredModel(cfg, savedChoice);
            merged[key] = fallbackModel;
            warnings[key] = cfg?.selected_unavailable?.reason ?? `${savedChoice} unavailable, switched to ${fallbackModel}`;
          }
          if (!merged[key]) {
            merged[key] = preferredModel(cfg);
          }
          if (cfg?.warning) {
            warnings[key] = warnings[key] || cfg.warning;
          }
        }
        setModelChoices(merged);
        setModelWarnings(warnings);
      })
      .catch((err: unknown) => console.error("Failed to load model options", err))
      .finally(() => setModelLoading(false));
  }, []);

  const handleModelSelect = useCallback((moduleKey: string, model: string) => {
    setModelWarnings((prev) => {
      const next = { ...prev };
      delete next[moduleKey];
      return next;
    });
    let nextChoices: Record<string, string> = {};
    setModelChoices((prev) => {
      nextChoices = { ...prev, [moduleKey]: model };
      return nextChoices;
    });
    if (modelSaveTimer.current) clearTimeout(modelSaveTimer.current);
    setModelSaving(true);
    modelSaveTimer.current = setTimeout(() => {
      updateUserPreferences({ model_choices: nextChoices })
        .then((updated) => {
          setModelChoices(updated.model_choices ?? nextChoices);
          setModelWarnings((prev) => ({ ...prev, ...(updated.warnings ?? {}) }));
        })
        .catch((err: unknown) => console.error("Failed to save model choice", err))
        .finally(() => setModelSaving(false));
    }, 400);
  }, []);

  function openDialog(providerCode: ProviderCode) {
    setActiveProvider(providerCode);
    setError("");
    setValidation(null);
    setApiKeyStage("idle");
    setDialogOpen(true);
  }

  async function confirmSave() {
    if (!canConfirm) return;
    setSaving(true);
    setError("");
    setValidation(null);
    setApiKeyStage("validating");
    try {
      const checked = await validateApiKey(apiKey, activeProvider);
      setValidation(checked);
      if (!checked.ok) {
        setApiKeyStage("failed");
        setError(checked.message);
        return;
      }
      setApiKeyStage("saving");
      const next = await saveApiKey(apiKey, activeProvider);
      setStatus(next);
      setValidation(next.validation ?? checked);
      setApiKey("");
      setApiKeyStage("saved");
      window.dispatchEvent(new CustomEvent("xiangmushu:apikey-status-changed", { detail: next }));
    } catch (err) {
      setApiKeyStage("failed");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function removeKey(providerCode: ProviderCode) {
    setSaving(true);
    setError("");
    try {
      const next = await deleteApiKey(providerCode);
      setStatus(next);
      window.dispatchEvent(new CustomEvent("xiangmushu:apikey-status-changed", { detail: next }));
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
      <PageHeader eyebrow={t("settings.eyebrow")} title={t("settings.title")} description={t("settings.description")} />
      <ErrorBanner message={error} />

      <Panel className="relative z-30 overflow-visible mb-5 md:mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-lime/40 bg-signal-lime/12 text-signal-lime md:h-11 md:w-11">
                <Languages size={20} />
              </div>
              <div className="min-w-0">
                <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("settings.languageCardTitle")}</h2>
                <p className="mt-0.5 text-sm text-slate-400">{t("settings.languageCardBody")}</p>
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
                    <span className="font-display text-lg font-semibold md:text-xl">{t(`settings.language.${item}.title`)}</span>
                    {active ? <Check size={19} className="text-signal-lime" /> : null}
                  </span>
                  <span className="mt-1.5 block text-sm leading-6 text-slate-400 md:mt-2">{t(`settings.language.${item}.body`)}</span>
                </button>
              );
            })}
          </div>
        </div>
      </Panel>

      <Panel className="relative z-40 overflow-visible mb-5 md:mb-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-lime/40 bg-signal-lime/12 text-signal-lime md:h-11 md:w-11">
            <Cpu size={20} />
          </div>
          <div className="min-w-0">
            <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">{t("settings.modelCardTitle")}</h2>
            <p className="mt-0.5 text-sm text-slate-400">{t("settings.modelCardBody")}</p>
          </div>
          {modelSaving ? <Loader2 className="ml-auto animate-spin text-signal-lime" size={16} /> : null}
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
            {visibleModelOptions.map(([key, cfg]) => (
              <div key={key} className="space-y-2">
                <ModelSelector moduleKey={key} config={cfg} selected={modelChoices[key] || ""} onSelect={handleModelSelect} saving={modelSaving} />
                {cfg.source && cfg.source !== "registry" ? <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">{cfg.source}</p> : null}
                {modelWarnings[key] ? <p className="text-xs text-signal-amber">{modelWarnings[key]}</p> : null}
              </div>
            ))}
          </div>
        ) : null}
      </Panel>

      <div className="grid gap-5 md:gap-6 lg:grid-cols-3">
        {PROVIDERS.map((provider) => {
          const item = providerStatuses[provider.code];
          return (
            <Panel key={provider.code} className="min-w-0">
              <div className="flex flex-col gap-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="mb-2 inline-flex items-center border border-white/10 bg-night-950/70 px-2 py-1 text-[11px] text-slate-400">
                      {provider.badge}
                    </div>
                    <h2 className="break-words font-display text-xl font-semibold text-white">{provider.title}</h2>
                    <p className="mt-1 text-sm text-slate-400">{providerStatusText(item, loading)}</p>
                  </div>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/12 text-signal-cyan">
                    <KeyRound size={18} />
                  </div>
                </div>

                {item?.has_key && item.key_preview ? (
                  <div className="inline-flex items-center gap-2 border border-white/10 bg-night-950/70 px-3 py-2 font-mono text-sm tracking-wide text-signal-cyan">
                    <KeyRound size={14} />
                    <span>{item.key_preview}</span>
                  </div>
                ) : null}

                <p className="text-sm leading-6 text-slate-300">{provider.body}</p>
                {provider.code === "mimo" ? (
                  <div className="space-y-2 text-xs leading-5 text-slate-400">
                    <p>Base URL: `https://api.xiaomimimo.com/v1`</p>
                    <p>按量付费，联网服务单独计费，不包含在 token 价格内。</p>
                    <a className="text-signal-cyan underline" href="https://platform.xiaomimimo.com/console/plugin?userId=2933868983" target="_blank" rel="noreferrer">
                      开通 MiMo 联网搜索插件
                    </a>
                  </div>
                ) : null}
                {item?.updated_at ? <p className="text-xs text-slate-500">{t("settings.updatedAt")} {item.updated_at}</p> : null}

                <div className="grid gap-2.5">
                  <Button className="min-h-12 w-full" onClick={() => openDialog(provider.code)} disabled={saving}>
                    <KeyRound size={17} />
                    {item?.has_key ? t("settings.replaceKey") : t("settings.addKey")}
                  </Button>
                  <Button className="min-h-12 w-full" variant="danger" onClick={() => void removeKey(provider.code)} disabled={!item?.has_key || saving}>
                    {saving ? <Loader2 className="animate-spin" size={17} /> : <Trash2 size={17} />}
                    {t("settings.deleteKey")}
                  </Button>
                  <a
                    className="inline-flex min-h-12 items-center justify-center border border-white/10 bg-white/[0.055] px-4 text-sm font-semibold text-signal-cyan hover:border-signal-cyan/50"
                    href={provider.link}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {provider.linkLabel}
                  </a>
                </div>
              </div>
            </Panel>
          );
        })}
      </div>

      {dialogOpen ? (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-night-950/92 px-4 py-6 backdrop-blur">
          <div className="mx-auto w-full max-w-3xl border border-white/10 bg-night-900 p-4 shadow-panel md:p-5">
            <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-3 md:pb-4">
              <h2 className="break-words font-display text-xl font-semibold text-white md:text-3xl">
                保存 {PROVIDERS.find((item) => item.code === activeProvider)?.title} API Key
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

            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-200">
              <p>当前 provider：{PROVIDERS.find((item) => item.code === activeProvider)?.title}</p>
              {activeProvider === "dashscope" ? <p>DashScope 仍是全站基础能力，未保存或未验证时首页、生成页、模板分析页都会保持 missing_key。</p> : null}
              {activeProvider === "deepseek" ? <p>DeepSeek 仅用于文本角色，不参与联网搜索、视觉和 embedding。</p> : null}
              {activeProvider === "mimo" ? <p>MiMo 采用按量付费模式，联网搜索需先在插件页开通，否则保存时会返回明确错误。</p> : null}
            </div>

            <div className="mt-6 grid gap-4">
              <label className="block">
                <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">API Key</span>
                <Input
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={activeProvider === "mimo" ? "请输入 Xiaomi MiMo API Key" : activeProvider === "deepseek" ? "请输入 DeepSeek API Key" : "请输入 DashScope API Key"}
                  type="password"
                  autoComplete="off"
                  disabled={saving || apiKeyStage === "saved"}
                />
              </label>
            </div>

            <div className="mt-4 border border-white/10 bg-night-950/65 p-3 text-sm">
              {apiKeyStage === "idle" ? <p className="text-slate-400">确认后会先验证当前 provider 的 API Key，再执行保存。</p> : null}
              {apiKeyStage === "validating" ? (
                <p className="inline-flex items-center gap-2 text-signal-cyan">
                  <Loader2 className="animate-spin" size={16} />
                  正在验证 API Key...
                </p>
              ) : null}
              {apiKeyStage === "saving" ? (
                <p className="inline-flex items-center gap-2 text-signal-cyan">
                  <Loader2 className="animate-spin" size={16} />
                  验证通过，正在保存...
                </p>
              ) : null}
              {apiKeyStage === "saved" ? (
                <p className="inline-flex items-center gap-2 text-signal-lime">
                  <Check size={16} />
                  API Key 已保存。
                </p>
              ) : null}
              {apiKeyStage === "failed" && validation ? <p className="text-signal-amber">{validation.message}</p> : null}
              {validation?.probes?.length ? (
                <div className="mt-3 space-y-2">
                  {validation.probes.map((probe) => (
                    <div
                      key={`${probe.model}-${probe.code}`}
                      className={`flex flex-col gap-1 border px-3 py-2 text-xs sm:flex-row sm:items-center sm:justify-between ${
                        probe.ok
                          ? "border-signal-lime/25 bg-signal-lime/5 text-signal-lime"
                          : "border-signal-amber/30 bg-signal-amber/5 text-signal-amber"
                      }`}
                    >
                      <span className="font-mono">{probe.model}</span>
                      <span className="break-words sm:text-right">{probe.ok ? "可用" : probe.message}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="mt-6 grid gap-3 sm:flex sm:flex-wrap sm:justify-end">
              <Button className="min-h-12 w-full sm:w-auto" variant="ghost" onClick={() => setDialogOpen(false)} disabled={saving}>
                {apiKeyStage === "saved" ? "完成" : t("settings.cancel")}
              </Button>
              <Button className="min-h-12 w-full font-bold sm:w-auto" onClick={confirmSave} disabled={!canConfirm || saving || apiKeyStage === "saved"}>
                {saving ? <Loader2 className="animate-spin" size={17} /> : <KeyRound size={17} />}
                {apiKeyStage === "validating" ? "测试中" : apiKeyStage === "saving" ? "保存中" : apiKeyStage === "saved" ? "已保存" : t("settings.confirm")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
