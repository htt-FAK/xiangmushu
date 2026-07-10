import { AtSign, CheckCircle2, KeyRound, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  completeRecovery,
  identifyAccount,
  loginWithPassword,
  resendSignup,
  startRecovery,
  startSignup,
  useAuth,
  verifyRecovery,
  verifySignup,
  type AccountState,
} from "../auth";
import { Button, ErrorBanner, Field, Input } from "../components/ui";
import { normalizeErrorMessage } from "../errors";
import { useI18n } from "../i18n";
import { clsx } from "../utils";

type AuthStep = "entry" | "login" | "signup" | "signupVerify" | "verifyAccount" | "recovery" | "recoveryVerify" | "recoveryReset";

function routeStep(pathname: string): AuthStep {
  if (pathname.endsWith("/login")) return "login";
  if (pathname.endsWith("/signup/verify")) return "signupVerify";
  if (pathname.endsWith("/signup")) return "signup";
  if (pathname.endsWith("/verify-account")) return "verifyAccount";
  if (pathname.endsWith("/recovery/verify")) return "recoveryVerify";
  if (pathname.endsWith("/recovery/reset")) return "recoveryReset";
  if (pathname.endsWith("/recovery")) return "recovery";
  return "entry";
}

function stepPath(step: AuthStep): string {
  switch (step) {
    case "login":
      return "/auth/login";
    case "signup":
      return "/auth/signup";
    case "signupVerify":
      return "/auth/signup/verify";
    case "verifyAccount":
      return "/auth/verify-account";
    case "recovery":
      return "/auth/recovery";
    case "recoveryVerify":
      return "/auth/recovery/verify";
    case "recoveryReset":
      return "/auth/recovery/reset";
    default:
      return "/auth";
  }
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [recoveryToken, setRecoveryToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [resendMsg, setResendMsg] = useState("");
  const cooldownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const auth = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const step = routeStep(location.pathname);
  const params = new URLSearchParams(location.search);
  const rawNext = params.get("next") || "/";
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/";
  const isPasswordValid = password.length >= 8 && /[A-Za-z]/.test(password) && /\d/.test(password);

  useEffect(() => {
    if (cooldown <= 0) return;
    cooldownRef.current = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          if (cooldownRef.current) clearInterval(cooldownRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => {
      if (cooldownRef.current) clearInterval(cooldownRef.current);
    };
  }, [cooldown > 0]);

  const startCooldown = useCallback(() => setCooldown(60), []);

  function go(stepName: AuthStep) {
    navigate(`${stepPath(stepName)}?next=${encodeURIComponent(next)}`, { replace: true });
    setError("");
    setResendMsg("");
  }

  async function handleEntry(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await identifyAccount(email);
      const accountState: AccountState = result.account_state;
      if (accountState === "existing_verified") {
        go("login");
      } else if (accountState === "existing_unverified") {
        go("verifyAccount");
      } else if (accountState === "restricted") {
        setError(t("login.restricted"));
      } else {
        go("signup");
      }
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.sendError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await loginWithPassword(email, password);
      auth.setToken(result.access_token);
      navigate(next, { replace: true });
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.verifyError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleSignupStart(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await startSignup(email, password);
      setEmail(result.email);
      startCooldown();
      go("signupVerify");
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.sendError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleSignupVerify(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await verifySignup(email, code);
      auth.setToken(result.access_token);
      navigate(next, { replace: true });
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.verifyError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleSignupResend() {
    if (cooldown > 0 || loading) return;
    setLoading(true);
    setError("");
    setResendMsg("");
    try {
      await resendSignup(email);
      setCode("");
      startCooldown();
      setResendMsg(t("login.resendSuccess"));
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.resendFailed")));
    } finally {
      setLoading(false);
    }
  }

  async function handleRecoveryStart(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await startRecovery(email);
      setEmail(result.email);
      startCooldown();
      go("recoveryVerify");
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.sendError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleRecoveryVerify(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await verifyRecovery(email, code);
      setRecoveryToken(result.recovery_token);
      go("recoveryReset");
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.verifyError")));
    } finally {
      setLoading(false);
    }
  }

  async function handleRecoveryComplete(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await completeRecovery(email, recoveryToken, password);
      auth.setToken(result.access_token);
      navigate(next, { replace: true });
    } catch (err) {
      setError(normalizeErrorMessage(err, t("login.verifyError")));
    } finally {
      setLoading(false);
    }
  }

  const intro =
    step === "login"
      ? t("login.loginHint")
      : step === "signup" || step === "signupVerify" || step === "verifyAccount"
        ? t("login.registerHint")
        : step === "recovery" || step === "recoveryVerify" || step === "recoveryReset"
          ? t("login.forgotPasswordHint")
          : t("login.description");

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
            <p className="mt-4 max-w-xl text-sm leading-6 text-slate-300 md:mt-5 md:leading-7">{intro}</p>
          </section>

          <section className="w-full max-w-xl justify-self-end border border-white/12 bg-night-900 p-4 shadow-[0_24px_90px_rgba(5,6,10,0.5)] sm:p-5 md:p-8">
            <div className="mb-4 flex items-start gap-3 border border-white/10 bg-white/[0.025] p-3.5 md:mb-5 md:p-4">
              <Sparkles className="mt-0.5 shrink-0 text-signal-lime" size={20} />
              <p className="text-sm leading-6 text-slate-300">{intro}</p>
            </div>

            <ErrorBanner message={error} />
            {resendMsg && (
              <div className="mb-3 flex items-center gap-2  border border-signal-lime/30 bg-signal-lime/10 px-3 py-2 text-sm font-medium text-signal-lime">
                <CheckCircle2 size={16} />
                {resendMsg}
              </div>
            )}

            {step === "entry" && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleEntry}>
                <Field label={t("login.email")}>
                  <div className="group relative">
                    <AtSign className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("login.emailPlaceholder")} required />
                  </div>
                </Field>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading}>
                  <Mail size={16} />
                  {loading ? t("login.sending") : t("login.sendCode")}
                </Button>
              </form>
            )}

            {step === "login" && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleLogin}>
                <Field label={t("login.email")}>
                  <div className="group relative">
                    <AtSign className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("login.emailPlaceholder")} required />
                  </div>
                </Field>
                <Field label={t("login.password")}>
                  <div className="group relative">
                    <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t("login.passwordPlaceholder")} required />
                  </div>
                </Field>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading}>
                  <LockKeyhole size={16} />
                  {loading ? t("login.verifying") : t("login.login")}
                </Button>
                <div className="flex justify-between text-sm font-semibold">
                  <button className="text-signal-cyan transition hover:text-white" onClick={() => go("signup")} type="button">{t("login.needRegister")}</button>
                  <button className="text-slate-400 transition hover:text-signal-cyan" onClick={() => go("recovery")} type="button">{t("login.forgotPassword")}</button>
                </div>
              </form>
            )}

            {(step === "signup" || step === "verifyAccount") && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleSignupStart}>
                <Field label={t("login.email")}>
                  <div className="group relative">
                    <AtSign className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("login.emailPlaceholder")} required />
                  </div>
                </Field>
                <Field label={t("login.password")}>
                  <div className="group relative">
                    <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t("login.passwordPlaceholder")} required />
                  </div>
                  <p className={clsx("mt-2 flex items-center gap-2 text-xs font-semibold", isPasswordValid ? "text-signal-lime" : "text-signal-rose")}>{isPasswordValid && <CheckCircle2 size={14} />}{isPasswordValid ? t("login.passwordStrong") : t("login.passwordRule")}</p>
                </Field>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading || !isPasswordValid}>
                  <Mail size={16} />
                  {loading ? t("login.sending") : t("login.sendCode")}
                </Button>
                <div className="flex justify-between text-sm font-semibold">
                  <button className="text-signal-cyan transition hover:text-white" onClick={() => go("login")} type="button">{t("login.needLogin")}</button>
                  {step === "verifyAccount" && <button className="text-slate-400 transition hover:text-signal-cyan" onClick={() => go("signupVerify")} type="button">{t("login.verify")}</button>}
                </div>
              </form>
            )}

            {step === "signupVerify" && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleSignupVerify}>
                <Field label={t("login.email")}>
                  <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("login.emailPlaceholder")} required />
                </Field>
                <Field label={t("login.code")}>
                  <div className="group relative">
                    <KeyRound className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10 tracking-[0.24em]" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder={t("login.codePlaceholder")} required />
                  </div>
                </Field>
                <div className="flex items-center justify-between">
                  <button className={clsx("text-sm font-semibold transition", cooldown > 0 ? "cursor-not-allowed text-slate-500" : "text-signal-cyan hover:text-white")} disabled={cooldown > 0 || loading} onClick={handleSignupResend} type="button">
                    {cooldown > 0 ? t("login.resendCooldown").replace("{n}", String(cooldown)) : t("login.resendCode")}
                  </button>
                </div>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading || code.length !== 6}>
                  <ShieldCheck size={16} />
                  {loading ? t("login.verifying") : t("login.verify")}
                </Button>
              </form>
            )}

            {step === "recovery" && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleRecoveryStart}>
                <Field label={t("login.email")}>
                  <div className="group relative">
                    <AtSign className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("login.emailPlaceholder")} required />
                  </div>
                </Field>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading}>
                  <Mail size={16} />
                  {loading ? t("login.sending") : t("login.sendResetCode")}
                </Button>
                <button className="text-sm font-semibold text-slate-400 transition hover:text-signal-cyan" onClick={() => go("login")} type="button">{t("login.backToLogin")}</button>
              </form>
            )}

            {step === "recoveryVerify" && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleRecoveryVerify}>
                <Field label={t("login.email")}>
                  <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("login.emailPlaceholder")} required />
                </Field>
                <Field label={t("login.code")}>
                  <div className="group relative">
                    <KeyRound className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10 tracking-[0.24em]" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder={t("login.codePlaceholder")} required />
                  </div>
                </Field>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading || code.length !== 6}>
                  <ShieldCheck size={16} />
                  {loading ? t("login.verifying") : t("login.verify")}
                </Button>
              </form>
            )}

            {step === "recoveryReset" && (
              <form className="space-y-4 md:space-y-5" onSubmit={handleRecoveryComplete}>
                <Field label={t("login.newPassword")}>
                  <div className="group relative">
                    <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 transition group-focus-within:text-signal-cyan" size={16} />
                    <Input className="pl-10" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t("login.newPasswordPlaceholder")} required />
                  </div>
                  <p className={clsx("mt-2 flex items-center gap-2 text-xs font-semibold", isPasswordValid ? "text-signal-lime" : "text-signal-rose")}>{isPasswordValid && <CheckCircle2 size={14} />}{isPasswordValid ? t("login.passwordStrong") : t("login.passwordRule")}</p>
                </Field>
                <Button className="min-h-12 w-full border-signal-cyan bg-signal-cyan font-bold shadow-[0_0_0_1px_rgba(54,242,230,0.22),0_18px_54px_rgba(54,242,230,0.18)]" type="submit" disabled={loading || !isPasswordValid || !recoveryToken}>
                  <ShieldCheck size={16} />
                  {loading ? t("login.verifying") : t("login.resetPassword")}
                </Button>
              </form>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
