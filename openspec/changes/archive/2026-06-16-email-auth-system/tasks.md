## 1. Backend Auth Foundation

- [x] 1.1 Add auth configuration constants to `config.py` and `.env.example` for SQLite path, JWT secret/expiry, code TTL, and optional SMTP settings.
- [x] 1.2 Add `core/auth.py` with SQLite schema initialization, email normalization, user lookup/create, verification-code create/consume, JWT issue/validate, and email delivery logging/SMTP helper.

## 2. FastAPI Integration

- [x] 2.1 Add public auth endpoints in `server.py`: `POST /api/auth/request-code`, `POST /api/auth/verify-code`, and `GET /api/auth/me`.
- [x] 2.2 Add a FastAPI current-user dependency and protect knowledge base, template, generate, and download API routes with bearer JWT validation.

## 3. Frontend Login and Route Protection

- [x] 3.1 Add frontend auth utilities/context in `frontend/src` for token persistence, auth API calls, and authenticated fetch headers.
- [x] 3.2 Add a dark-theme login page for email input, six-digit code verification, loading states, and error feedback.
- [x] 3.3 Update `frontend/src/App.tsx` routing so `/login` is public and `/`, `/template`, `/generate`, and `/knowledge` redirect unauthenticated users to login while preserving the destination.
- [x] 3.4 Update existing frontend API calls and streaming generation to include the JWT bearer token.

## 4. Tests and Validation

- [x] 4.1 Add pytest coverage for email normalization/uniqueness, code request/verification, invalid code rejection, JWT issuance, and protected API 401 behavior.
- [x] 4.2 Run backend tests, frontend build/type checks where available, and `openspec validate email-auth-system --json`.
