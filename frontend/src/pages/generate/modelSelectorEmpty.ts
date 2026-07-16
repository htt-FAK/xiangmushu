import type { CustomModel, ModelOption } from "../../types";

export type CustomModelEmptyState =
  | "has_options"
  | "no_custom_models_global"
  | "no_custom_models_for_role";

export function detectCustomModelEmptyState(
  options: readonly ModelOption[],
  customModels: readonly CustomModel[],
): CustomModelEmptyState {
  if (options.some((item) => item.provider_code === "custom")) {
    return "has_options";
  }
  if (customModels.length === 0) {
    return "no_custom_models_global";
  }
  return "no_custom_models_for_role";
}
