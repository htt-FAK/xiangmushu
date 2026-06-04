import {
  BookOpen,
  Database,
  FileSearch,
  Home,
  PanelLeft,
  Sparkles,
} from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import TemplateAnalysisPage from "./pages/TemplateAnalysisPage";
import GeneratePage from "./pages/GeneratePage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import { clsx } from "./utils";

const nav = [
  { to: "/", label: "首页", icon: Home },
  { to: "/template", label: "模板分析", icon: FileSearch },
  { to: "/generate", label: "生成舱", icon: Sparkles },
  { to: "/knowledge", label: "知识库", icon: Database },
];

function Shell() {
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
              项目书生成舱
            </p>
            <p className="text-xs text-slate-500">Word template agent</p>
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
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="absolute bottom-6 left-5 right-5 border border-white/10 bg-night-950/70 p-4">
          <p className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-signal-lime">
            API
          </p>
          <p className="mt-2 break-all text-xs leading-5 text-slate-500">
            Vite 代理到 localhost:8000
          </p>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-white/10 bg-night-950/82 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex gap-2 overflow-x-auto">
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
                  {item.label}
                </NavLink>
              );
            })}
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-10">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/template" element={<TemplateAnalysisPage />} />
            <Route path="/generate" element={<GeneratePage />} />
            <Route path="/knowledge" element={<KnowledgeBasePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return <Shell />;
}
