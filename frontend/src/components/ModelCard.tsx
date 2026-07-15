/**
 * `<ModelCard>` — per-model display card showing info, capabilities, roles, and actions.
 *
 * @remarks
 * - Renders as a Panel card within the ModelList, showing name, base URL (truncated), model IDs, capability badges (green=supported, gray=untested), role badges, and status indicator.
 * - State machine: idle, confirm-delete (modal), deleting (spinner).
 * - Calls: `deleteCustomModel` for deletion; delegates test/edit callbacks to parent.
 * - Integrates with: ModelList (parent); uses TestModelButton for capability testing.
 *
 * @example
 * ```tsx
 * import ModelCard from "../components/ModelCard";
 * <ModelCard model={model} onEdit={handleEdit} onDelete={handleDelete} onTestComplete={handleTest} />
 * ```
 *
 * @packageDocumentation
 * Part of the multi-custom-models feature (openspec change: multi-custom-models).
 */
import { Cog, Edit2, KeyRound, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteCustomModel } from "../api";
import { Button, Panel } from "./ui";
import { useI18n } from "../i18n";
import TestModelButton from "./TestModelButton";
import type { CustomModel, TestResult } from "../types";

interface ModelCardProps {
  model: CustomModel;
  onEdit: () => void;
  onDelete: () => void;
  onTestComplete: (result: TestResult) => void;
}

export default function ModelCard({
  model,
  onEdit,
  onDelete,
  onTestComplete,
}: ModelCardProps) {
  const { t } = useI18n();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteCustomModel(model.id);
      onDelete();
    } catch (err) {
      console.error("Delete failed", err);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  const statusLabel = ({
    validated: t("settings.customModels.statusValidated"),
    tested: t("settings.customModels.statusTested"),
    override: t("settings.customModels.statusOverride"),
    active: t("settings.customModels.statusTested"),
    untested: t("settings.customModels.statusUntested"),
    failed: t("settings.customModels.statusUntested"),
  } as Record<string, string>)[model.status] || model.status;

  const statusToneClass = {
    validated: "border-signal-lime/30 bg-signal-lime/10 text-signal-lime",
    tested: "border-signal-lime/30 bg-signal-lime/10 text-signal-lime",
    failed: "border-signal-rose/30 bg-signal-rose/10 text-signal-rose",
    untested: "border-white/10 bg-white/[0.025] text-slate-400",
    override: "border-signal-amber/30 bg-signal-amber/10 text-signal-amber",
    active: "border-signal-cyan/30 bg-signal-cyan/10 text-signal-cyan",
  }[model.status] || "border-white/10 bg-white/[0.025] text-slate-400";

  return (
    <Panel className="group relative border-night-700/60 transition-all hover:border-signal-cyan/40">
      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate font-display text-lg font-semibold text-white">
                {model.name}
              </h3>
              <div
                className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${statusToneClass}`}
              >
                {statusLabel}
              </div>
            </div>
            <p className="mt-1 truncate font-mono text-xs text-slate-500">
              {model.base_url.replace(/^https?:\/\//, "").slice(0, 40)}
              {model.base_url.length > 40 && "..."}
            </p>
          </div>
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-white/10 bg-night-950 text-slate-500 group-hover:text-signal-cyan">
            <Cog size={20} />
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-2 gap-4 border-y border-white/5 py-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Model ID
            </p>
            <p className="mt-1 truncate font-mono text-xs text-slate-300">
              {model.model_id}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Default ID
            </p>
            <p className="mt-1 truncate font-mono text-xs text-signal-cyan">
              {model.default_model_id}
            </p>
          </div>
        </div>

        {/* Badges */}
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {["text", "vision", "embedding"].map((cap) => {
              const hasCap = model.capabilities.includes(cap);
              return (
                <span
                  key={cap}
                  className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
                    hasCap
                      ? "border-signal-lime/40 bg-signal-lime/10 text-signal-lime"
                      : "border-white/5 bg-white/[0.02] text-slate-600"
                  }`}
                >
                  {cap}
                </span>
              );
            })}
          </div>
          {model.assigned_roles.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {model.assigned_roles.map((role) => (
                <span
                  key={role}
                  className="border border-signal-cyan/40 bg-signal-cyan/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-signal-cyan"
                >
                  {role}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center gap-2 pt-2">
          <TestModelButton model={model} onTestComplete={onTestComplete} />
          <Button variant="ghost" className="h-9 px-3" onClick={onEdit}>
            <Edit2 size={14} />
          </Button>
          <Button
            variant="danger"
            className="h-9 px-3"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 size={14} />
          </Button>
          {model.api_key_preview && (
            <div className="ml-auto flex items-center gap-1.5 font-mono text-[10px] text-slate-500">
              <KeyRound size={12} />
              {model.api_key_preview}
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {confirmDelete && (
        <dialog open className="fixed inset-0 z-[60] flex h-full w-full items-center justify-center bg-night-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm border border-signal-rose/30 bg-night-900 p-6 shadow-2xl">
            <h4 className="font-display text-lg font-bold text-white">
              {t("settings.customModels.deleteConfirmTitle")}
            </h4>
            <p className="mt-2 text-sm text-slate-400">
              {t("settings.customModels.deleteConfirmBody", model.name)}
            </p>
            <div className="mt-6 flex gap-3">
              <Button
                variant="danger"
                className="flex-1"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Trash2 size={16} />
                )}
                {t("common.delete")}
              </Button>
              <Button
                variant="ghost"
                className="flex-1"
                onClick={() => setConfirmDelete(false)}
                disabled={deleting}
              >
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        </dialog>
      )}
    </Panel>
  );
}
