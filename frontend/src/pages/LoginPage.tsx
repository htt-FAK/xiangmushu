import { AtSign, CheckCircle2, KeyRound, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { loginWithPassword, requestLoginCode, resetPassword, useAuth, verifyLoginCode } from "../auth";
import { Button, ErrorBanner, Field, Input } from "../components/ui";
import { useI18n } from "../i18n";
import { clsx } from "../utils";

type AuthMode = "login" | "register" | "forgotPassword";

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
  const isPasswordValid = password.length >= 8 && /[A-Za-z]/.test(password) && /\d/.test(password);

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
      } else if (mode === "register") {
        // Register: send verification code first
        const result = await requestLoginCode(email, password);
        setEmail(result.email);
        setSent(true);
      } else {
        const result = await requestLoginCode(email);
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
      const result =
        mode === "forgotPassword"
          ? await resetPassword(email, code, password)
          : await verifyLoginCode(email, password, code);
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

      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-6 md:py-12">
        <div className="grid w-full gap-6 md:gap-8 lg:grid-cols-[0.92fr_1.08fr] lg:items-center">
          <section>
            <div className="mb-4 inline-flex h-11 w-11 items-center justify-center border border-signal-cyan/60 bg-signal-cyan text-night-950 shadow-glow md:mb-6 md:h-12 md:w-12">
              <ShieldCheck size={24} />
            </div>
            <p className="font-display text-xs font-semibold uppercase tracking-[0.22em] text-signal-cyan md:tracking-[0.26em]">
              {t("login.eyebrow")}
            </p>
            <h1 className="mt-3 max-w-2xl font-display text-3xl font-semibold leading-tight text-white md:mt-4 md:text-5xl">
              {t("login.title")}
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-6 text-slate-300 md:mt-5 md:leading-7">
              {t("login.description")}
            </p>
          </section>

          <section className="w-full max-w-xl justify-self-end border border-white/12 bg-night-900/72 p-4 shadow-[0_24px_90px_rgba(0,0,0,0.46)] backdrop-blur-2xl sm:p-5 md:p-8">
            <div className="mb-4 grid grid-cols-2 border border-white/10 bg-night-950/70 p-1 md:mb-6">
              {(["login", "register"] as const).map((item) => (
                <button
                  key={item}
                  className={clsx(
                    "min-h-11 text-sm font-semibold transition",
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

            <div className="mb-4 flex items-start gap-3 border border-white/10 bg-white/[0.035] p-3.5 md:mb-5 md:p-4">
              <Sparkles className="mt-0.5 shrink-0 text-signal-lime" size={18} />
              <p className="text-sm leading-6 text-slate-300">
                {mode === "register"
                  ? t("login.registerHint")
                  : mode === "forgotPassword"
                    ? t("login.forgotPasswordHint")
                    : t("login.loginHint")}
              </p>
            </div>

            <ErrorBanner message={error} />

            <form className="space-y-4 md:space-y-5" onSubmit={sent ? handleVerifyCode : handleSubmit}>
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

              {mode === "forgotPassword" && sent && (
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

              {(mode !== "forgotPassword" || sent) && (
                <Field label={mode === "forgotPassword" ? t("login.newPassword") : t("login.password")}>
                  <div className="group relative">
                    <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={17} />
                    <Input
                      className="pl-10"
                      type="password"
                      autoComplete={mode === "login" ? "current-password" : "new-password"}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder={mode === "forgotPassword" ? t("login.newPasswordPlaceholder") : t("login.passwordPlaceholder")}
                      required
                    />
                  </div>
                  {(mode === "register" || mode === "forgotPassword") && (
                    <p
                      className={clsx(
                        "mt-2 flex items-center gap-2 text-xs font-semibold",
                        isPasswordValid ? "text-signal-lime" : "text-signal-rose",
                      )}
                    >
                      {isPasswordValid && <CheckCircle2 size={14} />}
                      {isPasswordValid ? t("login.passwordStrong") : t("login.passwordRule")}
                    </p>
                  )}
                </Field>
              )}

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
                  className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]"
                  type="submit"
                  disabled={
                    loading ||
                    (mode === "register" && !sent && !isPasswordValid) ||
                    (mode !== "login" && sent && code.length !== 6) ||
                    (mode === "forgotPassword" && sent && !isPasswordValid)
                  }
                >
                  {mode === "login" ? (
                    <LockKeyhole size={17} />
                  ) : mode === "forgotPassword" && sent ? (
                    <ShieldCheck size={17} />
                  ) : sent ? (
                    <ShieldCheck size={17} />
                  ) : (
                    <Mail size={17} />
                  )}
                  {mode === "login"
                    ? loading
                      ? t("login.verifying")
                      : t("login.login")
                    : mode === "forgotPassword"
                      ? loading
                        ? sent
                          ? t("login.verifying")
                          : t("login.sending")
                        : sent
                          ? t("login.resetPassword")
                          : t("login.sendResetCode")
                    : loading
                      ? sent
                        ? t("login.verifying")
                        : t("login.sending")
                      : sent
                        ? t("login.verify")
                        : t("login.sendCode")}
                </Button>
                {mode !== "login" && sent && (
                  <Button
                    className="min-h-12 w-full sm:w-auto"
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

            <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between md:mt-6">
              {mode !== "forgotPassword" && (
                <button
                  className="min-h-11 px-1 text-left text-sm font-semibold text-signal-cyan transition hover:text-white sm:px-0"
                  onClick={() => switchMode(mode === "login" ? "register" : "login")}
                  type="button"
                >
                  {mode === "login" ? t("login.needRegister") : t("login.needLogin")}
                </button>
              )}
              {mode === "login" && (
                <button
                  className="min-h-11 px-1 text-left text-sm font-semibold text-slate-400 transition hover:text-signal-cyan sm:px-0 sm:text-right"
                  onClick={() => switchMode("forgotPassword")}
                  type="button"
                >
                  {t("login.forgotPassword")}
                </button>
              )}
              {mode === "forgotPassword" && (
                <button
                  className="min-h-11 px-1 text-left text-sm font-semibold text-slate-400 transition hover:text-signal-cyan sm:px-0 sm:text-right"
                  onClick={() => switchMode("login")}
                  type="button"
                >
                  {t("login.backToLogin")}
                </button>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
