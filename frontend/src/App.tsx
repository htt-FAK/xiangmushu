import {
  Database,
  FileSearch,
  Home,
  Languages,
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
import type { ReactElement } from "react";
import { useAuth } from "./auth";
import { Button } from "./components/ui";
import { useI18n } from "./i18n";
import GeneratePage from "./pages/GeneratePage";
import HomePage from "./pages/HomePage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import LoginPage from "./pages/LoginPage";
import SettingsPage from "./pages/SettingsPage";
import TemplateAnalysisPage from "./pages/TemplateAnalysisPage";
import { clsx } from "./utils";

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

function Shell() {
  const auth = useAuth();
  const { language, setLanguage, t } = useI18n();
  const navigate = useNavigate();

  function handleLogout() {
    auth.logout();
    navigate("/login", { replace: true });
  }

  function toggleLanguage() {
    setLanguage(language === "zh" ? "en" : "zh");
  }

  return (
    <div className="min-h-screen bg-night-950 text-slate-100">
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
          <Button className="w-full" variant="ghost" onClick={toggleLanguage} title={t("lang.switch")}>
            <Languages size={17} />
            {language === "zh" ? "English" : "中文"}
          </Button>
          <Button className="w-full" variant="ghost" onClick={handleLogout}>
            <LogOut size={17} />
            {t("nav.signOut")}
          </Button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-white/10 bg-night-950/82 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center gap-2 overflow-x-auto">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    clsx(
                      "flex shrink-0 items-center gap-2 border px-3 py-2 text-xs font-semibold",
                      isActive
                        ? "border-signal-cyan/60 text-signal-cyan"
                        : "border-white/10 text-slate-400",
                    )
                  }
                >
                  <Icon size={15} />
                  {t(item.labelKey)}
                </NavLink>
              );
            })}
            <button
              className="ml-auto flex h-9 w-9 shrink-0 items-center justify-center border border-white/10 text-slate-400"
              onClick={toggleLanguage}
              title={t("lang.switch")}
              type="button"
            >
              <Languages size={16} />
            </button>
            <button
              className="flex h-9 w-9 shrink-0 items-center justify-center border border-white/10 text-slate-400"
              onClick={handleLogout}
              title={t("nav.signOut")}
              type="button"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-10">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/template" element={<TemplateAnalysisPage />} />
            <Route path="/generate" element={<GeneratePage />} />
            <Route path="/knowledge" element={<KnowledgeBasePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
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
