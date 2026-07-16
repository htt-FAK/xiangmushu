import type { ApiKeyStatus, ModelModuleConfig, ModelOption } from "./types";

/**
 * Flatten a model module config into a de-duplicated list of options,
 * preserving tier order first and then loose `options`.
 */
export function flattenModelOptions(config?: ModelModuleConfig): ModelOption[] {
  const out: ModelOption[] = [];
  const seen = new Set<string>();
  for (const group of Object.values(config?.tiers ?? {})) {
    for (const item of group) {
      const identity = String(item.value || item.model || "").trim();
      if (!item.model || !identity || seen.has(identity)) continue;
      seen.add(identity);
      out.push(item);
    }
  }
  for (const item of config?.options ?? []) {
    const identity = String(item.value || item.model || "").trim();
    if (!item.model || !identity || seen.has(identity)) continue;
    seen.add(identity);
    out.push(item);
  }
  return out;
}

/**
 * Pick the best model from a flattened option list:
 * keep `current` if still valid, otherwise the recommended one, otherwise the
 * first option. Falls back to `current` only when `fallbackToCurrent` is true.
 */
export function pickModel(options: ModelOption[], current = "", fallbackToCurrent = false): string {
  if (
    current &&
    options.some((item) => String(item.value || item.model || "") === current)
  ) {
    return current;
  }
  return (
    options.find((item) => item.recommended)?.value ||
    options.find((item) => item.recommended)?.model ||
    options[0]?.value ||
    options[0]?.model ||
    (fallbackToCurrent ? current : "")
  );
}

/** Convenience wrapper resolving the preferred model directly from a config. */
export function preferredModel(config?: ModelModuleConfig, current = ""): string {
  return pickModel(flattenModelOptions(config), current, true);
}

export function providerCodeForModel(modelId: string): string {
  const value = String(modelId || "").trim().toLowerCase();
  if (!value) return "dashscope";
  if (value.startsWith("custom:")) return "custom";
  if (value.startsWith("builtin:")) {
    const raw = value.slice("builtin:".length);
    if (raw.startsWith("deepseek")) return "deepseek";
    if (raw.startsWith("mimo-")) return "mimo";
    return "dashscope";
  }
  if (value.startsWith("deepseek")) return "deepseek";
  if (value.startsWith("mimo-")) return "mimo";
  return "dashscope";
}

export function hasValidatedProvider(status: ApiKeyStatus | null | undefined, providerCode: string): boolean {
  const item = status?.providers?.[providerCode];
  return Boolean(item?.has_key && item?.validated);
}

export function hasAnyValidatedProvider(status: ApiKeyStatus | null | undefined): boolean {
  return Object.values(status?.providers ?? {}).some((item) => Boolean(item?.has_key && item?.validated));
}

export function hasValidatedModelProvider(
  status: ApiKeyStatus | null | undefined,
  selectedModels: Array<string | null | undefined>,
): boolean {
  const models = selectedModels.map((item) => String(item || "").trim()).filter(Boolean);
  if (models.length === 0) {
    return hasAnyValidatedProvider(status);
  }
  return models.some((model) => hasValidatedProvider(status, providerCodeForModel(model)));
}
