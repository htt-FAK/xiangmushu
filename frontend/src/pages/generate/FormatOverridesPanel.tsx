import { AlertTriangle, ChevronDown, Info, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { clsx } from "../../utils";
import { SetupField } from "./ui";

export interface FormatOverrides {
  body_font_ascii?: string;
  body_font_east_asia?: string;
  body_size_pt?: number;
  body_bold?: boolean;
  heading_size_delta_pt?: number;
  line_spacing?: number;
  first_line_indent_pt?: number;
}

interface FormatOverridesPanelProps {
  templateId: string;
  onChange: (overrides: FormatOverrides) => void;
  disabled?: boolean;
}

const FONTS = ["宋体", "黑体", "楷体", "仿宋", "微软雅黑"];
const LINE_SPACINGS = [1.0, 1.25, 1.5, 2.0];

export function FormatOverridesPanel({ templateId, onChange, disabled }: FormatOverridesPanelProps) {
  const { t } = useI18n();
  const storageKey = `format_prefs_${templateId}`;

  const [overrides, setOverrides] = useState<FormatOverrides>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    const cleanOverrides = Object.fromEntries(
      Object.entries(overrides).filter(([_, v]) => v !== undefined && v !== "")
    );
    onChange(cleanOverrides);
    if (Object.keys(cleanOverrides).length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(cleanOverrides));
    } else {
      localStorage.removeItem(storageKey);
    }
  }, [overrides, storageKey, onChange]);

  const updateField = (field: keyof FormatOverrides, value: any) => {
    setOverrides((prev) => ({ ...prev, [field]: value }));
  };

  const reset = () => {
    setOverrides({});
  };

  return (
    <details className="border border-white/10 bg-night-950/55 p-3 group">
      <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold uppercase tracking-[0.12em] text-signal-cyan">
        <span>{t("generate.formatSettings")}</span>
        <ChevronDown size={14} className="transition-transform group-open:rotate-180" />
      </summary>
      
      <div className="mt-4 space-y-4">
        <div className="flex items-start gap-2 border border-signal-cyan/20 bg-signal-cyan/5 p-2 text-[10px] text-cyan-100/70">
          <Info size={14} className="shrink-0 text-signal-cyan" />
          <p>{t("generate.formatSettingsHint")}</p>
        </div>

        <SetupField label={t("generate.bodyFont")} compact={true}>
          <select
            className="min-h-10 w-full border border-white/10 bg-night-950/80 px-3 text-xs font-semibold text-white outline-none transition focus:border-signal-cyan/70 disabled:opacity-50"
            value={overrides.body_font_east_asia || ""}
            onChange={(e) => updateField("body_font_east_asia", e.target.value)}
            disabled={disabled}
          >
            <option value="">{t("generate.templateDefault")}</option>
            {FONTS.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </SetupField>

        <SetupField label={`${t("generate.bodySize")} (${overrides.body_size_pt || 12}pt)`} compact={true}>
          <input
            type="range"
            min="10"
            max="18"
            step="0.5"
            className="w-full accent-signal-cyan"
            value={overrides.body_size_pt || 12}
            onChange={(e) => updateField("body_size_pt", parseFloat(e.target.value))}
            disabled={disabled}
          />
          <div className="mt-1 flex justify-between text-[10px] text-slate-500">
            <span>10pt</span>
            <span>18pt</span>
          </div>
        </SetupField>

        <SetupField label={t("generate.lineSpacing")} compact={true}>
          <div className="grid grid-cols-4 gap-2">
            {LINE_SPACINGS.map((val) => (
              <button
                key={val}
                type="button"
                disabled={disabled}
                onClick={() => updateField("line_spacing", val)}
                className={clsx(
                  "border py-1.5 text-xs transition active:scale-[0.98]",
                  overrides.line_spacing === val
                    ? "border-signal-cyan bg-signal-cyan/10 text-signal-cyan"
                    : "border-white/10 bg-night-950 text-slate-400"
                )}
              >
                {val.toFixed(1)}
              </button>
            ))}
          </div>
        </SetupField>

        <button
          type="button"
          onClick={reset}
          disabled={disabled || Object.keys(overrides).length === 0}
          className="flex w-full items-center justify-center gap-2 border border-white/10 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 transition hover:bg-white/5 disabled:opacity-30"
        >
          <RotateCcw size={12} />
          {t("generate.resetToDefault")}
        </button>
      </div>
    </details>
  );
}
