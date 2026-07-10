import { create } from "zustand";

import type { TokenPair, User } from "../api/types";

interface AuthState {
  user: User | null;
  tokens: TokenPair | null;
  temporaryToken: string | null;
  hasSeenWelcome: boolean;
  profileName: string;
  isGuest: boolean;
  isInitializing: boolean;
  setAuth: (user: User, tokens: TokenPair) => void;
  setTemporaryToken: (token: string | null) => void;
  setWelcomeSeen: (value: boolean) => void;
  setProfileName: (value: string) => void;
  setGuestMode: (value: boolean) => void;
  setInitializing: (value: boolean) => void;
  logout: () => void;
}

function readStored<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    window.localStorage.removeItem(key);
    return null;
  }
}

function writeStored(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export const useAuthStore = create<AuthState>((set) => ({
  user: readStored<User>("moneybot.user"),
  tokens: readStored<TokenPair>("moneybot.tokens"),
  temporaryToken: null,
  hasSeenWelcome: readStored<boolean>("moneybot.hasSeenWelcome") ?? false,
  profileName: readStored<string>("moneybot.profileName") ?? "",
  isGuest: readStored<boolean>("moneybot.isGuest") ?? false,
  isInitializing: !!readStored<TokenPair>("moneybot.tokens"),
  setAuth: (user, tokens) => {
    writeStored("moneybot.user", user);
    writeStored("moneybot.tokens", tokens);
    writeStored("moneybot.isGuest", false);
    set({ user, tokens, temporaryToken: null, isGuest: false });
  },
  setTemporaryToken: (temporaryToken) => set({ temporaryToken }),
  setWelcomeSeen: (hasSeenWelcome) => {
    writeStored("moneybot.hasSeenWelcome", hasSeenWelcome);
    set({ hasSeenWelcome });
  },
  setProfileName: (profileName) => {
    writeStored("moneybot.profileName", profileName);
    set({ profileName });
  },
  setGuestMode: (isGuest) => {
    writeStored("moneybot.isGuest", isGuest);
    set({ isGuest });
  },
  setInitializing: (isInitializing) => set({ isInitializing }),
  logout: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("moneybot.user");
      window.localStorage.removeItem("moneybot.tokens");
      window.localStorage.removeItem("moneybot.isGuest");
    }
    set({ user: null, tokens: null, temporaryToken: null, isGuest: false });
  },
}));
