/**
 * Skeleton tests for the custom-models API client functions.
 *
 * Uses ``global.fetch`` mocking (no vitest/jest dependency). Each test
 * replaces ``globalThis.fetch`` with a stub that returns a predefined
 * ``Response``, then calls the corresponding API function and asserts the
 * shape of the resolved / rejected value.
 *
 * Task 6.10 — acceptance: all error types handled; typed errors accessible;
 * structured responses verified.
 */

import type {
  AssignRolesResponse,
  CreateCustomModelRequest,
  CustomModel,
  CustomModelError,
  TestResult,
} from "../types";

// ── Minimal test scaffolding (self-contained; no external deps) ──────────────

type TestFn = () => void | Promise<void>;

interface TestCase {
  suite: string;
  name: string;
  fn: TestFn;
}

const _cases: TestCase[] = [];
let _currentSuite = "";

function describe(name: string, fn: () => void): void {
  _currentSuite = name;
  fn();
}

function it(name: string, fn: TestFn): void {
  _cases.push({ suite: _currentSuite, name, fn });
}

function expect<T>(actual: T) {
  return {
    toBe(expected: T): void {
      if (actual !== expected) {
        throw new Error(`Expected ${String(expected)}, got ${String(actual)}`);
      }
    },
    toEqual(expected: T): void {
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        throw new Error(
          `Deep equal failed.\nExpected: ${JSON.stringify(expected)}\nActual:   ${JSON.stringify(actual)}`,
        );
      }
    },
    toBeTruthy(): void {
      if (!actual) throw new Error(`Expected truthy, got ${String(actual)}`);
    },
    toBeDefined(): void {
      if (actual === undefined) throw new Error(`Expected defined value`);
    },
    toBeGreaterThan(n: number): void {
      if (!(Number(actual) > n)) {
        throw new Error(`Expected > ${n}, got ${String(actual)}`);
      }
    },
    rejects: {
      async toThrow(): Promise<void> {
        try {
          await (actual as unknown as Promise<unknown>);
          throw new Error("Expected promise to reject, but it resolved");
        } catch (err) {
          if (err instanceof Error && err.message === "Expected promise to reject, but it resolved") {
            throw err;
          }
          // Expected rejection — swallow
        }
      },
    },
  };
}

// ── Fetch mock helpers ───────────────────────────────────────────────────────

const _originalFetch = globalThis.fetch;

function mockFetch(response: Response): void {
  globalThis.fetch = (() => Promise.resolve(response)) as typeof globalThis.fetch;
}

