## Why

The current web application exposes document generation workflows without an application-level user identity boundary. Adding email verification login gives the React/FastAPI application a lightweight authentication layer before protected pages are used.

## What Changes

- Add email-based registration/login where one email maps to one user account.
- Add a two-step verification flow: submit email, send a six-digit numeric code, verify the code, and receive a JWT token.
- Add a lightweight SQLite-backed database for users and verification codes.
- Add FastAPI authentication endpoints and JWT validation for protected backend routes.
- Add a dark-theme login page in the React frontend.
- Redirect unauthenticated users away from protected frontend routes (`/`, `/template`, `/generate`, `/knowledge`) to the login page.
- Add pytest coverage for core authentication behavior.

## Capabilities

### New Capabilities
- `email-auth`: Covers email verification code delivery, single-user-per-email registration/login, JWT issuance, authenticated API access, and protected frontend route behavior.

### Modified Capabilities
- None.

## Impact

- Backend: `server.py`, `config.py`, new authentication/database modules, and tests.
- Frontend: React routing/auth state, API client behavior, and a new login page under `frontend/`.
- Runtime data: new SQLite database file and related environment configuration.
- API surface: new authentication endpoints and protected route authorization behavior.
- Dependencies: JWT, password/code hashing or signed token support, and SQLite access using Python standard library where practical.
