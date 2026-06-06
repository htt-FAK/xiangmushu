import { AtSign, CheckCircle2, KeyRound, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { loginWithPassword, requestLoginCode, useAuth, verifyLoginCode } from "../auth";
import { Button, ErrorBanner, Field, Input } from "../components/ui";
import { useI18n } from "../i18n";
import { clsx } from "../utils";

type AuthMode = "login" | "register";

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const auth = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();

  const params = new URLSearchParams(location.search);
  const next = params.get("next") || "/";
  const isRegisterPasswordValid = password.length >= 8 && /[A-Za-z]/.test(password) && /\d/.test(password);

  function switchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setSent(false);
    setCode("");
    setError("");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        // Login: email + password only, no verification code
        const result = await loginWithPassword(email, password);
        auth.setToken(result.access_token);
        navigate(next, { replace: true });
      } else {
        // Register: send verification code first
        const result = await requestLoginCode(email, password);
        setEmail(result.email);
        setSent(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : (mode === "login" ? t("login.verifyError") : t("login.sendError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyCode(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await verifyLoginCode(email, password, code);
      auth.setToken(result.access_token);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.verifyError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen overflow-hidden bg-night-950 text-slate-100">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_18%_18%,rgba(54,242,230,0.24),transparent_28%),radial-gradient(circle_at_78%_22%,rgba(184,255,94,0.12),transparent_26%),linear-gradient(115deg,#05060a_0%,#09111d_46%,#120b17_100%)]" />
      <div className="fixed inset-0 -z-10 opacity-45 grid-mask" />
      <div className="pointer-events-none fixed -left-24 top-20 h-72 w-72 rounded-full bg-signal-cyan/10 blur-3xl animate-pulse" />
      <div className="pointer-events-none fixed -right-24 bottom-10 h-80 w-80 rounded-full bg-signal-rose/10 blur-3xl animate-pulse" />

      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-12">
        <div className="grid w-full gap-8 lg:grid-cols-[0.92fr_1.08fr] lg:items-center">
          <section>
            <div className="mb-6 inline-flex h-12 w-12 items-center justify-center border border-signal-cyan/60 bg-signal-cyan text-night-950 shadow-glow">
              <ShieldCheck size={24} />
            </div>
            <p className="font-display text-xs font-semibold uppercase tracking-[0.26em] text-signal-cyan">
              {t("login.eyebrow")}
            </p>
            <h1 className="mt-4 max-w-2xl font-display text-4xl font-semibold leading-tight text-white md:text-5xl">
              {t("login.title")}
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300">
              {t("login.description")}
            </p>
          </section>

          <section className="w-full max-w-xl justify-self-end border border-white/12 bg-night-900/72 p-6 shadow-[0_24px_90px_rgba(0,0,0,0.46)] backdrop-blur-2xl md:p-8">
            <div className="mb-6 grid grid-cols-2 border border-white/10 bg-night-950/70 p-1">
              {(["login", "register"] as const).map((item) => (
                <button
                  key={item}
                  className={clsx(
                    "min-h-10 text-sm font-semibold transition",
                    mode === item
                      ? "bg-signal-cyan text-night-950 shadow-glow"
                      : "text-slate-400 hover:text-white",
                  )}
                  onClick={() => switchMode(item)}
                  type="button"
                >
                  {t(`login.${item}`)}
                </button>
              ))}
            </div>

            <div className="mb-5 flex items-start gap-3 border border-white/10 bg-white/[0.035] p-4">
              <Sparkles className="mt-0.5 shrink-0 text-signal-lime" size={18} />
              <p className="text-sm leading-6 text-slate-300">
                {mode === "register" ? t("login.registerHint") : t("login.loginHint")}
              </p>
            </div>

            <ErrorBanner message={error} />

            <form className="space-y-5" onSubmit={sent ? handleVerifyCode : handleSubmit}>
              <Field label={t("login.email")}>
                <div className="group relative">
                  <AtSign className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={17} />
                  <Input
                    className="pl-10"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder={t("login.emailPlaceholder")}
                    required
                  />
                </div>
              </Field>

              <Field label={t("login.password")}>
                <div className="group relative">
                  <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={17} />
                  <Input
                    className="pl-10"
                    type="password"
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder={t("login.passwordPlaceholder")}
                    required
                  />
                </div>
                {mode === "register" && (
                  <p
                    className={clsx(
                      "mt-2 flex items-center gap-2 text-xs font-semibold",
                      isRegisterPasswordValid ? "text-signal-lime" : "text-signal-rose",
                    )}
                  >
                    {isRegisterPasswordValid && <CheckCircle2 size={14} />}
                    {isRegisterPasswordValid ? t("login.passwordStrong") : t("login.passwordRule")}
                  </p>
                )}
              </Field>

              {mode === "register" && sent && (
                <Field label={t("login.code")}>
                  <div className="group relative">
                    <KeyRound className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={17} />
                    <Input
                      className="pl-10 tracking-[0.24em]"
                      inputMode="numeric"
                      maxLength={6}
                      pattern="\\d{6}"
                      value={code}
                      onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                      placeholder={t("login.codePlaceholder")}
                      required
                    />
                  </div>
                </Field>
              )}

              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <Button
                  type="submit"
                  disabled={
                    loading ||
                    (mode === "register" && !sent && !isRegisterPasswordValid) ||
                    (mode === "register" && sent && code.length !== 6)
                  }
                >
                  {mode === "login" ? (
                    <LockKeyhole size={17} />
                  ) : sent ? (
                    <ShieldCheck size={17} />
                  ) : (
                    <Mail size={17} />
                  )}
                  {mode === "login"
                    ? loading
                      ? t("login.verifying")
                      : t("login.login")
                    : loading
                      ? sent
                        ? t("login.verifying")
                        : t("login.sending")
                      : sent
                        ? t("login.verify")
                        : t("login.sendCode")}
                </Button>
                {mode === "register" && sent && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setSent(false);
                      setCode("");
                      setError("");
                    }}
                  >
                    {t("login.changeEmail")}
                  </Button>
                )}
              </div>
            </form>

            <button
              className="mt-6 text-sm font-semibold text-signal-cyan transition hover:text-white"
              onClick={() => switchMode(mode === "login" ? "register" : "login")}
              type="button"
            >
              {mode === "login" ? t("login.needRegister") : t("login.needLogin")}
            </button>
          </section>
        </div>
      </main>
    </div>
  );
}
