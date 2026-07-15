/**
 * `<ModelList>` — renders the array of custom models as sortable cards.
 *
 * @remarks
 * - Renders as a list of ModelCard components inside the CustomModelsManager panel.
 * - State machine: loading (skeleton placeholders) vs. loaded (cards) vs. empty (CTA state).
 * - Calls: delegates edit/delete/test callbacks to parent (CustomModelsManager).
 * - Integrates with: CustomModelsManager; displays EmptyState when no models exist.
 *
 * @example
 * ```tsx
 * import ModelList from "../components/ModelList";
 * <ModelList models={models} loading={false} onEdit={handleEdit} onDelete={handleDelete} onTestComplete={handleTest} onAddFirst={handleAddFirst} />
 * ```
 *
 * @packageDocumentation
 * Part of the multi-custom-models feature (openspec change: multi-custom-models).
 */
import { Plus } from "lucide-react";
import ModelCard from "./ModelCard";
import { EmptyState } from "./ui";
import { useI18n } from "../i18n";
import type { CustomModel, TestResult } from "../types";

interface ModelListProps {
  models: CustomModel[];
  loading: boolean;
  onEdit: (model: CustomModel) => void;
  onDelete: () => void;
  onTestComplete: (result: TestResult) => void;
  onAddFirst: () => void;
}

export default function ModelList({
  models,
  loading,
  onEdit,
  onDelete,
  onTestComplete,
  onAddFirst,
}: ModelListProps) {
  const { t } = useI18n();

  const sortedModels = [...models].sort((a, b) => {
    // Tested (validated) first
    if (a.status === "validated" && b.status !== "validated") return -1;
    if (a.status !== "validated" && b.status === "validated") return 1;
    // Then by name
    return a.name.localeCompare(b.name);
  });

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-[240px] animate-pulse border border-white/10 bg-white/[0.02]"
          />
        ))}
      </div>
    );
  }

  if (sortedModels.length === 0) {
    return (
      <div className="py-6">
        <EmptyState
          title={t("settings.customModels.emptyTitle")}
          body={t("settings.customModels.emptyBody")}
        />
        <div className="mt-6 flex justify-center">
          <button
            onClick={onAddFirst}
            className="flex items-center gap-2 border border-signal-cyan/40 bg-signal-cyan/10 px-6 py-3 text-sm font-bold uppercase tracking-wider text-signal-cyan transition hover:bg-signal-cyan/20"
          >
            <Plus size={18} />
            {t("settings.customModels.addFirst")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {sortedModels.map((model) => (
        <ModelCard
          key={model.id}
          model={model}
          onEdit={() => onEdit(model)}
          onDelete={onDelete}
          onTestComplete={onTestComplete}
        />
      ))}
    </div>
  );
}
