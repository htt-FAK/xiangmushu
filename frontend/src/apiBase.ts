const configuredApiBase = import.meta.env.VITE_API_BASE?.trim().replace(/\/+$/, "");

/**
 * Base URL for all API requests.
 * - In dev, leave empty so requests stay relative and the Vite proxy
 *   (see vite.config.ts) forwards `/api` to the backend.
 * - In production, set VITE_API_BASE to the backend origin.
 */
export const API_BASE = configuredApiBase || "";

export function apiUrl(path: string) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}
