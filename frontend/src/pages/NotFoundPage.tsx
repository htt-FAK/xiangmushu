import { Home } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";

export default function NotFoundPage() {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <section className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-xl border border-white/10 bg-night-900/72 p-8 text-center shadow-panel backdrop-blur-xl">
        <p className="font-display text-8xl font-semibold leading-none text-signal-cyan md:text-9xl">
          {t("notFound.title")}
        </p>
        <p className="mt-5 font-display text-2xl font-semibold text-white">
          {t("notFound.description")}
        </p>
        <div className="mt-8 flex justify-center">
          <Button type="button" onClick={() => navigate("/")}>
            <Home size={16} />
            {t("notFound.backHome")}
          </Button>
        </div>
      </div>
    </section>
  );
}
