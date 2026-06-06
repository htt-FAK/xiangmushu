import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
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
  const [validating, setValidating] = useState(true);

  // Validate token on mount — if invalid, clear it
  useEffect(() => {
    if (!token) {
      setValidating(false);
      return;
    }
    let cancelled = false;
    fetch(apiUrl("/api/auth/me"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (cancelled) return;
        if (!res.ok) {
          window.localStorage.removeItem(TOKEN_KEY);
          setTokenState("");
        }
      })
      .catch(() => {
        if (!cancelled) {
          window.localStorage.removeItem(TOKEN_KEY);
          setTokenState("");
        }
      })
      .finally(() => {
        if (!cancelled) setValidating(false);
      });
    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
      isAuthenticated: !validating && Boolean(token),
      setToken,
      logout,
    }),
    [logout, setToken, token, validating],
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

export async function requestLoginCode(email: string, password?: string) {
  return authRequest<{ ok: boolean; email: string; expires_at: string }>(
    "/api/auth/request-code",
    { email, password },
  );
}

export async function verifyLoginCode(email: string, password: string, code: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/verify-code", { email, password, code });
}

export async function loginWithPassword(email: string, password: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/login", { email, password });
}
