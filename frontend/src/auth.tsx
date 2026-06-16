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
import { parseApiErrorMessage } from "./errors";

const TOKEN_KEY = "xiangmushu.auth.token";

export type Language = "zh" | "en";

export type AuthUser = {
  id: number;
  email: string;
};

type VerifyCodeResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

export type AccountState = "unknown_email" | "existing_verified" | "existing_unverified" | "restricted";

type AuthIdentifyResponse = {
  email: string;
  account_state: AccountState;
};

type RecoveryVerifyResponse = {
  ok: boolean;
  email: string;
  recovery_token: string;
};

type AuthContextValue = {
  token: string;
  isAuthenticated: boolean;
  validating: boolean;
  userEmail: string;
  isAdmin: boolean;
  language: Language;
  setToken: (token: string) => void;
  setLanguage: (language: Language) => Promise<void>;
  refreshPreferences: () => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY) ?? "";
}

export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function buildAuthHeaders(): HeadersInit {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function normalizeLanguage(value: unknown): Language {
  return value === "en" ? "en" : "zh";
}

function bearerHeaders(tokenValue: string): HeadersInit {
  return { Authorization: `Bearer ${tokenValue}` };
}

async function fetchMe(tokenValue: string): Promise<{ email?: string; is_admin?: boolean }> {
  const response = await fetch(apiUrl("/api/auth/me"), {
    headers: bearerHeaders(tokenValue),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as { email?: string; is_admin?: boolean };
}

async function fetchUserPreferences(tokenValue: string): Promise<Language> {
  const response = await fetch(apiUrl("/api/user/preferences"), {
    headers: bearerHeaders(tokenValue),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = (await response.json()) as { language?: unknown };
  return normalizeLanguage(data.language);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState(() => getStoredToken());
  const [validating, setValidating] = useState(true);
  const [userEmail, setUserEmail] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [language, setLanguageState] = useState<Language>("zh");

  // Validate token on mount — if invalid, clear it
  useEffect(() => {
    if (!token) {
      setLanguageState("zh");
      setValidating(false);
      return;
    }
    let cancelled = false;
    fetchMe(token)
      .then(async (data) => {
        if (cancelled) return;
        setUserEmail(data.email ?? "");
        setIsAdmin(Boolean(data.is_admin));
        try {
          const nextLanguage = await fetchUserPreferences(token);
          if (!cancelled) setLanguageState(nextLanguage);
        } catch {
          if (!cancelled) setLanguageState("zh");
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearStoredToken();
          setTokenState("");
          setUserEmail("");
          setIsAdmin(false);
          setLanguageState("zh");
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
    void fetchMe(value)
      .then((data) => {
        setUserEmail(data.email ?? "");
        setIsAdmin(Boolean(data.is_admin));
      })
      .catch(() => undefined);
    void fetchUserPreferences(value)
      .then(setLanguageState)
      .catch(() => setLanguageState("zh"));
  }, []);

  const refreshPreferences = useCallback(async () => {
    if (!token) {
      setLanguageState("zh");
      return;
    }
    setLanguageState(await fetchUserPreferences(token));
  }, [token]);

  const setLanguage = useCallback(
    async (value: Language) => {
      const previous = language;
      setLanguageState(value);
      if (!token) return;
      const response = await fetch(apiUrl("/api/user/preferences"), {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ language: value }),
      });
      if (!response.ok) {
        setLanguageState(previous);
        const message = await response.text();
        throw new Error(message || `HTTP ${response.status}`);
      }
      const data = (await response.json()) as { language?: unknown };
      setLanguageState(normalizeLanguage(data.language));
    },
    [language, token],
  );

  const logout = useCallback(() => {
    clearStoredToken();
    setTokenState("");
    setUserEmail("");
    setIsAdmin(false);
    setLanguageState("zh");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: !validating && Boolean(token),
      validating,
      userEmail,
      isAdmin,
      language,
      setToken,
      setLanguage,
      refreshPreferences,
      logout,
    }),
    [language, logout, refreshPreferences, setLanguage, setToken, token, validating, userEmail, isAdmin],
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
    const raw = await response.text();
    throw new Error(parseApiErrorMessage(raw, `HTTP ${response.status}`));
  }
  return (await response.json()) as T;
}

export async function requestLoginCode(email: string, password?: string) {
  return authRequest<{ ok: boolean; email: string; expires_at: string }>(
    "/api/auth/request-code",
    { email, password },
  );
}

export async function identifyAccount(email: string) {
  return authRequest<AuthIdentifyResponse>("/api/auth/identify", { email });
}

export async function startSignup(email: string, password: string) {
  return authRequest<{ ok: boolean; email: string; expires_at: string }>("/api/auth/signup/start", { email, password });
}

export async function resendSignup(email: string) {
  return authRequest<{ ok: boolean; email: string; expires_at: string }>("/api/auth/signup/resend", { email });
}

export async function verifySignup(email: string, code: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/signup/verify", { email, code });
}

export async function verifyLoginCode(email: string, password: string, code: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/verify-code", { email, password, code });
}

export async function loginWithPassword(email: string, password: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/login", { email, password });
}

export async function resetPassword(email: string, code: string, newPassword: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/reset-password", {
    email,
    code,
    new_password: newPassword,
  });
}

export async function startRecovery(email: string) {
  return authRequest<{ ok: boolean; email: string; expires_at: string }>("/api/auth/recovery/start", { email });
}

export async function verifyRecovery(email: string, code: string) {
  return authRequest<RecoveryVerifyResponse>("/api/auth/recovery/verify", { email, code });
}

export async function completeRecovery(email: string, recoveryToken: string, newPassword: string) {
  return authRequest<VerifyCodeResponse>("/api/auth/recovery/complete", {
    email,
    recovery_token: recoveryToken,
    new_password: newPassword,
  });
}