function restoreFetch(): void {
  globalThis.fetch = _originalFetch;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function emptyResponse(status = 204): Response {
  return new Response(null, { status });
}

// ── Fixtures ─────────────────────────────────────────────────────────────────

const SAMPLE_MODEL: CustomModel = {
  id: 1,
  user_id: 42,
  name: "Test Model",
  base_url: "https://api.example.com",
  model_id: "test-model",
  default_model_id: "test-model",
  capabilities: ["text"],
  assigned_roles: ["text-gen"],
  status: "validated",
  last_tested_at: "2026-07-14T00:00:00Z",
  last_error: null,
  api_key_preview: "sk-t...st",
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z",
};

const SAMPLE_CREATE_REQ: CreateCustomModelRequest = {
  name: "New Model",
  base_url: "https://api.example.com",
  model_id: "new-model",
  api_key: "sk-test-key-12345678",
};

const SAMPLE_TEST_RESULT: TestResult = {
  id: 1,
  capabilities: ["text"],
  status: "tested",
  last_tested_at: "2026-07-14T00:00:00Z",
  last_error: null,
  suggested_roles: ["text-gen", "audit"],
  test_results: {
    text: { passed: true, latency_ms: 120, detail: null },
  },
};

const SAMPLE_ASSIGN_RESPONSE: AssignRolesResponse = {
  id: 1,
  name: "Test Model",
  assigned_roles: ["text-gen"],
  default_model_id: "test-model",
  capabilities: ["text"],
  warnings: [],
};

// ── Stub the DOM environment minimally for api.ts imports ─────────────────────

// api.ts calls clearStoredToken + window.location on 401.
// For testing, we patch the module surface without executing real DOM code.
// The API functions we test below do NOT trigger 401 paths in the happy case.

// ── Tests ────────────────────────────────────────────────────────────────────

describe("custom models API client", () => {
  // -- fetchCustomModels --

  it("fetchCustomModels on 200 returns array", async () => {
    mockFetch(jsonResponse({ models: [SAMPLE_MODEL] }, 200));
    // We import lazily to avoid side-effects at module-level
    const { fetchCustomModels } = await import("../api");
    const result = await fetchCustomModels();
    expect(Array.isArray(result)).toBeTruthy();
    expect(result.length).toBe(1);
    expect(result[0].id).toBe(1);
    restoreFetch();
  });

  it("fetchCustomModels on empty list returns []", async () => {
    mockFetch(jsonResponse({ models: [] }, 200));
    const { fetchCustomModels } = await import("../api");
    const result = await fetchCustomModels();
    expect(result.length).toBe(0);
    restoreFetch();
  });

  // -- createCustomModel --

  it("createCustomModel on 201 returns saved model", async () => {
    mockFetch(jsonResponse(SAMPLE_MODEL, 201));
    const { createCustomModel } = await import("../api");
    const result = await createCustomModel(SAMPLE_CREATE_REQ);
    expect(result.id).toBe(1);
    expect(result.name).toBe("Test Model");
    restoreFetch();
  });

  it("createCustomModel on 422 throws Error with customModelError", async () => {
    const errorBody: { error: CustomModelError } = {
      error: { code: "name_required", message: "Name is required" },
    };
    mockFetch(jsonResponse(errorBody, 422));
    const { createCustomModel } = await import("../api");
    try {
      await createCustomModel({ ...SAMPLE_CREATE_REQ, name: "" });
      throw new Error("Expected rejection");
    } catch (err) {
      const customErr = (err as Error & { customModelError?: CustomModelError })
        .customModelError;
      expect(customErr?.code).toBe("name_required");
    }
    restoreFetch();
  });

  // -- deleteCustomModel --

  it("deleteCustomModel on 204 resolves without throwing", async () => {
    mockFetch(emptyResponse(204));
    const { deleteCustomModel } = await import("../api");
    // Should resolve (not throw)
    await deleteCustomModel(1);
    restoreFetch();
  });

  it("deleteCustomModel on 404 throws 'Model not found'", async () => {
    mockFetch(emptyResponse(404));
    const { deleteCustomModel } = await import("../api");
    await expect(deleteCustomModel(999)).rejects.toThrow();
    restoreFetch();
  });

  // -- testModelCapabilities --

  it("testModelCapabilities returns structured TestResult", async () => {
    mockFetch(jsonResponse(SAMPLE_TEST_RESULT, 200));
    const { testModelCapabilities } = await import("../api");
    const result = await testModelCapabilities(1, ["text"]);
    expect(result.id).toBe(1);
    expect(result.capabilities.length).toBe(1);
    expect(result.suggested_roles.length).toBeGreaterThan(0);
    expect(result.test_results.text?.passed).toBe(true);
    restoreFetch();
  });

  // -- assignModelRoles --

  it("assignModelRoles returns AssignRolesResponse", async () => {
    mockFetch(jsonResponse(SAMPLE_ASSIGN_RESPONSE, 200));
    const { assignModelRoles } = await import("../api");
    const result = await assignModelRoles(1, ["text-gen"], "test-model");
    expect(result.id).toBe(1);
    expect(result.assigned_roles.length).toBe(1);
    expect(result.assigned_roles[0]).toBe("text-gen");
    restoreFetch();
  });
});

// ── Self-test runner (safe to leave inert in production) ─────────────────────

let passed = 0;
let failed = 0;

async function run(): Promise<void> {
  for (const tc of _cases) {
    try {
      await tc.fn();
      passed++;
      // eslint-disable-next-line no-console
      console.log(`  ✓ ${tc.suite} › ${tc.name}`);
    } catch (err) {
      failed++;
      // eslint-disable-next-line no-console
      console.error(`  ✗ ${tc.suite} › ${tc.name}:`, err);
    }
  }
  // eslint-disable-next-line no-console
  console.log(`\n  ${passed} passed, ${failed} failed`);
}

if (
  typeof process !== "undefined" &&
  (process as { argv: string[] }).argv[1]?.includes("api_custom_models.test")
) {
  void run();
}

export { passed, failed, run };

// Ambient type for standalone execution check (Node.js)
declare const process: { argv: string[] } | undefined;
