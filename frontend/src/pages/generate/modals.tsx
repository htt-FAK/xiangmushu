import { Cpu, Layers3, Loader2, Play, Settings } from "lucide-react";
import { Button } from "../../components/ui";
import { useFocusTrap } from "../../hooks";
import type { CustomModel } from "../../types";
import type { QuotaAlertData } from "./useGenerationSession";
import { clsx } from "../../utils";

export function ConfirmModal({
  title,
  body,
  cancelLabel,
  confirmLabel,
  onCancel,
  onConfirm,
}: {
  title: string;
  body: string;
  cancelLabel: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const trapRef = useFocusTrap<HTMLDivElement>(true, onCancel);
  return (
    <div ref={trapRef} className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-night-950/90 px-4 py-6 backdrop-blur">
      <div className="w-full max-w-md border border-white/10 bg-night-900 p-5 shadow-panel md:p-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan">
            <Layers3 aria-hidden="true" size={19} />
          </div>
          <h3 className="font-display text-xl font-semibold text-white">{title}</h3>
        </div>
        <p className="text-sm leading-7 text-slate-300">{body}</p>
        <div className="mt-5 grid gap-3 sm:flex sm:justify-end">
          <Button className="min-h-12 w-full sm:w-auto" variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button className="min-h-12 w-full font-bold sm:w-auto" onClick={onConfirm}>
            <Play aria-hidden="true" size={16} />
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function QuotaSwitchModal({
  data,
  title,
  cancelLabel,
  saving,
  customModels = [],
  onSwitch,
  onCancel,
}: {
  data: QuotaAlertData;
  title: string;
  cancelLabel: string;
  saving: boolean;
  customModels?: CustomModel[];
  onSwitch: (model: string) => void;
  onCancel: () => void;
}) {
  const trapRef = useFocusTrap<HTMLDivElement>(true, onCancel);
  return (
    <div ref={trapRef} className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-night-950/90 px-4 py-6 backdrop-blur">
      <div className="w-full max-w-xl border border-rose-500/30 bg-night-900 p-5 shadow-panel md:p-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center border border-rose-500/40 bg-rose-500/10 text-rose-200">
            <Cpu aria-hidden="true" size={19} />
          </div>
          <h3 className="font-display text-xl font-semibold text-white">{title}</h3>
        </div>
        <p className="text-sm leading-7 text-slate-300">{data.message}</p>
        <div className="mt-5 grid gap-2">
          {data.available_models.map((model) => {
            const isCustom = customModels.some(m => m.default_model_id === model);
            return (
              <button
                key={model}
                type="button"
                onClick={() => onSwitch(model)}
                disabled={saving}
                className={clsx(
                  "flex items-center justify-between gap-3 border px-3 py-3 text-left transition disabled:opacity-60",
                  isCustom 
                    ? "border-signal-cyan/30 bg-night-900 text-cyan-50 hover:border-signal-cyan/60" 
                    : "border-white/10 bg-night-950 text-slate-300 hover:border-white/25 hover:text-white"
                )}
              >
                <span className="flex min-w-0 items-center gap-2">
                  {isCustom && <Settings size={14} className="shrink-0 text-signal-cyan" />}
                  <span className="block min-w-0 break-all text-sm font-semibold">{model}</span>
                  {isCustom && (
                    <span className="ml-1 bg-signal-cyan/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-signal-cyan">
                      No quota limit
                    </span>
                  )}
                </span>
                {saving ? (
                  <Loader2 aria-hidden="true" className="shrink-0 animate-spin" size={16} />
                ) : (
                  <Cpu aria-hidden="true" className="shrink-0" size={16} />
                )}
              </button>
            );
          })}
        </div>
        <div className="mt-5 grid gap-3 sm:flex sm:justify-end">
          <Button className="min-h-12 w-full sm:w-auto" variant="ghost" onClick={onCancel} disabled={saving}>
            {cancelLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
