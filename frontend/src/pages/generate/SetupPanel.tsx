import { AlertTriangle, MessageSquareText, Settings, Sparkles, Zap, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Panel } from "../../components/ui";
import { useI18n } from "../../i18n";
import type { CustomModel, ModelOptionsMap, ModelOption } from "../../types";
import { clsx } from "../../utils";
import { flattenModelOptions } from "../../models";
import { FormatOverridesPanel, type FormatOverrides } from "./FormatOverridesPanel";
import { detectCustomModelEmptyState, type CustomModelEmptyState } from "./modelSelectorEmpty";
import { SectionTitle, SetupField, TextArea } from "./ui";

type RailItem = { value: string; title: string; meta?: string };
type QualityMode = "balanced" | "quality" | "speed";

export type RecommendedConfig = {
  qualityMode: "balanced" | "quality";
  enableWeb: boolean;
  enableAudit: boolean;
};

export function SetupPanel({
  knowledgeItems,
  templateItems,
  slug,
  template,
  qualityMode,
  generationBrief,
  enableWeb,
  enableAudit,
  enableVisualAudit,
  recommendedConfig,
  busy,
  customModels = [],
  modelOptions,
  modelChoices = {},
  onSlugChange,
  onTemplateChange,
  onQualityModeChange,
  onGenerationBriefChange,
  onToggleWeb,
  onToggleAudit,
  onToggleVisualAudit,
  onFormatOverridesChange,
  onModelChoiceChange,
}: {
  knowledgeItems: RailItem[];
  templateItems: RailItem[];
  slug: string;
  template: string;
  qualityMode: QualityMode;
  generationBrief: string;
  enableWeb: boolean;
  enableAudit: boolean;
  enableVisualAudit: boolean;
  recommendedConfig: RecommendedConfig | null;
  busy: boolean;
  customModels?: CustomModel[];
  modelOptions: ModelOptionsMap | null;
  modelChoices?: Record<string, string>;
  onSlugChange: (value: string) => void;
  onTemplateChange: (value: string) => void;
  onQualityModeChange: (value: QualityMode) => void;
  onGenerationBriefChange: (value: string) => void;
  onToggleWeb: (value: boolean) => void;
  onToggleAudit: (value: boolean) => void;
  onToggleVisualAudit: (value: boolean) => void;
  onFormatOverridesChange: (overrides: FormatOverrides) => void;
  onModelChoiceChange: (role: string, model: string) => void;
}) {
  const { t } = useI18n();
  const isLocked = busy;

  const advancedToggles = [
    { label: t("generate.enableWeb"), desc: t("generate.enableWebDesc"), value: enableWeb, onChange: onToggleWeb },
    { label: t("generate.enableAudit"), desc: t("generate.enableAuditDesc"), value: enableAudit, onChange: onToggleAudit },
    {
      label: t("generate.enableVisualAudit"),
      desc: t("generate.enableVisualAuditDesc"),
      value: enableVisualAudit,
      onChange: onToggleVisualAudit,
    },
  ];

  const modeLabels: Record<QualityMode, string> = {
    speed: t("generate.modeSpeed"),
    balanced: t("generate.modeBalanced"),
    quality: t("generate.modeQuality"),
  };
  const modeDescriptions: Record<QualityMode, string> = {
    speed: t("generate.modeSpeedDesc"),
    balanced: t("generate.modeBalancedDesc"),
    quality: t("generate.modeQualityDesc"),
  };

  const mainWriterOptions = flattenModelOptions(modelOptions?.main_writer);
  const fastWriterOptions = flattenModelOptions(modelOptions?.fast_writer);
  const auditOptions = flattenModelOptions(modelOptions?.audit_text);

  const mainWriterEmptyState = isLocked
    ? undefined
    : detectCustomModelEmptyState(mainWriterOptions, customModels);
  const fastWriterEmptyState = isLocked
    ? undefined
    : detectCustomModelEmptyState(fastWriterOptions, customModels);
  const auditEmptyState = isLocked
    ? undefined
    : detectCustomModelEmptyState(auditOptions, customModels);

  return (
    <Panel className="min-w-0">
      <SectionTitle icon={<Sparkles aria-hidden="true" size={20} />} title={t("generate.setupTitle")} hint={t("generate.setupHint")} />

      <div className="space-y-3 transition-all duration-200">
        <SetupField label={t("generate.knowledge")} compact={true}>
          <select
            className="min-h-11 w-full border border-white/10 bg-night-950/80 px-3 text-sm font-semibold text-white outline-none transition focus:border-signal-cyan/70 disabled:opacity-50"
            value={slug}
            onChange={(event) => onSlugChange(event.target.value)}
            disabled={isLocked || knowledgeItems.length === 0}
          >
            {knowledgeItems.length === 0 ? (
              <option value="">{t("generate.noKnowledge")}</option>
            ) : (
              knowledgeItems.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.title}
                </option>
              ))
            )}
          </select>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <span className="break-words">{slug || t("generate.noKnowledge")}</span>
            <Link to="/knowledge" className="font-semibold text-signal-cyan transition hover:text-white">
              {t("generate.goKnowledge")}
            </Link>
          </div>
        </SetupField>

        <SetupField label={t("generate.template")} compact={true}>
          <select
            className="min-h-11 w-full border border-white/10 bg-night-950/80 px-3 text-sm font-semibold text-white outline-none transition focus:border-signal-cyan/70 disabled:opacity-50"
            value={template}
            onChange={(event) => onTemplateChange(event.target.value)}
            disabled={isLocked || templateItems.length === 0}
          >
            {templateItems.length === 0 ? (
              <option value="">{t("generate.noTemplates")}</option>
            ) : (
              templateItems.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.title}
                </option>
              ))
            )}
          </select>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <span className="break-words">{template || t("generate.noTemplates")}</span>
            <Link to="/template" className="font-semibold text-signal-cyan transition hover:text-white">
              {t("generate.goTemplate")}
            </Link>
          </div>
        </SetupField>

        {recommendedConfig && !isLocked && (
          <div className="mb-2 flex items-start gap-2 border border-dashed border-signal-cyan/30 bg-signal-cyan/5 px-3 py-2.5 text-xs">
            <Sparkles aria-hidden="true" className="mt-0.5 shrink-0 text-signal-cyan" size={14} />
            <div className="min-w-0">
              <p className="font-semibold text-signal-cyan">{t("generate.smartDefaultsActive")}</p>
              <p className="mt-0.5 break-words text-slate-400">
                {recommendedConfig.qualityMode === "quality" ? t("generate.smartDefaultsQualityFirst") : t("generate.smartDefaultsBalanced")}
                {recommendedConfig.enableWeb ? t("generate.smartDefaultsWeb") : ""}
                {recommendedConfig.enableAudit ? t("generate.smartDefaultsAudit") : ""}
              </p>
            </div>
          </div>
        )}

        <SetupField label={t("generate.qualityMode")} compact={true}>
          <div className="grid grid-cols-3 gap-2">
            {(["speed", "balanced", "quality"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                disabled={isLocked}
                onClick={() => onQualityModeChange(mode)}
                className={clsx(
                  "border px-3 py-2.5 text-left transition hover:border-white/25 disabled:pointer-events-none disabled:opacity-45",
                  qualityMode === mode
                    ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
                    : "border-white/10 bg-night-950 text-slate-300",
                )}
              >
                <span className="block text-xs font-semibold">{modeLabels[mode]}</span>
                <span className="mt-0.5 block text-[10px] text-slate-500">{modeDescriptions[mode]}</span>
              </button>
            ))}
          </div>
        </SetupField>

        <FormatOverridesPanel 
          templateId={template} 
          onChange={onFormatOverridesChange}
          disabled={isLocked} 
        />

        {modelOptions && (
          <div className="space-y-3">
            <SetupField label={t("settings.modelChoices.main_writer")} compact={true}>
              <ModelSelector
                role="main_writer"
                icon={<Zap size={14} className="text-signal-cyan" />}
                options={mainWriterOptions}
                value={modelChoices.main_writer || ""}
                disabled={isLocked}
                emptyState={mainWriterEmptyState}
                t={t}
                onChange={onModelChoiceChange}
              />
            </SetupField>
            <SetupField label={t("settings.modelChoices.fast_writer")} compact={true}>
              <ModelSelector
                role="fast_writer"
                icon={<Sparkles size={14} className="text-signal-lime" />}
                options={fastWriterOptions}
                value={modelChoices.fast_writer || ""}
                disabled={isLocked}
                emptyState={fastWriterEmptyState}
                t={t}
                onChange={onModelChoiceChange}
              />
            </SetupField>
            {enableAudit && (
              <SetupField label={t("settings.modelChoices.audit_text")} compact={true}>
                <ModelSelector
                  role="audit_text"
                  icon={<ShieldCheck size={14} className="text-signal-amber" />}
                  options={auditOptions}
                  value={modelChoices.audit_text || ""}
                  disabled={isLocked}
                  emptyState={auditEmptyState}
                  t={t}
                  onChange={onModelChoiceChange}
                />
              </SetupField>
            )}
          </div>
        )}

        <details className="border border-white/10 bg-night-950/55 p-3">
          <summary className="cursor-pointer list-none text-xs font-semibold uppercase tracking-[0.12em] text-signal-cyan">
            {t("generate.advancedSettings")}
          </summary>
          <div className="space-y-2">
            {advancedToggles.map((item) => (
              <button
                key={item.label}
                type="button"
                disabled={isLocked}
                onClick={() => item.onChange(!item.value)}
                className={clsx(
                  "flex w-full items-center justify-between gap-3 border px-3 py-2.5 text-left transition hover:border-white/25 active:scale-[0.99] disabled:pointer-events-none disabled:opacity-45",
                  item.value
                    ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
                    : "border-white/10 bg-night-950 text-slate-300",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold">{item.label}</span>
                  <span className="mt-0.5 block text-[10px] text-slate-500">{item.desc}</span>
                </span>
                <span
                  className={clsx(
                    "flex h-5 w-9 shrink-0 items-center rounded-full border px-0.5 transition",
                    item.value ? "border-signal-cyan bg-signal-cyan/20" : "border-white/15 bg-white/[0.08]",
                  )}
                >
                  <span
                    className={clsx(
                      "h-3.5 w-3.5 rounded-full transition",
                      item.value ? "translate-x-3.5 bg-signal-cyan" : "translate-x-0 bg-slate-400",
                    )}
                  />
                </span>
              </button>
            ))}
          </div>
        </details>

        <SetupField label={t("generate.instructions")} compact={true}>
          <TextArea
            value={generationBrief}
            onChange={onGenerationBriefChange}
            placeholder={t("generate.instructionsPlaceholder")}
            compact={true}
            disabled={isLocked}
          />
          <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <span className="flex min-w-0 items-center gap-2">
              <MessageSquareText aria-hidden="true" className="shrink-0 text-signal-cyan" size={16} />
              <span className="break-words">{t("generate.instructionsHint")}</span>
            </span>
            <span className="shrink-0">{generationBrief.length}/1200</span>
          </div>
        </SetupField>
      </div>
    </Panel>
  );
}

