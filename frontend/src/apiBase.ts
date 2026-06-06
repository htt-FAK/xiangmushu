const configuredApiBase = import.meta.env.VITE_API_BASE?.trim().replace(/\/+$/, "");

export const API_BASE = configuredApiBase || "";

export function apiUrl(path: string) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}
