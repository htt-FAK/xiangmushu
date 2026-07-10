import {
  BarChart3,
  Database,
  Github,
  History,
  FileSearch,
  Home,
  LogOut,
  Menu,
  PanelLeft,
  Settings,
  Sparkles,
  X,
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
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const KnowledgeBasePage = lazy(() => import("./pages/KnowledgeBasePage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TemplateAnalysisPage = lazy(() => import("./pages/TemplateAnalysisPage"));

const nav = [
  { to: "/", labelKey: "nav.home", icon: Home },
  { to: "/template", labelKey: "nav.template", icon: FileSearch },
  { to: "/generate", labelKey: "nav.generate", icon: Sparkles },
  { to: "/history", labelKey: "nav.history", icon: History },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: Database },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

// P0 mobile bottom bar: only high-frequency entries; the rest open the More sheet.
// Desktop sidebar (`aside`) still renders the full `nav` above and is unaffected.
const mobileBarItems = [
  { to: "/", labelKey: "nav.home", icon: Home },
  { to: "/generate", labelKey: "nav.generate", icon: Sparkles },
  { to: "/history", labelKey: "nav.history", icon: History },
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
    return <Navigate to={`/auth?next=${encodeURIComponent(next)}`} replace />;
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
  const location = useLocation();
  const { state: workflowState } = useWorkflow();
  const activeSession = workflowState.generate.session;
  const activeGeneration = activeSession?.status === "running";
  const activeTemplateSession = workflowState.templateAnalysis.session;
  const activeTemplateAnalysis = activeTemplateSession?.status === "running";
  const [moreOpen, setMoreOpen] = useState(false);

  // Close the mobile "More" sheet whenever the route changes.
  useEffect(() => setMoreOpen(false), [location.pathname]);

  // Secondary destinations surfaced in the mobile "More" bottom sheet.
  const moreSheetItems = [
    {
      href: "https://github.com/Leonxlnx/xiangmushu",
      icon: Github,
      labelKey: "nav.github",
      isExternal: true,
    },
    { to: "/template", labelKey: "nav.template", icon: FileSearch },
    { to: "/knowledge", labelKey: "nav.knowledge", icon: Database },
    { to: "/settings", labelKey: "nav.settings", icon: Settings },
    ...(auth.isAdmin
      ? [{ to: "/admin", labelKey: "nav.admin", icon: BarChart3 }]
      : []),
  ];

  function handleLogout() {
    auth.logout();
    navigate("/auth", { replace: true });
  }

  return (
    <div className="min-h-screen bg-night-950 text-slate-100">
      <OfflineBanner />
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:border focus:border-signal-cyan/50 focus:bg-night-900 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-signal-cyan focus:shadow-glow"
      >
        Skip to content
      </a>
      <div className="fixed inset-0 -z-10 bg-[linear-gradient(115deg,#05060a_0%,#09111d_44%,#111019_100%)]" style={{ willChange: "transform" }} />
      <div className="fixed inset-0 -z-10 opacity-45 grid-mask" style={{ willChange: "transform" }} />
      <div className="fixed inset-x-0 top-0 -z-10 h-64 bg-[linear-gradient(90deg,rgba(54,242,230,0.16),rgba(255,77,141,0.08),rgba(184,255,94,0.10))]" style={{ willChange: "transform" }} />

      <aside className="fixed bottom-0 left-0 top-0 z-20 hidden w-72 border-r border-white/10 bg-night-900 px-5 py-6 lg:block">
        <div className="mb-9 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center border border-signal-cyan/50 bg-signal-cyan text-night-950">
            <PanelLeft size={20} />
          </div>
          <div>
            <p className="font-display text-lg font-semibold leading-tight text-white">
              {t("app.name")}
            </p>
            <p className="text-xs text-slate-500">{t("app.subtitle")}</p>
          </div>
        </div>

        <div className="space-y-2">
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
                <Icon size={20} />
                {t(item.labelKey)}
              </NavLink>
            );
          })}
          {auth.isAdmin && (
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
              <BarChart3 size={20} />
              {t("nav.admin")}
            </NavLink>
          )}
          <a
            href="https://github.com/Leonxlnx/xiangmushu"
            target="_blank"
            rel="noreferrer noopener"
            aria-label="GitHub repository"
            className={clsx(
              "flex min-h-12 items-center gap-3 border px-4 text-sm font-semibold transition",
              "border-white/5 bg-white/[0.025] text-slate-400 hover:border-white/20 hover:text-white hover:text-signal-cyan/80",
            )}
          >
            <Github size={20} />
            {t("nav.github", "GitHub")}
          </a>
        </div>

        <div className="absolute bottom-6 left-5 right-5 space-y-3">
          <div className="border border-white/10 bg-night-950 p-4">
            <p className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-signal-lime">
              {t("app.account")}
            </p>
            <p className="mt-2 break-all text-xs leading-5 text-slate-300">
              {auth.userEmail || "-"}
            </p>
          </div>
          <Button className="w-full" variant="ghost" onClick={handleLogout}>
            <LogOut size={16} />
            {t("nav.signOut")}
          </Button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 border-b border-white/10 bg-night-950 px-4 py-2.5 lg:hidden">
          <div className="flex min-h-10 items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-display text-[15px] font-semibold leading-tight text-white">
                {t("app.name")}
              </p>
              <p className="truncate text-[11px] leading-4 text-slate-500">{t("app.subtitle")}</p>
            </div>
            <button
              className="flex h-10 w-10 shrink-0 items-center justify-center border border-white/10 bg-white/[0.025] text-slate-400 transition hover:border-white/25 hover:text-white active:border-signal-cyan/40 active:text-signal-cyan"
              onClick={handleLogout}
              title={t("nav.signOut")}
              type="button"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        {activeGeneration && (
          <div className="border-b border-signal-cyan/20 bg-signal-cyan/10 px-4 py-2.5 text-sm text-cyan-100 md:px-8 md:py-3">
            <div className="mx-auto flex w-full max-w-7xl flex-nowrap items-center justify-between gap-2 md:flex-wrap md:gap-3">
              <span
                className="min-w-0 flex-1 truncate md:whitespace-normal"
                title={`${t("app.activeGeneration")}: ${activeSession?.currentTask || "..."} (${activeSession?.progress.done ?? 0}/${activeSession?.progress.total ?? 0})`}
              >
                <span className="md:hidden">
                  ({activeSession?.progress.done ?? 0}/{activeSession?.progress.total ?? 0}) {activeSession?.currentTask || "..."}
                </span>
                <span className="hidden md:inline">
                  {t("app.activeGeneration")}: {activeSession?.currentTask || "..."} ({activeSession?.progress.done ?? 0}/{activeSession?.progress.total ?? 0})
                </span>
              </span>
              <Button className="min-h-12 shrink-0 px-3 text-xs md:min-h-10" variant="ghost" onClick={() => navigate("/generate")}>
                {t("app.returnToGeneration")}
              </Button>
            </div>
          </div>
        )}
        {activeTemplateAnalysis && (
          <div className="border-b border-signal-lime/20 bg-signal-lime/10 px-4 py-2.5 text-sm text-lime-100 md:px-8 md:py-3">
            <div className="mx-auto flex w-full max-w-7xl flex-nowrap items-center justify-between gap-2 md:flex-wrap md:gap-3">
              <span
                className="min-w-0 flex-1 truncate md:whitespace-normal"
                title={`${t("app.activeTemplateAnalysis")}: ${activeTemplateSession?.currentPhase || activeTemplateSession?.statusMessage || "..."}`}
              >
                <span className="md:hidden">{activeTemplateSession?.currentPhase || activeTemplateSession?.statusMessage || "..."}</span>
                <span className="hidden md:inline">
                  {t("app.activeTemplateAnalysis")}: {activeTemplateSession?.currentPhase || activeTemplateSession?.statusMessage || "..."}
                </span>
              </span>
              <Button className="min-h-12 shrink-0 px-3 text-xs md:min-h-10" variant="ghost" onClick={() => navigate("/template")}>
                {t("app.returnToTemplate")}
              </Button>
            </div>
          </div>
        )}
        <PullToRefresh>
        <main id="main-content" className="mx-auto w-full max-w-7xl px-4 pb-[calc(5.5rem+env(safe-area-inset-bottom,0px))] pt-5 overscroll-y-contain md:px-8 md:pb-10 md:pt-10">
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
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/knowledge" element={<KnowledgeBasePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </main>
        </PullToRefresh>

        <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-night-950 px-2 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-1.5 lg:hidden">
          <div className="grid grid-cols-4 gap-1">
            {mobileBarItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    clsx(
                      "relative flex min-h-14 flex-col items-center justify-center gap-0.5 border px-2 text-[12px] font-semibold leading-tight transition active:scale-[0.98]",
                      isActive
                        ? "border-signal-cyan/45 bg-signal-cyan/10 text-signal-cyan shadow-glow before:absolute before:left-1/2 before:top-0 before:h-0.5 before:w-7 before:-translate-x-1/2 before:bg-signal-cyan before:shadow-[0_0_18px_rgba(54,242,230,0.75)]"
                        : "border-transparent text-slate-500 hover:bg-white/[0.025] hover:text-slate-300 active:text-signal-cyan/80",
                    )
                  }
                >
                  <Icon size={16} strokeWidth={2.2} />
                  <span className="max-w-full whitespace-nowrap">{t(item.labelKey)}</span>
                </NavLink>
              );
            })}
            <button
              key="more"
              type="button"
              onClick={() => setMoreOpen(true)}
              className={clsx(
                "relative flex min-h-14 flex-col items-center justify-center gap-0.5 border px-2 text-[12px] font-semibold leading-tight transition active:scale-[0.98]",
                moreOpen
                  ? "border-signal-cyan/45 bg-signal-cyan/10 text-signal-cyan shadow-glow before:absolute before:left-1/2 before:top-0 before:h-0.5 before:w-7 before:-translate-x-1/2 before:bg-signal-cyan before:shadow-[0_0_18px_rgba(54,242,230,0.75)]"
                  : "border-transparent text-slate-500 hover:bg-white/[0.025] hover:text-slate-300 active:text-signal-cyan/80",
              )}
            >
              <Menu size={16} strokeWidth={2.2} />
              <span className="max-w-full whitespace-nowrap">{t("nav.more")}</span>
            </button>
          </div>
        </nav>

        {moreOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              aria-label={t("generate.close")}
              className="absolute inset-0 cursor-default bg-night-950"
              onClick={() => setMoreOpen(false)}
            />
            <div className="absolute inset-x-0 bottom-0 border-t border-white/10 bg-night-900 pb-[max(env(safe-area-inset-bottom),0.5rem)] shadow-panel">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <p className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-signal-cyan">
                  {t("nav.more")}
                </p>
                <button
                  type="button"
                  onClick={() => setMoreOpen(false)}
                  aria-label={t("generate.close")}
                  className="flex h-9 w-9 items-center justify-center border border-white/10 text-slate-400 transition hover:border-white/25 hover:text-white"
                >
                  <X size={20} />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2 p-3">
                {moreSheetItems.map((item) => {
                  const Icon = item.icon;
                  if (item.isExternal && "href" in item) {
                    return (
                      <a
                        key={item.href}
                        href={item.href}
                        target="_blank"
                        rel="noreferrer noopener"
                        aria-label={t(item.labelKey, "GitHub")}
                        onClick={() => setMoreOpen(false)}
                        className={clsx(
                          "flex min-h-14 flex-col items-center justify-center gap-1.5 border px-3 text-sm font-semibold transition",
                          "border-white/10 bg-white/[0.025] text-slate-300 hover:border-white/25 hover:text-white hover:text-signal-cyan/80",
                        )}
                      >
                        <Icon size={20} />
                        <span className="whitespace-nowrap">{t("nav.github", "GitHub")}</span>
                      </a>
                    );
                  }
                  return (
                    <NavLink
                      key={(item as { to: string }).to}
                      to={(item as { to: string }).to}
                      onClick={() => setMoreOpen(false)}
                      className={({ isActive }) =>
                        clsx(
                          "flex min-h-14 flex-col items-center justify-center gap-1.5 border px-3 text-sm font-semibold transition",
                          isActive
                            ? "border-signal-cyan/45 bg-signal-cyan/10 text-signal-cyan"
                            : "border-white/10 bg-white/[0.025] text-slate-300 hover:border-white/25 hover:text-white",
                        )
                      }
                    >
                      <Icon size={20} />
                      <span className="whitespace-nowrap">{t(item.labelKey)}</span>
                    </NavLink>
                  );
                })}
              </div>
              <div className="p-3 pt-0">
                <button
                  type="button"
                  onClick={() => {
                    setMoreOpen(false);
                    handleLogout();
                  }}
                  className="flex min-h-12 w-full items-center justify-center gap-2 border border-signal-rose/40 bg-signal-rose/10 px-4 text-sm font-semibold text-signal-rose transition hover:bg-signal-rose hover:text-white"
                >
                  <LogOut size={20} />
                  <span className="whitespace-nowrap">{t("nav.signOut")}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/auth/*" element={<LoginPage />} />
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
