import { ArrowRight, BarChart3, CheckCircle2, Sparkles, ShieldCheck, SkipForward } from "lucide-react";
import { useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { Button } from "../components/Button";
import { GlassCard, ScreenContainer } from "../components/AdaptiveLayout";
import { Input } from "../components/Input";
import { useAuthStore } from "../store/auth";

type Slide = {
  title: string;
  description: string;
  icon: typeof Sparkles;
};

const slides: Slide[] = [
  {
    title: "Управляйте сетками без хаоса",
    description: "Контролируйте торговые сетки, счета и историю сделок в одном спокойном интерфейсе.",
    icon: Sparkles,
  },
  {
    title: "Адаптивно под любой экран",
    description: "Панель подстраивается под телефон, планшет и десктоп без жестких размеров и обрезанных блоков.",
    icon: BarChart3,
  },
  {
    title: "Вход с защитой",
    description: "Поддерживаются обычный логин, 2FA и приглашения пользователей для команды.",
    icon: ShieldCheck,
  },
];

export function WelcomePage() {
  const navigate = useNavigate();
  const hasSeenWelcome = useAuthStore((state) => state.hasSeenWelcome);
  const profileName = useAuthStore((state) => state.profileName);
  const setWelcomeSeen = useAuthStore((state) => state.setWelcomeSeen);
  const setProfileName = useAuthStore((state) => state.setProfileName);
  const setGuestMode = useAuthStore((state) => state.setGuestMode);
  const user = useAuthStore((state) => state.user);
  const [currentPage, setCurrentPage] = useState(0);
  const [name, setName] = useState(profileName);

  const currentSlide = slides[currentPage];

  const ctaLabel = useMemo(() => {
    if (currentPage < slides.length - 1) return "Продолжить";
    return "Начать";
  }, [currentPage]);

  const finishOnboarding = () => {
    const trimmed = name.trim();
    if (trimmed) {
      setProfileName(trimmed);
    }
    setWelcomeSeen(true);
    setGuestMode(true);
    navigate("/dashboard", { replace: true });
  };

  if (hasSeenWelcome) {
    return <Navigate to={user ? "/dashboard" : "/login"} replace />;
  }

  return (
    <ScreenContainer className="flex items-start justify-center">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 py-4 sm:py-6">
        <div className="flex items-center justify-between px-1 pt-1">
          <div className="text-xs uppercase tracking-[0.32em] text-white/40">MoneyBot v2</div>
          <button
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/60 transition hover:bg-white/10 hover:text-white"
            onClick={finishOnboarding}
            type="button"
          >
            <SkipForward size={16} />
            Пропустить
          </button>
        </div>

        <GlassCard className="overflow-hidden">
          <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr] lg:items-center">
            <div className="space-y-5">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-400/20 bg-indigo-400/10 px-3 py-1 text-xs text-indigo-100">
                <Sparkles size={14} />
                Онбординг для нового интерфейса
              </div>

              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">
                  {currentSlide.title}
                </h1>
                <p className="max-w-xl text-sm leading-6 text-white/70 sm:text-base">
                  {currentSlide.description}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {slides.map((slide, index) => (
                  <button
                    key={slide.title}
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs transition ${
                      index === currentPage
                        ? "border-white/20 bg-white text-slate-950"
                        : "border-white/10 bg-white/5 text-white/60 hover:text-white"
                    }`}
                    onClick={() => setCurrentPage(index)}
                    type="button"
                  >
                    <slide.icon size={14} />
                    {index + 1}
                  </button>
                ))}
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button
                  className="inline-flex items-center justify-center gap-2 border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white shadow-[0_18px_40px_rgba(79,70,229,0.3)] hover:brightness-110"
                  onClick={() => {
                    if (currentPage < slides.length - 1) {
                      setCurrentPage((value) => value + 1);
                      return;
                    }
                    finishOnboarding();
                  }}
                >
                  {ctaLabel}
                  <ArrowRight size={16} />
                </Button>
                <Button
                  className="border border-white/10 bg-white/5 text-white hover:bg-white/10"
                  onClick={finishOnboarding}
                >
                  У меня уже есть доступ
                </Button>
              </div>
            </div>

            <GlassCard className="space-y-4 border-white/10 bg-black/20" padding="p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs uppercase tracking-[0.28em] text-white/40">Setup</div>
                  <div className="mt-1 text-lg font-semibold text-white">Как к вам обращаться?</div>
                </div>
                <div className="rounded-2xl bg-emerald-400/15 px-3 py-2 text-xs text-emerald-100">
                  optional
                </div>
              </div>

              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Ваше имя"
              />

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-400 text-white">
                    <CheckCircle2 size={20} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white">Персональный запуск</div>
                    <div className="text-xs leading-5 text-white/60">
                      Имя сохранится локально и будет использоваться в приветствии и профиле.
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button
                  className="flex-1 border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white shadow-[0_18px_40px_rgba(79,70,229,0.3)] hover:brightness-110"
                  onClick={finishOnboarding}
                >
                  Продолжить
                </Button>
                <Button
                  className="border border-white/10 bg-white/5 text-white hover:bg-white/10"
                  onClick={() => {
                    setWelcomeSeen(true);
                    setGuestMode(true);
                    navigate("/dashboard", { replace: true });
                  }}
                >
                  <SkipForward size={16} />
                </Button>
              </div>
            </GlassCard>
          </div>
        </GlassCard>
      </div>
    </ScreenContainer>
  );
}
