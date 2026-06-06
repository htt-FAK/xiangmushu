import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { apiUrl } from "./apiBase";

const TOKEN_KEY = "xiangmushu.auth.token";

export type AuthUser = {
  id: number;
  email: string;
};

type VerifyCodeResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

type AuthContextValue = {
  token: string;
  isAuthenticated: boolean;
  setToken: (token: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY) ?? "";
}

export function buildAuthHeaders(): HeadersInit {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState(() => getStoredToken());

  const setToken = useCallback((value: string) => {
    window.localStorage.setItem(TOKEN_KEY, value);
    setTokenState(value);
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setTokenState("");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      setToken,
      logout,
    }),
    [logout, setToken, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

async function authRequest<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function requestLoginCode(email: string) {
  return authRequest<{ ok: boolean; email: string; expires_at: string }>(
    "/api/auth/request-code",
    { email },
  );
}

export async function verifyLoginCode(email: string, code: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/verify-code", { email, code });
}
