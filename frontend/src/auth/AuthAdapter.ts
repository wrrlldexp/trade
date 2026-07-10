/**
 * AuthAdapter определяет, в какой среде запущено приложение,
 * и абстрагирует получение данных аутентификации.
 *
 * - web:      обычный браузер → email + пароль + 2FA через REST
 * - telegram: внутри Telegram Mini App → initData передаётся бэкенду
 * - vk:       внутри VK Mini App → initParams через VK Bridge
 *
 * На Шаге 5 это будет полноценный модуль. Сейчас — каркас и автодетект.
 */

export type AuthEnvironment = "web" | "telegram" | "vk";

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: Record<string, unknown>;
  themeParams: Record<string, string>;
  ready: () => void;
  expand: () => void;
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
  };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
    vkBridge?: {
      send: (method: string, params?: Record<string, unknown>) => Promise<unknown>;
    };
  }
}

export function detectEnvironment(): AuthEnvironment {
  if (typeof window === "undefined") return "web";
  if (window.Telegram?.WebApp?.initData) return "telegram";
  if (window.vkBridge) return "vk";
  return "web";
}

export function applyNativeTheme(): void {
  const tg = window.Telegram?.WebApp;
  if (tg?.themeParams) {
    const root = document.documentElement;
    for (const [key, value] of Object.entries(tg.themeParams)) {
      root.style.setProperty(`--tg-theme-${key.replace(/_/g, "-")}`, value);
    }
    tg.ready();
    tg.expand();
  }
}

export function bindTelegramBackButton(onClick: () => void): void {
  const tg = window.Telegram?.WebApp;
  if (!tg?.BackButton) return;
  tg.BackButton.show();
  tg.BackButton.onClick(onClick);
}

export interface AuthInitData {
  environment: AuthEnvironment;
  initData?: string; // для Telegram
  vkParams?: Record<string, unknown>; // для VK
}

export async function getInitData(): Promise<AuthInitData> {
  const env = detectEnvironment();

  if (env === "telegram") {
    return {
      environment: "telegram",
      initData: window.Telegram!.WebApp!.initData,
    };
  }

  if (env === "vk") {
    try {
      const params = (await window.vkBridge!.send("VKWebAppGetLaunchParams")) as Record<
        string,
        unknown
      >;
      return { environment: "vk", vkParams: params };
    } catch {
      return { environment: "vk" };
    }
  }

  return { environment: "web" };
}