function ModelSelector({
  role,
  icon,
  options,
  value,
  disabled,
  emptyState,
  t,
  onChange,
}: {
  role: string;
  icon: React.ReactNode;
  options: ModelOption[];
  value: string;
  disabled: boolean;
  emptyState?: CustomModelEmptyState;
  t: (key: string) => string;
  onChange: (role: string, model: string) => void;
}) {
  const warningKey =
    emptyState === "no_custom_models_global"
      ? "generate.noCustomModelsGlobal"
      : emptyState === "no_custom_models_for_role"
        ? "generate.noCustomModelsForRole"
        : null;

  return (
    <div className="relative">
      <div className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none">
        {icon}
      </div>
      <select
        className="min-h-11 w-full border border-white/10 bg-night-950/80 pl-9 pr-3 text-sm font-semibold text-white outline-none transition focus:border-signal-cyan/70 disabled:opacity-50"
        value={value}
        onChange={(e) => onChange(role, e.target.value)}
        disabled={disabled}
      >
        <option value="">{t("settings.modelChoices.default")}</option>
        {options.map((opt) => (
          <option key={opt.model} value={opt.model}>
            {opt.label || opt.model} {opt.provider_code === "custom" ? `[${t("settings.customModels.customBadge")}]` : ""}
          </option>
        ))}
      </select>
      {warningKey ? (
        <div className="mt-2 flex flex-wrap items-start gap-2 text-xs text-signal-amber">
          <AlertTriangle aria-hidden="true" size={14} className="mt-0.5 shrink-0" />
          <span className="min-w-0 flex-1 break-words">{t(warningKey)}</span>
          <Link to="/settings" className="shrink-0 font-semibold text-signal-cyan transition hover:text-white">
            {t("generate.goAssignRoles")}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
