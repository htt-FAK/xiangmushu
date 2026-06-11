import {
  BarChart3,
  Database,
  FileSearch,
  Home,
  LogOut,
  PanelLeft,
  Settings,
  Sparkles,
} from "lucide-react";
import {
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { lazy, Suspense, useEffect, useState } from "react";
import type { ReactElement } from "react";
import { useAuth } from "./auth";
import { useWorkflow } from "./workflow";
import { Button } from "./components/ui";
import { useI18n } from "./i18n";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import { clsx } from "./utils";
import { PullToRefresh } from "./components/PullToRefresh";

const AdminPage = lazy(() => import("./pages/AdminPage"));
const GeneratePage = lazy(() => import("./pages/GeneratePage"));
const KnowledgeBasePage = lazy(() => import("./pages/KnowledgeBasePage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TemplateAnalysisPage = lazy(() => import("./pages/TemplateAnalysisPage"));

const nav = [
  { to: "/", labelKey: "nav.home", icon: Home },
  { to: "/template", labelKey: "nav.template", icon: FileSearch },
  { to: "/generate", labelKey: "nav.generate", icon: Sparkles },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: Database },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

function ProtectedRoute({ children }: { children: ReactElement }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.validating) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-night-950 text-slate-400">
        <div className="text-sm font-semibold tracking-widest uppercase">Loading...</div>
      </div>
    );
  }
  if (!auth.isAuthenticated) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return children;
}

function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine);
  useEffect(() => {
    const onOff = () => setOffline(true);
    const onOn = () => setOffline(false);
    window.addEventListener("offline", onOff);
    window.addEventListener("online", onOn);
    return () => {
      window.removeEventListener("offline", onOff);
      window.removeEventListener("online", onOn);
    };
  }, []);
  if (!offline) return null;
  return (
    <div className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-2 bg-signal-amber px-3 py-2 text-xs font-bold text-night-950 shadow-lg">
      <span>⚠</span>
      <span>Network disconnected — some features may be unavailable</span>
    </div>
  );
}

function Shell() {
  const auth = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const { state: workflowState } = useWorkflow();
  const activeSession = workflowState.generate.session;
  const activeGeneration = activeSession?.status === "running";

  function handleLogout() {
    auth.logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-night-950 text-slate-100">
      <OfflineBanner />
      <div className="fixed inset-0 -z-10 bg-[linear-gradient(115deg,#05060a_0%,#09111d_44%,#111019_100%)]" />
      <div className="fixed inset-0 -z-10 opacity-45 grid-mask" />
      <div className="fixed inset-x-0 top-0 -z-10 h-64 bg-[linear-gradient(90deg,rgba(54,242,230,0.16),rgba(255,77,141,0.08),rgba(184,255,94,0.10))]" />

      <aside className="fixed bottom-0 left-0 top-0 z-20 hidden w-72 border-r border-white/10 bg-night-900/88 px-5 py-6 backdrop-blur-xl lg:block">
        <div className="mb-9 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center border border-signal-cyan/50 bg-signal-cyan text-night-950">
            <PanelLeft size={21} />
          </div>
          <div>
            <p className="font-display text-lg font-semibold leading-tight text-white">
              {t("app.name")}
            </p>
            <p className="text-xs text-slate-500">{t("app.subtitle")}</p>
          </div>
        </div>

        <nav className="space-y-2">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  clsx(
                    "flex min-h-12 items-center gap-3 border px-4 text-sm font-semibold transition",
                    isActive
                      ? "border-signal-cyan/60 bg-signal-cyan/12 text-signal-cyan"
                      : "border-white/5 bg-white/[0.025] text-slate-400 hover:border-white/20 hover:text-white",
                  )
                }
              >
                <Icon size={18} />
                {t(item.labelKey)}
              </NavLink>
            );
          })}
          {auth.userEmail === "3406847927@qq.com" && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                clsx(
                  "flex min-h-12 items-center gap-3 border px-4 text-sm font-semibold transition",
                  isActive
                    ? "border-signal-lime/60 bg-signal-lime/12 text-signal-lime"
                    : "border-white/5 bg-white/[0.025] text-slate-400 hover:border-white/20 hover:text-white",
                )
              }
            >
              <BarChart3 size={18} />
              {t("nav.admin")}
            </NavLink>
          )}
        </nav>

        <div className="absolute bottom-6 left-5 right-5 space-y-3">
          <div className="border border-white/10 bg-night-950/70 p-4">
            <p className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-signal-lime">
              {t("app.account")}
            </p>
            <p className="mt-2 break-all text-xs leading-5 text-slate-300">
              {auth.userEmail || "-"}
            </p>
          </div>
          <Button className="w-full" variant="ghost" onClick={handleLogout}>
            <LogOut size={17} />
            {t("nav.signOut")}
          </Button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 border-b border-white/10 bg-night-950/90 px-4 py-2.5 backdrop-blur-md lg:hidden">
          <div className="flex min-h-10 items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-display text-[15px] font-semibold leading-tight text-white">
                {t("app.name")}
              </p>
              <p className="truncate text-[11px] leading-4 text-slate-500">{t("app.subtitle")}</p>
            </div>
            <button
              className="flex h-10 w-10 shrink-0 items-center justify-center border border-white/10 bg-white/[0.035] text-slate-400 transition hover:border-white/25 hover:text-white active:border-signal-cyan/40 active:text-signal-cyan"
              onClick={handleLogout}
              title={t("nav.signOut")}
              type="button"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        {activeGeneration && (
          <div className="border-b border-signal-cyan/20 bg-signal-cyan/10 px-4 py-3 text-sm text-cyan-100 md:px-8">
            <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3">
              <span>
                {t("app.activeGeneration")}: {activeSession?.currentTask || "..."} ({activeSession?.progress.done ?? 0}/{activeSession?.progress.total ?? 0})
              </span>
              <Button className="min-h-10 px-3 text-xs" variant="ghost" onClick={() => navigate("/generate")}>
                {t("app.returnToGeneration")}
              </Button>
            </div>
          </div>
        )}
        <PullToRefresh>
        <main className="mx-auto w-full max-w-7xl px-4 pb-36 pt-5 overscroll-y-contain md:px-8 md:pb-10 md:pt-10">
          <Suspense
            fallback={
              <div className="py-12 text-sm font-semibold tracking-widest text-slate-400 uppercase">
                Loading...
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/template" element={<TemplateAnalysisPage />} />
              <Route path="/generate" element={<GeneratePage />} />
              <Route path="/knowledge" element={<KnowledgeBasePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </main>
        </PullToRefresh>

        <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-night-950/92 px-2 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-1.5 backdrop-blur-md lg:hidden">
          <div className="grid grid-cols-5 gap-1">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    clsx(
                      "relative flex min-h-14 flex-col items-center justify-center gap-0.5 overflow-hidden border px-1 text-[11px] font-semibold leading-tight transition active:scale-[0.98]",
                      isActive
                        ? "border-signal-cyan/45 bg-signal-cyan/10 text-signal-cyan shadow-glow before:absolute before:left-1/2 before:top-0 before:h-0.5 before:w-7 before:-translate-x-1/2 before:bg-signal-cyan before:shadow-[0_0_18px_rgba(54,242,230,0.75)]"
                        : "border-transparent text-slate-500 hover:bg-white/[0.035] hover:text-slate-300 active:text-signal-cyan/80",
                    )
                  }
                >
                  <Icon size={17} strokeWidth={2.2} />
                  <span className="max-w-full truncate">{t(item.labelKey)}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Shell />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
