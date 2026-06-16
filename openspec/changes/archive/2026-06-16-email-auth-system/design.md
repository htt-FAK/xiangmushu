## Context

The FastAPI backend is currently centered in `server.py` and serves both JSON/SSE APIs and the React SPA fallback. The React app already uses route-based pages under `frontend/src` and a dark Tailwind theme. There is no user identity, token storage, SQLite persistence, or route protection.

This change crosses backend API, persistence, frontend routing, API client behavior, configuration, and tests. It also introduces security-sensitive behavior around verification codes and JWT tokens.

## Goals / Non-Goals

**Goals:**
- Provide email verification registration/login with one normalized email per user.
- Persist users and verification codes in SQLite without requiring an external database service.
- Issue and validate JWT bearer tokens for protected API routes.
- Add a dark-theme React login page and authenticated route guard for `/`, `/template`, `/generate`, and `/knowledge`.
- Keep implementation small and compatible with the existing FastAPI/Vite structure.
- Add pytest coverage for user uniqueness, code verification, token issuance, and protected API rejection.

**Non-Goals:**
- Password login, OAuth, account recovery, roles, teams, or admin management.
- Production-grade email provider integration beyond a configurable SMTP hook and development logging fallback.
- Server-side session storage; JWT tokens remain bearer tokens.
- Streamlit `app.py` authentication.

## Decisions

### SQLite auth store in a dedicated module
Add `core/auth.py` (or equivalent focused module) to own SQLite schema initialization, user lookup/creation, verification-code storage, and JWT helpers. `server.py` imports this module and wires FastAPI endpoints/dependencies.

Alternative considered: place all logic in `server.py`. This avoids a file but makes testing and security review harder in an already broad module.

### Standard-library SQLite, explicit schema migration
Use Python's `sqlite3` module with tables:
- `users(id, email, created_at, last_login_at)` with `email` unique.
- `email_verification_codes(id, email, code_hash, expires_at, consumed_at, created_at)` with lookup by normalized email.

Schema initialization runs at app startup/import through an idempotent helper. This keeps setup lightweight and avoids adding an ORM.

Alternative considered: SQLAlchemy. It is more scalable but unnecessary for two auth tables and would add dependency surface.

### Hashed verification codes and latest-code semantics
Store only a SHA-256/HMAC hash of the six-digit code, never the raw code. Verification checks the latest unconsumed code for the normalized email and rejects expired, consumed, superseded, or malformed codes.

Alternative considered: store raw codes for simpler debugging. This weakens the database security posture for little benefit.

### JWT with configurable secret and expiry
Issue HS256 JWT access tokens containing at least `sub` (user id), `email`, and `exp`. Read `AUTH_JWT_SECRET`, `AUTH_JWT_EXPIRE_MINUTES`, `AUTH_DB_PATH`, `AUTH_CODE_TTL_MINUTES`, and mail settings from `config.py` environment-backed constants. Use a development fallback secret with a warning so local runs still work.

Alternative considered: opaque tokens in SQLite. That enables revocation but introduces server-side token storage and cleanup that is not required by the specs.

### Email delivery adapter with logging fallback
Provide a small `send_verification_email(email, code)` function. If SMTP configuration is present, send via SMTP; otherwise log the code with `logging` for local development and tests.

Alternative considered: require a provider API immediately. That violates the lightweight/no-extra-service constraint and blocks local testing.

### FastAPI dependency for protected APIs
Add `get_current_user` using `HTTPBearer`/authorization header validation. Apply it to protected API endpoints used by the authenticated pages:
- Knowledge base APIs
- Template APIs
- Generate SSE API
- Download API

Auth endpoints and SPA/static serving remain public. This preserves frontend routing and lets unauthenticated users load `/login`.

### Frontend token persistence and route guard
Add an auth utility/context that reads/writes token to `localStorage`, appends `Authorization: Bearer <token>` in API calls, and exposes login/logout state. Add `/login` as a public route and wrap existing routes in a `ProtectedRoute` component that redirects to `/login?next=<path>`.

Alternative considered: cookie-based auth. Cookies can improve UX but require CSRF decisions and cookie attributes; bearer token storage is simpler for this app.

### Flow

```text
User -> React /login: enter email
React -> POST /api/auth/request-code
FastAPI -> SQLite: store latest six-digit code hash + expiry
FastAPI -> SMTP/logging: deliver code
User -> React /login: enter code
React -> POST /api/auth/verify-code
FastAPI -> SQLite: validate latest unexpired unused code
FastAPI -> SQLite: create or reuse user by normalized email
FastAPI -> React: JWT access token
React -> localStorage: persist token
React -> protected route/API: Authorization bearer token
FastAPI -> protected endpoint: validate JWT or return 401
```

## Risks / Trade-offs

- [Risk] Development logging exposes verification codes in server logs. -> Mitigation: use only when SMTP is not configured and clearly log that this is a development fallback.
- [Risk] JWT tokens cannot be revoked before expiry. -> Mitigation: keep expiry configurable and reasonably short by default.
- [Risk] Browser `localStorage` tokens are vulnerable to XSS. -> Mitigation: keep the existing React rendering model, avoid unsafe HTML, and limit token payload/scope.
- [Risk] Protecting all APIs can break unauthenticated smoke usage. -> Mitigation: keep auth endpoints and SPA/static public; tests document the new 401 behavior.
- [Risk] SQLite file path differences in tests can leak state. -> Mitigation: support `AUTH_DB_PATH` override and test against temporary databases.

## Migration Plan

1. Add configuration defaults and `.env.example` entries.
2. Add auth persistence/JWT/email helpers with idempotent schema initialization.
3. Add public auth endpoints and protected-route dependency in `server.py`.
4. Add frontend login page, route guard, token persistence, and API authorization header injection.
5. Add pytest coverage and run OpenSpec validation.

Rollback: remove the new auth dependency from protected routes, stop mounting `/login` in the frontend, and leave the SQLite database file unused. No existing document data migration is required.

## Open Questions

- Which SMTP provider and sender identity should be used in production?
- Should JWT expiry be short with refresh tokens later, or long enough for a simple single-token MVP?
