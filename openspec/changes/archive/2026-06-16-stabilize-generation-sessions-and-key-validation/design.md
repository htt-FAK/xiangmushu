## Context

The current FastAPI + React application treats generation as a page-scoped streaming action. `GeneratePage` owns all live state in local component memory, starts a single `POST /api/generate` request, and loses that in-memory progress as soon as the route unmounts. `KnowledgeBasePage` follows a similar pattern for selected library context, upload results, and current statistics. This creates the visible symptom users reported: after navigating away and coming back, the work appears to have disappeared even though the underlying data may still exist or the backend may still be running.

The product also currently lets users save a personal API Key without proving that it works. The existing key-management change introduced encrypted storage and request-time usage of saved keys, but not pre-save validation. In addition, the current generation flow collapses many downstream provider failures into generic generation errors, so the frontend cannot reliably tell users whether a key is invalid, quota is exhausted, model permissions are missing, or the provider/network is temporarily unavailable.

This change is cross-cutting for four reasons:

1. Generation must move from a page-owned live stream to a recoverable server-owned session model.
2. API Key validation must be split from generation and must bypass any platform-key fallback behavior.
3. The shell and multiple pages need shared workflow-awareness state for onboarding and active-generation visibility.
4. New requirements affect backend APIs, frontend routing/state, and landing/shell behavior together.

```text
Current

GeneratePage mount
  -> local useState owns outputs/progress/current task
  -> POST /api/generate
  -> route change/unmount
  -> state lost

Target

POST /api/generate/sessions
  -> server creates generation session
  -> client subscribes to session stream
  -> route change/unmount
  -> session keeps running on server
  -> client returns to /generate
  -> fetch session snapshot + reconnect to stream
```

## Goals / Non-Goals

**Goals:**
- Preserve workflow-critical page state across route changes, especially Generate and Knowledge Base context.
- Introduce recoverable generation sessions that remain queryable and streamable after navigation away from `/generate`.
- Ensure returning users can see the current generation snapshot immediately and then continue watching live progress.
- Require successful API Key validation before save, using the user-provided key directly with no silent fallback to platform credentials.
- Normalize API Key and generation errors into structured categories that the frontend can turn into actionable guidance.
- Add shell-level and landing-level onboarding so first-time users know the required order of operations.
- Add the provided SVG as the browser tab icon and align shell branding with the guided workflow.

**Non-Goals:**
- No background job queue, distributed workers, or durable long-term task orchestration beyond the scope needed for recoverable in-process sessions.
- No promise of browser-close or server-restart recovery for active generation sessions in this change.
- No support for multiple provider families in API Key validation; this change remains focused on the current Aliyun Bailian-compatible flow.
- No guarantee that validating one model implies the key can access every optional model in the product.
- No redesign of all existing pages; onboarding changes should layer on top of the current visual language.

## Decisions

### Decision: Introduce explicit server-owned generation sessions

Generation will no longer be modeled only as a one-shot page request. The backend will create a session record for each active generation and expose:

- a start endpoint that returns a `session_id`
- a snapshot/status endpoint for recovery
- a stream endpoint keyed by `session_id`

The session will hold the minimal recoverable state needed for UI restoration: user ownership, params snapshot, current status, progress, current task, generated outputs so far, billing so far, report/download paths when available, and the latest terminal error if any.

Why this over browser-only persistence:
- Browser-only persistence can restore stale snapshots, but cannot continue real-time progress once the original stream connection is lost.
- The user explicitly wants to return to the page and keep seeing live progress, which requires a reconnectable server source of truth.
- A server-owned session also gives the shell a single place to ask whether a user currently has an active generation.

Alternative considered:
- Keep `/api/generate` as-is and only persist frontend state to `localStorage` or a global store. Rejected because it cannot satisfy the “continue watching live progress” requirement.

### Decision: Keep generation execution in-process, but separate session lifecycle from stream transport

The backend will continue running generation in the current FastAPI process and existing generation codepaths, but session orchestration will be factored above the SSE transport. The session manager will own:

- session creation
- latest snapshot updates
- append-only event history or replay-safe recent events
- terminal state transition

The stream endpoint will subscribe to session events instead of directly owning generation execution state.

Why this over introducing a task queue now:
- The codebase already runs generation inside the web process; a queue/worker architecture would be a much larger infrastructure change.
- The immediate need is recoverability across route changes, not horizontal scaling.
- A session abstraction created now can later back a real worker system without forcing another frontend contract redesign.

Alternative considered:
- Introduce Celery/Redis or a durable work queue immediately. Rejected as out of scope for the current stability-focused change.

### Decision: Restrict active generation to one session per user at a time

The system will treat generation as a single active workflow per authenticated user for now. Starting a new generation while another session is still running should either reuse the current session context deliberately or reject the new request with a clear response, depending on final UX choice during implementation.

Why:
- It keeps shell indicators, recovery logic, and ownership semantics simple.
- The existing UI is already designed around one active generation workspace.
- It avoids ambiguous “which active session should be restored when I return to `/generate`?” behavior.

Alternative considered:
- Allow multiple concurrent sessions per user. Rejected because it would force a session picker UI, more complex stream subscription management, and more complicated storage rules.

### Decision: Split API Key validation into a dedicated strict validation flow

API Key validation will not reuse the full generation path. Instead, the backend will add a dedicated validation routine and route that:

- accepts a candidate key from the authenticated user
- creates a provider client using only that key
- probes a small ordered set of low-cost candidate models
- returns structured validation output
- only persists the key if validation succeeds

Why this over “save first, discover later during generation”:
- Users need confidence before entering the main workflow.
- Strong validation is an explicit product requirement.
- The generation path has fallback logic and more moving parts, which would make validation results less trustworthy.

Alternative considered:
- Save the key first and show a warning if validation fails. Rejected because the product decision is to block save until the key is proven usable.

### Decision: Classify validation and generation failures into structured error codes

Both the new key-validation endpoint and the generation session flow will normalize known provider failures into stable application-level codes such as:

- `invalid_api_key`
- `quota_exceeded`
- `permission_denied`
- `model_unavailable`
- `network_error`
- `provider_error`
- `unknown_error`

Validation may include per-model probe results, but it must also emit one summary classification for the UI.

Why:
- The frontend currently cannot reliably distinguish “wrong key” from “temporary outage.”
- The user specifically asked to avoid falsely blaming the key when the network/provider is at fault.
- Structured codes are easier to localize and reuse in Settings and Generate.

Alternative considered:
- Continue sending free-form error text only. Rejected because it is brittle, hard to localize, and not reliable enough for product guidance.

### Decision: Treat page-context preservation and generation-session recovery as two separate layers

Not every workflow state needs a server-backed session.

- Generate live run state: server-backed session + reconnectable stream
- Generate selection/setup state: frontend persistence/shared workflow store
- Knowledge Base selected slug, recent upload results, latest stats: frontend persistence/shared workflow store

Why:
- Knowledge Base context loss is a page-state continuity problem, not a live background task problem.
- Keeping lightweight page context client-side avoids unnecessary backend complexity.
- Separating these layers prevents over-engineering simple UI continuity problems.

Alternative considered:
- Store all UI state server-side. Rejected because only active generation progress needs server recovery guarantees.

### Decision: Add shell-level workflow awareness and guided readiness checks

The shell and key pages will expose a simple readiness model:

- API Key saved and validated
- at least one knowledge base exists
- the active knowledge base has uploaded content
- at least one template exists
- generation is ready / blocked by prerequisites

This will power homepage guidance, Generate page prerequisite messaging, and a shell-level active generation indicator.

Why:
- The current product expects the user to infer page order on their own.
- A lightweight readiness model gives onboarding structure without a heavy guided-tour dependency.
- The shell already wraps all protected pages and is the right place to surface active-generation status.

Alternative considered:
- Add only static help text. Rejected because it does not reflect the user’s actual setup status.

### Decision: Ship the provided SVG as the primary favicon

The browser tab icon will use the provided SVG asset as the primary branded favicon referenced from `frontend/index.html`. If implementation later reveals small-size clarity issues, a simplified derivative may be added, but the initial requirement is to use the provided brand asset.

Why:
- The current app has no favicon configured.
- This is a low-cost improvement to product identity and makes the app easier to recognize among many browser tabs.

Alternative considered:
- Delay favicon work to a later branding pass. Rejected because this change already touches shell/onboarding polish and the asset is already defined.

## Risks / Trade-offs

- [Risk] In-process generation sessions can still be lost on server restart -> Mitigation: document this as an accepted limitation for this change and keep the session abstraction isolated so durable storage can be added later.
- [Risk] Session/event synchronization increases backend complexity -> Mitigation: centralize session management in one module instead of spreading state across API handlers.
- [Risk] Validation against a small model set may mark a key valid even if some premium models remain inaccessible -> Mitigation: return the successful probe model and message that validation proves baseline usability, not universal model access.
- [Risk] Provider SDK errors may not map cleanly to one classification -> Mitigation: prefer deterministic mappings for known exceptions/status codes and fall back to `provider_error` or `unknown_error` with raw diagnostic detail logged server-side.
- [Risk] Shell-level readiness indicators can drift from backend truth -> Mitigation: derive readiness from explicit APIs or already-loaded canonical data, not duplicated heuristics scattered across components.
- [Risk] Frontend persistence for upload results or selected context can become stale -> Mitigation: persist only recent UX context, and refresh canonical knowledge/template lists from the server when pages remount.

## Migration Plan

1. Add the change specs that define generation-session recovery, API Key validation, onboarding/readiness, and shell branding behavior.
2. Introduce backend session orchestration and authenticated recovery endpoints while keeping the existing generation internals reusable.
3. Add strict API Key validation endpoints and structured error mapping without changing encrypted storage semantics.
4. Refactor the frontend to use a shared workflow state layer, recover active generation sessions on `/generate`, and expose shell/home readiness indicators.
5. Add the provided SVG icon to frontend assets and reference it from the HTML entrypoint.
6. Verify with backend tests plus frontend build/type checks.

Rollback strategy:
- Frontend can revert to page-local generation state and the old Settings save flow.
- New session and validation routes can remain unused if reverted; any ephemeral session storage can be safely discarded.

## Open Questions

1. When a user attempts to start a second generation while one session is still running, should the backend reject it outright or should the frontend force the user back into the active session?
2. How much recent event history should the session manager retain for reconnection: full replay, snapshot-only, or snapshot plus a short replay buffer?
3. Should successful API Key validation persist any metadata such as the model that passed validation, or should that remain transient UI-only information?
