/**
 * `<CustomModelsManager>` — top-level container for managing multiple custom AI models.
 *
 * @remarks
 * - Renders as a Panel integrated into SettingsPage, replacing the deprecated CustomAuditModelCard.
 * - State machine: model list (loading/error/loaded), dialog (add/edit), test result panel visibility.
 * - Calls: `fetchCustomModels`, `createCustomModel`, `updateCustomModel`, `deleteCustomModel` via child components.
 * - Integrates with: SettingsPage as the entry point for custom model CRUD, testing, and role assignment.
 *
 * @example
 * ```tsx
 * import CustomModelsManager from "../components/CustomModelsManager";
 * <CustomModelsManager />
 * ```
 *
 * @packageDocumentation
 * Part of the multi-custom-models feature (openspec change: multi-custom-models).
 */
import { Plus, Settings2 } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchCustomModels } from "../api";
import { Button, Panel } from "./ui";
import { useI18n } from "../i18n";
import ModelList from "./ModelList";
import AddModelDialog from "./AddModelDialog";
import TestResultPanel from "./TestResultPanel";
import type { CustomModel, TestResult } from "../types";

export default function CustomModelsManager() {
  const { t } = useI18n();
  const [models, setModels] = useState<CustomModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<CustomModel | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  async function loadModels() {
    setLoading(true);
    try {
      const data = await fetchCustomModels();
      setModels(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadModels();
  }, []);

  function handleAdd() {
    setEditingModel(null);
    setDialogOpen(true);
  }

  function handleEdit(model: CustomModel) {
    setEditingModel(model);
    setDialogOpen(true);
  }

  function handleModelSaved() {
    void loadModels();
    setDialogOpen(false);
  }

  return (
    <div className="space-y-6">
      {error && (
        <Panel className="border-signal-rose/50 bg-signal-rose/10 p-4 text-signal-rose">
          {error}
        </Panel>
      )}
      <Panel className="mb-6">
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="break-words font-display text-xl font-semibold text-white md:text-2xl">
                {t("settings.customModels.title")}
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                {t("settings.customModels.description")}
              </p>
            </div>
            <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-signal-cyan/40 bg-signal-cyan/12 text-signal-cyan">
              <Settings2 size={20} />
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-white/10 pt-4">
            <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              {models.length} {t("settings.customModels.countSuffix")}
            </span>
            <Button onClick={handleAdd} className="h-9 px-4">
              <Plus size={16} />
              {t("settings.customModels.addButton")}
            </Button>
          </div>
        </div>
      </Panel>

      <ModelList
        models={models}
        loading={loading}
        onEdit={handleEdit}
        onDelete={loadModels}
        onTestComplete={setTestResult}
        onAddFirst={handleAdd}
      />

      <AddModelDialog
        open={dialogOpen}
        editingModel={editingModel}
        onClose={() => setDialogOpen(false)}
        onSaved={handleModelSaved}
      />

      {testResult && (
        <TestResultPanel
          result={testResult}
          onAcceptSuggestions={() => {
            void loadModels();
            setTestResult(null);
          }}
          onRetry={() => {
            // In a real app, we might trigger a specific model test again.
            // For now, closing and letting the user click test again is sufficient.
            setTestResult(null);
          }}
          onClose={() => setTestResult(null)}
        />
      )}
    </div>
  );
}
