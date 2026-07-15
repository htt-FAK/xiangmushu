/**
 * `<TestModelButton>` — button that triggers capability testing for a single model.
 *
 * @remarks
 * - Renders as a Button with dynamic label: "Test" when never tested or last test older than 5 minutes, "Re-test" when recently tested.
 * - State machine: idle, testing (spinner).
 * - Calls: `testModelCapabilities` to run text/vision/embedding probes.
 * - Integrates with: ModelCard (parent); invokes onTestComplete callback with TestResult.
 *
 * @example
 * ```tsx
 * import TestModelButton from "../components/TestModelButton";
 * <TestModelButton model={model} onTestComplete={handleTestComplete} />
 * ```
 *
 * @packageDocumentation
 * Part of the multi-custom-models feature (openspec change: multi-custom-models).
 */
import { Loader2, PlayCircle } from "lucide-react";
import { useState } from "react";
import { testModelCapabilities } from "../api";
import { Button } from "./ui";
import { useI18n } from "../i18n";
import type { CustomModel, TestResult } from "../types";

interface TestModelButtonProps {
  model: CustomModel;
  onTestComplete: (result: TestResult) => void;
}

export default function TestModelButton({ model, onTestComplete }: TestModelButtonProps) {
  const { t } = useI18n();
  const [testing, setTesting] = useState(false);

  const isRecentlyTested =
    model.last_tested_at &&
    Date.now() - new Date(model.last_tested_at).getTime() < 5 * 60 * 1000;

  async function handleTest() {
    setTesting(true);
    try {
      const result = await testModelCapabilities(model.id);
      onTestComplete(result);
    } catch (err) {
      console.error("Test failed", err);
    } finally {
      setTesting(false);
    }
  }

  return (
    <Button
      variant="ghost"
      onClick={handleTest}
      disabled={testing}
      className="gap-2"
    >
      {testing ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <PlayCircle size={14} />
      )}
      {isRecentlyTested
        ? t("settings.customModels.retest")
        : t("settings.customModels.test")}
    </Button>
  );
}
