import { detectCustomModelEmptyState } from "./modelSelectorEmpty";
import type { CustomModel, ModelOption } from "../../types";

type TestFn = () => void | Promise<void>;

interface TestCase {
  readonly suite: string;
  readonly name: string;
  readonly fn: TestFn;
}

const cases: TestCase[] = [];
let currentSuite = "";

function describe(name: string, fn: () => void): void {
  currentSuite = name;
  fn();
}

function it(name: string, fn: TestFn): void {
  cases.push({ suite: currentSuite, name, fn });
}

function expect<T>(actual: T) {
  return {
    toBe(expected: T): void {
      if (actual !== expected) {
        throw new Error(`Expected ${String(expected)}, got ${String(actual)}`);
      }
    },
  };
}

const CUSTOM_MODEL = {
  id: 1,
  user_id: 7,
  name: "My Custom Writer",
  base_url: "https://api.example.com/v1",
  model_id: "my-custom-writer",
  default_model_id: "my-custom-writer",
  capabilities: ["text"],
  assigned_roles: ["text-gen"],
  status: "validated",
  last_tested_at: null,
  last_error: null,
  api_key_preview: "sk-****",
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
} satisfies CustomModel;

describe("detectCustomModelEmptyState", () => {
  it("returns has_options when at least one custom option is selectable", () => {
    const options = [
      { model: "qwen3.7-plus", provider_code: "dashscope" },
      { model: "my-custom-writer", provider_code: "custom" },
    ] satisfies readonly ModelOption[];

    expect(detectCustomModelEmptyState(options, [CUSTOM_MODEL])).toBe("has_options");
  });

  it("returns no_custom_models_global when user has no custom models", () => {
    const options = [{ model: "qwen3.7-plus", provider_code: "dashscope" }] satisfies readonly ModelOption[];
    expect(detectCustomModelEmptyState(options, [])).toBe("no_custom_models_global");
  });

  it("returns no_custom_models_for_role when custom models exist but no custom option is selectable", () => {
    const options = [{ model: "qwen3.7-plus", provider_code: "dashscope" }] satisfies readonly ModelOption[];
    expect(detectCustomModelEmptyState(options, [CUSTOM_MODEL])).toBe("no_custom_models_for_role");
  });

  it("returns no_custom_models_for_role when options are empty but custom models exist", () => {
    expect(detectCustomModelEmptyState([], [CUSTOM_MODEL])).toBe("no_custom_models_for_role");
  });

  it("returns has_options when options contain mixed built-in and custom models", () => {
    const options = [
      { model: "qwen3.7-plus", provider_code: "dashscope" },
      { model: "my-custom-writer", provider_code: "custom" },
      { model: "deepseek-chat", provider_code: "deepseek" },
    ] satisfies readonly ModelOption[];

    expect(detectCustomModelEmptyState(options, [CUSTOM_MODEL])).toBe("has_options");
  });
});

let passed = 0;
let failed = 0;

async function run(): Promise<void> {
  for (const testCase of cases) {
    try {
      await testCase.fn();
      passed += 1;
      console.log(`  ✓ ${testCase.suite} › ${testCase.name}`);
    } catch (error) {
      failed += 1;
      console.error(`  ✗ ${testCase.suite} › ${testCase.name}:`, error);
    }
  }
  console.log(`\n  ${passed} passed, ${failed} failed`);
}

declare const process: { argv: string[] } | undefined;

if (
  typeof process !== "undefined" &&
  process.argv[1]?.includes("modelSelectorEmpty.test")
) {
  void run();
}

export { failed, passed, run };
