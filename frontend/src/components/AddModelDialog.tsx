/**
 * `<AddModelDialog>` — modal form for creating or editing a custom model.
 *
 * @remarks
 * - Renders as a DetailOverlay with form fields: name, base_url, model_id (comma-separated hint), api_key (password input), default_model_id (dropdown from parsed model IDs).
 * - State machine: form input (validation), saving (spinner), error (inline banner).
 * - Calls: `createCustomModel` for new entries, `updateCustomModel` for edits.
 * - Integrates with: CustomModelsManager (opens/closes dialog, receives saved model callback).
 *
 * @example
 * ```tsx
 * import AddModelDialog from "../components/AddModelDialog";
 * <AddModelDialog open={dialogOpen} editingModel={editingModel} onClose={closeDialog} onSaved={handleSaved} />
 * ```
 *
 * @packageDocumentation
 * Part of the multi-custom-models feature (openspec change: multi-custom-models).
 */
import { Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { createCustomModel, updateCustomModel } from "../api";
import { Button, DetailOverlay, ErrorBanner, Field, Input } from "./ui";
import { useI18n } from "../i18n";
import type { CustomModel } from "../types";

interface AddModelDialogProps {
  open: boolean;
  editingModel: CustomModel | null;
  onClose: () => void;
  onSaved: (model: CustomModel) => void;
}

interface FormState {
  name: string;
  base_url: string;
  model_id: string;
  api_key: string;
  default_model_id: string;
}

const INITIAL_FORM: FormState = {
  name: "",
  base_url: "",
  model_id: "",
  api_key: "",
  default_model_id: "",
};

export default function AddModelDialog({
  open,
  editingModel,
  onClose,
  onSaved,
}: AddModelDialogProps) {
  const { t } = useI18n();
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (editingModel) {
      setForm({
        name: editingModel.name,
        base_url: editingModel.base_url,
        model_id: editingModel.model_id,
        api_key: "",
        default_model_id: editingModel.default_model_id,
      });
    } else {
      setForm(INITIAL_FORM);
    }
    setError("");
  }, [editingModel, open]);

  const modelOptions = form.model_id
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  function validate() {
    if (!form.name.trim()) return t("settings.customModels.errorNameRequired");
    if (!form.base_url.trim()) return t("settings.customModels.errorUrlRequired");
    try {
      new URL(form.base_url);
    } catch {
      return t("settings.customModels.errorUrlInvalid");
    }
    if (!form.model_id.trim()) return t("settings.customModels.errorModelIdRequired");
    if (!editingModel && !form.api_key.trim()) return t("settings.customModels.errorKeyRequired");
    if (form.api_key && form.api_key.length < 8) return t("settings.customModels.errorKeyTooShort");
    if (!form.default_model_id && modelOptions.length > 0) return t("settings.customModels.errorDefaultRequired");
    return null;
  }

  async function handleSave() {
    const err = validate();
    if (err) {
      setError(err);
      return;
    }

    setSaving(true);
    setError("");
    try {
      if (editingModel) {
        const updatePayload: Record<string, string> = {
          name: form.name.trim(),
          base_url: form.base_url.trim(),
          model_id: form.model_id.trim(),
        };
        if (form.default_model_id) updatePayload.default_model_id = form.default_model_id;
        if (form.api_key.trim()) updatePayload.api_key = form.api_key.trim();
        const saved = await updateCustomModel(editingModel.id, updatePayload);
        onSaved(saved);
      } else {
        const saved = await createCustomModel({
          name: form.name.trim(),
          base_url: form.base_url.trim(),
          model_id: form.model_id.trim(),
          api_key: form.api_key.trim(),
          default_model_id: form.default_model_id || undefined,
        });
        onSaved(saved);
      }
      
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <DetailOverlay
      title={editingModel ? t("settings.customModels.editTitle") : t("settings.customModels.addTitle")}
      onClose={onClose}
    >
      <div className="space-y-4">
        <ErrorBanner message={error} />
        
        <Field label={t("settings.customModels.nameLabel")}>
          <Input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={t("settings.customModels.namePlaceholder")}
          />
        </Field>

        <Field label={t("settings.customModels.baseUrlLabel")}>
          <Input
            value={form.base_url}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            placeholder="https://api.openai.com/v1"
          />
        </Field>

        <Field label={t("settings.customModels.modelIdLabel")}>
          <Input
            value={form.model_id}
            onChange={(e) => {
              const val = e.target.value;
              const options = val.split(",").map(s => s.trim()).filter(Boolean);
              setForm({ 
                ...form, 
                model_id: val,
                default_model_id: options.includes(form.default_model_id) ? form.default_model_id : (options[0] || "")
              });
            }}
            placeholder="gpt-4o, gpt-4-turbo"
          />
          <p className="mt-1 text-xs text-slate-500">{t("settings.customModels.modelIdHint")}</p>
        </Field>

        {modelOptions.length > 0 && (
          <Field label={t("settings.customModels.defaultModelLabel")}>
            <select
              value={form.default_model_id}
              onChange={(e) => setForm({ ...form, default_model_id: e.target.value })}
              className="min-h-12 w-full border border-white/10 bg-night-950 px-3 text-sm text-white outline-none focus:border-signal-cyan/70"
            >
              {modelOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </Field>
        )}

        <Field label={t("settings.customModels.apiKeyLabel")}>
          <Input
            type="password"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            placeholder={editingModel ? t("settings.customModels.keyPlaceholderKeep") : t("settings.customModels.keyPlaceholder")}
          />
        </Field>

        <div className="flex gap-3 pt-6">
          <Button
            variant="primary"
            className="flex-1"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {t("common.save")}
          </Button>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            {t("common.cancel")}
          </Button>
        </div>
      </div>
    </DetailOverlay>
  );
}
