import { Activity, ArrowLeftRight, BarChart3, CandlestickChart, ClipboardList, Home, LogOut, ScrollText, Shield, UserCircle, Users } from "lucide-react";
import type { PropsWithChildren } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { logout } from "../api/auth";
import { useAuthStore } from "../store/auth";
import { PageTransition } from "./PageTransition";

const navItems = [
  { to: "/dashboard", label: "Дашборд", shortLabel: "Дашб.", icon: Home },
  { to: "/grids", label: "Сетки", icon: BarChart3 },
  { to: "/chart", label: "График", icon: CandlestickChart },
  { to: "/logs", label: "Логи", icon: ScrollText },
  { to: "/trades", label: "Сделки", icon: ArrowLeftRight },
  { to: "/monitoring", label: "Мониторинг", shortLabel: "Монит.", icon: Activity },
  { to: "/accounts", label: "Аккаунты", shortLabel: "Акк.", icon: ClipboardList },
  { to: "/users", label: "Пользователи", shortLabel: "Юзеры", icon: Users },
  { to: "/audit", label: "Аудит", icon: Shield },
  { to: "/profile", label: "Профиль", icon: UserCircle },
];

export function Layout({ children }: PropsWithChildren) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const tokens = useAuthStore((state) => state.tokens);
  const isGuest = useAuthStore((state) => state.isGuest);
  const profileName = useAuthStore((state) => state.profileName);
  const clear = useAuthStore((state) => state.logout);

  const onLogout = async () => {
    if (tokens?.access_token && tokens?.refresh_token) {
      await logout(tokens.access_token, tokens.refresh_token).catch(() => undefined);
    }
    clear();
    navigate("/login");
  };

  const visibleItems = navItems.filter((item) => {
    if (isGuest && item.to !== "/dashboard") return false;
    return true;
  });

  const displayName = user?.full_name || profileName || "Гость";
  const displayRole = user?.role || (isGuest ? "guest" : "viewer");

  return (
    <div className="min-h-[100dvh] w-full overflow-x-hidden bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.18),_transparent_30%),linear-gradient(180deg,#08111f_0%,#0d1324_52%,#070b12_100%)] text-white">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[70] focus:rounded-xl focus:bg-indigo-500 focus:px-4 focus:py-2 focus:text-white focus:text-sm">
        Перейти к содержимому
      </a>
      <div className="mx-auto flex min-h-[100dvh] w-full max-w-[1440px] flex-col md:flex-row">
        <aside className="hidden shrink-0 border-r border-white/10 bg-white/5 p-6 backdrop-blur-2xl md:block md:w-[clamp(17rem,22vw,22rem)]">
          <Link to="/dashboard" className="mb-8 block text-2xl font-semibold tracking-tight text-white">
            MoneyBot v2
          </Link>
          <nav className="space-y-1" aria-label="Основная навигация">
            {visibleItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition-all duration-200 ${isActive ? "bg-white text-slate-950 shadow-lg font-medium" : "text-white/70 hover:bg-white/10 hover:text-white"}`
                }
              >
                <item.icon size={18} />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <button className="mt-8 flex items-center gap-2 text-sm text-white/50 transition hover:text-white" onClick={onLogout}>
            <LogOut size={16} />
            {isGuest ? "Выйти из гостевого режима" : "Выйти"}
          </button>
        </aside>

        <div className="flex-1 min-w-0 pb-20 md:pb-0 overflow-x-hidden">
          <header className="border-b border-white/10 bg-white/5 px-3 py-3 backdrop-blur-xl sm:px-6 sm:py-4">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-[10px] sm:text-xs uppercase tracking-[0.28em] text-white/50">MoneyBot</div>
                <div className="text-base sm:text-lg font-semibold text-white truncate">{displayName}</div>
              </div>
              <div className="shrink-0 rounded-full border border-white/10 bg-white/10 px-2.5 py-0.5 text-[10px] sm:text-xs text-white/75">
                {displayRole}
              </div>
            </div>
          </header>
          <main id="main-content" className="p-3 sm:p-6"><PageTransition>{children}</PageTransition></main>
        </div>
      </div>

      <nav
        className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-[#06070b]/95 px-1 py-1 pb-[max(env(safe-area-inset-bottom),0.25rem)] backdrop-blur-2xl md:hidden"
        aria-label="Мобильная навигация"
      >
        <div className="no-scrollbar flex gap-0.5 overflow-x-auto">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex shrink-0 flex-col items-center justify-center gap-0.5 rounded-xl min-w-[3.2rem] px-1.5 py-1.5 text-[9px] transition-all duration-200 ${isActive ? "bg-white text-slate-950 font-semibold" : "text-white/45 active:text-white/70"}`
              }
            >
              <item.icon size={17} />
              <span className="leading-none truncate max-w-full">{item.shortLabel || item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
