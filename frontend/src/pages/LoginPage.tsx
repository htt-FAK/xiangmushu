import { KeyRound, Mail, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { requestLoginCode, useAuth, verifyLoginCode } from "../auth";
import { Button, ErrorBanner, Field, Input, Panel } from "../components/ui";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const params = new URLSearchParams(location.search);
  const next = params.get("next") || "/";

  async function handleRequestCode(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await requestLoginCode(email);
      setEmail(result.email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send verification code");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyCode(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await verifyLoginCode(email, code);
      auth.setToken(result.access_token);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid verification code");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-night-950 text-slate-100">
      <div className="fixed inset-0 -z-10 bg-[linear-gradient(115deg,#05060a_0%,#09111d_44%,#111019_100%)]" />
      <div className="fixed inset-0 -z-10 opacity-45 grid-mask" />
      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-10">
        <div className="grid w-full gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
          <section>
            <div className="mb-6 inline-flex h-12 w-12 items-center justify-center border border-signal-cyan/60 bg-signal-cyan text-night-950">
              <ShieldCheck size={24} />
            </div>
            <p className="font-display text-xs font-semibold uppercase tracking-[0.26em] text-signal-cyan">
              Secure Access
            </p>
            <h1 className="mt-4 font-display text-4xl font-semibold leading-tight text-white md:text-5xl">
              Sign in with your email
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300">
              Use a six-digit verification code to enter the project document workspace.
            </p>
          </section>

          <Panel className="w-full max-w-xl justify-self-end p-6 md:p-8">
            <ErrorBanner message={error} />
            {!sent ? (
              <form className="space-y-5" onSubmit={handleRequestCode}>
                <Field label="Email">
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" size={17} />
                    <Input
                      className="pl-10"
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="name@example.com"
                      required
                    />
                  </div>
                </Field>
                <Button className="w-full" type="submit" disabled={loading}>
                  <Mail size={17} />
                  {loading ? "Sending..." : "Send Code"}
                </Button>
              </form>
            ) : (
              <form className="space-y-5" onSubmit={handleVerifyCode}>
                <Field label="Email">
                  <Input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </Field>
                <Field label="Verification Code">
                  <div className="relative">
                    <KeyRound className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" size={17} />
                    <Input
                      className="pl-10 tracking-[0.24em]"
                      inputMode="numeric"
                      maxLength={6}
                      pattern="\\d{6}"
                      value={code}
                      onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                      placeholder="000000"
                      required
                    />
                  </div>
                </Field>
                <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                  <Button type="submit" disabled={loading || code.length !== 6}>
                    <ShieldCheck size={17} />
                    {loading ? "Verifying..." : "Verify"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setSent(false);
                      setCode("");
                      setError("");
                    }}
                  >
                    Change Email
                  </Button>
                </div>
              </form>
            )}
          </Panel>
        </div>
      </main>
    </div>
  );
}
